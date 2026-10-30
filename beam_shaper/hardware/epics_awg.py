import logging
import math
import time

import epics
import numpy as np

log = logging.getLogger(__name__)

WRITE_METHODS = ("pts", "wfm")


class EpicsAwg:
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
        time.sleep(2)
        self.wf = epics.caget(self.prefix + ":ReadWaveform_ascii_do")
        self.dac = epics.caget(self.prefix + ":DAC")
        self.wf = np.clip(self.wf, 0, self.dac)
        self.nwf = self.wf / float(self.dac)

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

    def write(self, points, zero_to_end, progress):
        # The shape must have been read first: writes are checked against it
        if not hasattr(self, "wf"):
            self._read_current_shape()
        self.pause_scanning()  # Stop IDIL/AWG comms while writing curve
        try:
            time.sleep(1)  # Let the message buffer clear
            if self.write_method == "pts":
                self._write_point_by_point(points, zero_to_end, progress)
            else:
                self._write_waveform(points, progress)
        finally:
            self.resume_scanning()  # Restart the comms now finished writing

    def _write_waveform(self, points, progress):
        data = np.zeros(len(self.wf))
        data[0 : len(points)] = points

        progress.start("Sending waveform", "Buffering values")
        try:
            # Send each of the points to the correct record
            pv_prefix = self.prefix + ":HoldSampleNorm"
            for i in range(0, len(data)):
                epics.caput(pv_prefix + str(i), data[i])
            time.sleep(1)

            progress.update(None, "Writing waveform to AWG")
            # Write the whole waveform to the AWG
            epics.caput(self.prefix + ":SetWaveform.PROC", 1)

            # Wait for the IOC to send not busy before continuing
            while epics.caget(self.prefix + ":SetWaveformBusy"):
                progress.update(None, "Waiting for AWG response")
                time.sleep(0.2)
        finally:
            progress.finish()

    def _modify_point(self, i, val):
        incr = 100.0 * math.fabs(val - self.wf[i]) / float(self.dac)

        if incr >= self.max_incr:
            log.error(
                "Error: increment too big: %.1f percent of DAC - max is %.1f", incr, self.max_incr
            )
            if val - self.wf[i] < 0:
                val = self.wf[i] - (self.max_incr / 100.0) * self.dac
            else:
                val = self.wf[i] + (self.max_incr / 100.0) * self.dac
            incr = 100.0 * math.fabs(val - self.wf[i]) / float(self.dac)

        log.info(
            "Modifying point %d from %d to %d : %.1f percent of DAC", i, self.wf[i], val, incr
        )
        epics.caput(self.prefix + ":_SetSample" + str(i) + "_do", val)

    def _write_point_by_point(self, points, zero_to_end, progress):
        if len(points) != self.pulse_size:
            raise ValueError(
                "Size of AWG trace is %d. Expecting %d" % (len(points), self.pulse_size)
            )

        prog_length = len(points) if not zero_to_end else len(self.wf)
        progress.start("Writing to AWG", "Writing sample 1", prog_length)
        try:
            for i, point in enumerate(points):
                val = int(point * self.dac)
                if val > self.dac:
                    continue
                self._modify_point(i, val)
                progress.update(i, "Writing sample %d" % i)
                time.sleep(self.wait_time)

            # If requested, zero anything outside the current range of pulse shaping algorithm
            # Not concerned about changed > max % change here as we're going to zero.
            if zero_to_end:
                for i in range(len(points), len(self.wf)):
                    progress.update(i, "Writing sample %d" % i)
                    if self.wf[i] != 0:
                        log.info("Setting point %d to zero", i)
                        epics.caput(self.prefix + ":_SetSample" + str(i) + "_do", 0)
                        time.sleep(self.wait_time)
        finally:
            progress.finish()
