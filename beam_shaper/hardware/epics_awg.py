import logging
import math
import time

import epics
import numpy as np

from beam_shaper.core.interfaces import AwgWriteError, WriteCancelled, never_cancel

log = logging.getLogger(__name__)

WRITE_METHODS = ("pts", "wfm")


class EpicsAwg:
    # Seconds to wait for the IOC to refresh its readback, and for the IDIL/AWG
    # message buffer to clear after pausing scanning. Tests shorten these.
    READ_SETTLE_TIME = 2.0
    BUFFER_CLEAR_TIME = 1.0
    # Readback may differ from what was written by this many DAC counts (rounding)
    VERIFY_TOLERANCE = 1

    def __init__(self, prefix, pulse_size, max_percent_change, write_method, wait_time):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_percent_change
        self.wait_time = wait_time
        if write_method not in WRITE_METHODS:
            log.warning(
                "Invalid AWG write method '%s' in config.ini (valid: wfm = whole waveform, "
                "pts = point by point). Defaulting to point by point",
                write_method,
            )
            write_method = "pts"
        self.write_method = write_method

    def _read_current_shape(self):
        log.info("Read current shape...")
        epics.caput(self.prefix + ":ReadWaveform_ascii_do.PROC", 1)
        time.sleep(self.READ_SETTLE_TIME)
        wf = epics.caget(self.prefix + ":ReadWaveform_ascii_do", use_monitor=False)
        dac = epics.caget(self.prefix + ":DAC", use_monitor=False)
        if wf is None or dac is None:
            raise AwgWriteError("Can't read the AWG waveform from %s" % self.prefix)
        self.dac = dac
        self.wf = np.clip(np.asarray(wf), 0, dac)
        self.nwf = self.wf / float(dac)

    def read_raw_shape(self):
        self._read_current_shape()
        return self.wf

    def read_normalised_shape(self):
        self._read_current_shape()
        return self.nwf

    def pause_scanning(self):
        epics.caput(self.prefix + ":_SelScanDisable", 1)

    def resume_scanning(self):
        epics.caput(self.prefix + ":_SelScanDisable", 0)

    def write(self, points, zero_to_end, progress, cancel=never_cancel):
        # The shape must have been read first: writes are checked against it
        if not hasattr(self, "wf"):
            self._read_current_shape()
        previous = np.array(self.wf, copy=True)
        self.pause_scanning()  # Stop IDIL/AWG comms while writing curve
        try:
            time.sleep(self.BUFFER_CLEAR_TIME)  # Let the message buffer clear
            if self.write_method == "pts":
                expected = self._write_point_by_point(points, zero_to_end, progress, cancel)
            else:
                expected = self._write_waveform(points, progress, cancel)
        except WriteCancelled:
            self._verify(previous, "after restoring the previous trace")
            raise
        finally:
            self.resume_scanning()  # Restart the comms now finished writing
        self._verify(expected, "after writing")

    def _verify(self, expected, when):
        """Read the AWG back and check it holds `expected` (DAC counts)."""
        self._read_current_shape()
        actual = self.wf[: len(expected)]
        wrong = np.flatnonzero(np.abs(actual - expected) > self.VERIFY_TOLERANCE)
        if len(wrong) == 0:
            return
        i = wrong[0]
        raise AwgWriteError(
            "AWG readback {0} differs at {1} sample(s); first at sample {2}: "
            "expected {3:.0f}, read {4:.0f}. The AWG state is uncertain.".format(
                when, len(wrong), i, expected[i], actual[i]
            )
        )

    def _write_waveform(self, points, progress, cancel):
        data = np.zeros(len(self.wf))
        data[0 : len(points)] = points

        progress.start("Sending waveform", "Buffering values")
        try:
            # Send each of the points to the correct record. Nothing reaches the AWG
            # until SetWaveform is processed, so stopping here leaves it unchanged.
            pv_prefix = self.prefix + ":HoldSampleNorm"
            for i in range(0, len(data)):
                if cancel():
                    raise WriteCancelled("AWG write stopped before sending; AWG unchanged")
                epics.caput(pv_prefix + str(i), data[i])
            time.sleep(1)

            progress.update(None, "Writing waveform to AWG")
            # Write the whole waveform to the AWG
            epics.caput(self.prefix + ":SetWaveform.PROC", 1)

            # Wait for the IOC to send not busy before continuing
            while epics.caget(self.prefix + ":SetWaveformBusy", use_monitor=False):
                progress.update(None, "Waiting for AWG response")
                time.sleep(0.2)
        finally:
            progress.finish()
        return np.round(data * self.dac)

    def _limited_value(self, i, val):
        """val, limited so no point changes by more than max_incr percent of the DAC."""
        incr = 100.0 * math.fabs(val - self.wf[i]) / float(self.dac)
        if incr < self.max_incr:
            return val, incr, False
        if val - self.wf[i] < 0:
            val = self.wf[i] - (self.max_incr / 100.0) * self.dac
        else:
            val = self.wf[i] + (self.max_incr / 100.0) * self.dac
        return val, 100.0 * math.fabs(val - self.wf[i]) / float(self.dac), True

    def _put_sample(self, i, val):
        epics.caput(self.prefix + ":_SetSample" + str(i) + "_do", val)

    def _write_point_by_point(self, points, zero_to_end, progress, cancel):
        if len(points) != self.pulse_size:
            raise ValueError(
                "Size of AWG trace is %d. Expecting %d" % (len(points), self.pulse_size)
            )

        expected = np.array(self.wf, dtype=float, copy=True)
        written = []  # (sample, previous value) so a stop can put them back
        limited = 0
        prog_length = len(points) if not zero_to_end else len(self.wf)
        progress.start("Writing to AWG", "Writing sample 1", prog_length)
        try:
            for i, point in enumerate(points):
                val = int(point * self.dac)
                if val > self.dac:
                    continue
                if cancel():
                    self._restore(written, progress)
                    raise WriteCancelled(
                        "AWG write stopped after %d of %d samples; previous trace restored"
                        % (i, len(points))
                    )
                val, incr, was_limited = self._limited_value(i, val)
                limited += was_limited
                log.info(
                    "Modifying point %d from %d to %d : %.1f percent of DAC",
                    i,
                    self.wf[i],
                    val,
                    incr,
                )
                self._put_sample(i, val)
                written.append((i, self.wf[i]))
                expected[i] = val
                progress.update(i, "Writing sample %d" % i)
                time.sleep(self.wait_time)

            # If requested, zero anything outside the current range of pulse shaping algorithm
            # Not concerned about changed > max % change here as we're going to zero.
            if zero_to_end:
                for i in range(len(points), len(self.wf)):
                    progress.update(i, "Writing sample %d" % i)
                    if self.wf[i] != 0:
                        if cancel():
                            self._restore(written, progress)
                            raise WriteCancelled(
                                "AWG write stopped while zeroing; previous trace restored"
                            )
                        log.info("Setting point %d to zero", i)
                        self._put_sample(i, 0)
                        written.append((i, self.wf[i]))
                        expected[i] = 0
                        time.sleep(self.wait_time)
        finally:
            progress.finish()
        if limited:
            log.warning(
                "%d sample(s) were limited to a change of %.1f%% of the DAC", limited, self.max_incr
            )
        return np.floor(expected)

    def _restore(self, written, progress):
        """Put back the samples already written, newest first."""
        progress.start("Stopping", "Restoring the previous AWG trace", len(written))
        for n, (i, old) in enumerate(reversed(written), start=1):
            self._put_sample(i, old)
            progress.update(n, "Restoring sample %d" % i)
            time.sleep(self.wait_time)
        log.warning(
            "AWG write stopped; restored %d sample(s) to their previous values", len(written)
        )
