"""The closed feedback loop: measure the pulse, compute a new AWG trace, apply it, repeat.

LoopEngine knows nothing about any GUI. The GUI supplies callbacks to approve each
step, to request a stop, and to redraw; it also supplies a Progress for slow hardware.
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from beam_shaper.core import correction as corr
from beam_shaper.core.interfaces import (
    AwgWriteError,
    FeedbackError,
    NullProgress,
    WriteCancelled,
    never_cancel,
)

log = logging.getLogger(__name__)
# Full detail for the log file (e.g. every trace written); the GUI log panel leaves it out
audit_log = logging.getLogger("beam_shaper.audit")


class AlgorithmError(Exception):
    """The user's correction algorithm failed or returned unusable values."""


class Decision(Enum):
    APPLY = 1
    RECALC = 2
    PAUSE = 3
    ABORT = 4


class Outcome(Enum):
    COMPLETED = 1  # Hit max iterations or tolerance
    ABORTED = 2
    PAUSED = 3
    STOPPED = 4
    UNSAFE = 5
    FEEDBACK_ERROR = 6
    WRITE_ERROR = 7
    ALGORITHM_ERROR = 8


@dataclass
class LoopResult:
    outcome: Outcome
    message: str

    @property
    def is_error(self):
        return self.outcome in (
            Outcome.UNSAFE,
            Outcome.FEEDBACK_ERROR,
            Outcome.WRITE_ERROR,
            Outcome.ALGORITHM_ERROR,
        )


@dataclass
class LoopParameters:
    """Everything that controls the maths of the loop."""

    gain: float
    iterations: int
    tolerance: float
    max_percent_change: float
    auto_loop: bool
    pulse_peak_power: float
    noise_threshold_percentage: float
    awg_zero_shift: float

    @classmethod
    def from_settings(cls, config, settings):
        """Combine the app config (AppConfig) with the user's run settings (LoopSettings)."""
        return cls(
            gain=settings.gain,
            iterations=settings.iterations,
            tolerance=settings.tolerance,
            max_percent_change=settings.max_percent_change,
            auto_loop=config.auto_loop,
            pulse_peak_power=config.pulse_peak_power,
            noise_threshold_percentage=config.noise_threshold_percentage,
            awg_zero_shift=config.awg_zero_shift,
        )


@dataclass(frozen=True)
class LoopSnapshot:
    """A copy of the loop state, safe to hand to another thread for display."""

    i: int
    gain: float
    rms: float
    peak_power: float
    target: np.ndarray
    current: np.ndarray
    correction: np.ndarray
    awg_now: np.ndarray
    awg_next: object  # np.ndarray, or None before the first calculation
    rms_history: tuple = ()  # RMS after each measurement, starting with the first


def _copy(array):
    return None if array is None else np.array(array, copy=True)


def _check_trace(values, n, what):
    """Return values as a float array, or raise ValueError saying what is wrong with it."""
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        raise ValueError(
            "{0} returned {1!r}, not an array of numbers".format(what, type(values))
        ) from None
    if array.shape != (n,):
        raise ValueError(
            "{0} returned {1} values; expected {2}".format(what, array.size if array.ndim else 1, n)
        )
    bad = np.count_nonzero(~np.isfinite(array))
    if bad:
        raise ValueError("{0} returned NaN or infinite values at {1} point(s)".format(what, bad))
    return array


class LoopEngine:
    def __init__(
        self,
        target,
        params,
        awg,
        feedback,
        correction_fn=corr.default_correction,
        filter_fn=corr.no_filter,
        diagnostics=None,
        background_raw=None,
        progress=None,
        on_warning=None,
    ):
        """
        target: target shape, one value per AWG point. Raises ValueError if it has no signal.
        awg, feedback: hardware (see beam_shaper.core.interfaces)
        diagnostics: a DiagnosticWriter, or None to not save files
        on_warning: called with (message, caption) for non-fatal problems
        """
        target = np.asarray(target, dtype=float)
        if target.size == 0 or not np.all(np.isfinite(target)) or np.max(target) <= 0:
            raise ValueError("The target shape is empty, all zero or contains invalid values")
        self.target = target / np.max(target)
        self.params = params
        self.gain = params.gain
        self.awg = awg
        self.feedback = feedback
        self.correction_fn = correction_fn
        self.filter_fn = filter_fn
        self.diagnostics = diagnostics
        self.background_raw = background_raw
        self.progress = progress or NullProgress()
        self.on_warning = on_warning or (lambda message, caption: None)

        self.num_points = len(self.target)
        self.i = 0  # Loop count, kept so a paused loop can be restarted
        self.current_output = None
        self.awg_now = None
        self.correction_factor = np.zeros(self.num_points)
        self.awg_next_norm = None
        self.rms_history = []

    # ------------------------------------------------------------------ state

    def rms_error(self):
        return corr.rms_error(self.target, self.current_output)

    def peak_power(self):
        return corr.peak_power(self.awg_next_norm)

    def is_safe(self):
        return self.peak_power() <= self.params.pulse_peak_power

    def snapshot(self):
        return LoopSnapshot(
            i=self.i,
            gain=self.gain,
            rms=self.rms_error(),
            peak_power=self.peak_power(),
            target=_copy(self.target),
            current=_copy(self.current_output),
            correction=_copy(self.correction_factor),
            awg_now=_copy(self.awg_now),
            awg_next=_copy(self.awg_next_norm),
            rms_history=tuple(self.rms_history),
        )

    def limits_reached(self):
        return not (self.i < self.params.iterations and self.rms_error() >= self.params.tolerance)

    def should_continue(self):
        # When not auto looping, loop until the user pauses or aborts
        return (not self.params.auto_loop) or not self.limits_reached()

    # ------------------------------------------------------------------ steps

    def start(self):
        """Take the first measurement. Raises FeedbackError."""
        log.info("Loop started: %s", self.params)
        self._measure()
        self.awg_now = self._read_awg()

    def calculate(self):
        """Work out the next AWG trace from the latest measurement, without applying it.

        Raises AlgorithmError if the correction algorithm fails or returns bad values."""
        self.awg_now = self._read_awg()
        try:
            correction = self.correction_fn(self.target, self.current_output, self.gain)
            correction = _check_trace(correction, self.num_points, "The correction algorithm")
        except ValueError as e:
            raise AlgorithmError(str(e)) from e
        except Exception as e:
            raise AlgorithmError("Error in the correction algorithm: {0}".format(e)) from e
        self.correction_factor = corr.limit_correction(correction, self.params.max_percent_change)
        awg_next = corr.next_awg_trace(
            self.awg_now,
            self.correction_factor,
            self.target,
            self.current_output,
            first_iteration=self.i == 0,
            noise_threshold_percentage=self.params.noise_threshold_percentage,
            awg_zero_shift=self.params.awg_zero_shift,
        )
        try:
            awg_next = _check_trace(self.filter_fn(awg_next), self.num_points, "The filter")
        except Exception as e:
            log.exception("Error when applying user-defined filter")
            self.on_warning(
                "Error when applying user-defined filter:\n{0}\n\nIgnoring filter".format(e),
                "Filter error",
            )
            # Remove filter to avoid error message every loop
            self.filter_fn = corr.no_filter
        self.awg_next_norm = corr.normalise(awg_next)

    def save_diagnostics(self):
        if self.diagnostics is None:
            return
        self.diagnostics.save_iteration(
            self.i,
            self.gain,
            self.target,
            self.background_raw,
            self.awg_now,
            self.correction_factor,
            self.current_output,
        )

    def apply(self, cancel=never_cancel):
        """Write the calculated trace to the AWG and measure the result.

        Raises RuntimeError if the trace is unsafe, WriteCancelled if cancel() became true
        during the write, AwgWriteError if the AWG readback is wrong, FeedbackError if
        measuring fails."""
        if not self.is_safe():
            raise RuntimeError("Proposed AWG trace would exceed peak power")
        log.info(
            "Writing iteration %i to AWG: gain %.2f, RMS %.4f, peak power %.2f",
            self.i + 1,
            self.gain,
            self.rms_error(),
            self.peak_power(),
        )
        audit_log.info(
            "Iteration %i AWG trace: %s",
            self.i + 1,
            np.array2string(self.awg_next_norm, precision=4, max_line_width=10**6),
        )
        # On the first pass only, set any AWG samples outside the pulse to zero
        self.awg.write(
            self.awg_next_norm, zero_to_end=self.i == 0, progress=self.progress, cancel=cancel
        )
        log.info("Applied correction for iteration %i", self.i + 1)
        self.i += 1
        self._measure()

    def _measure(self):
        self.current_output = self.feedback.measure(self.progress)
        self.rms_history.append(self.rms_error())

    def _read_awg(self):
        # Extract the number of points used for this pulse
        return self.awg.read_normalised_shape()[: self.num_points]

    # ------------------------------------------------------------------ loop

    def run(self, approve, should_stop=lambda: False, on_update=lambda engine: None):
        """
        Run iterations until a limit is reached or the user intervenes.

        approve(engine) -> (Decision, gain): asked before every write to the AWG.
            RECALC recalculates with the returned gain and asks again.
        should_stop() -> bool: polled before and during writing, e.g. for a Stop button.
        on_update(engine): called whenever there is new data to show.
        """
        try:
            return self._run(approve, should_stop, on_update)
        except AlgorithmError as e:
            return self._finish(Outcome.ALGORITHM_ERROR, "Quitting loop: {0}".format(e))

    def _run(self, approve, should_stop, on_update):
        while self.should_continue():
            self.calculate()
            on_update(self)
            decision, gain = approve(self)
            while decision is Decision.RECALC:
                self.gain = gain
                self.calculate()
                on_update(self)
                decision, gain = approve(self)
            self.gain = gain

            if decision is Decision.ABORT:
                return self._finish(Outcome.ABORTED, "Quitting loop. AWG curve will not be applied")
            if decision is Decision.PAUSE:
                return self._finish(Outcome.PAUSED, "Loop paused")

            self.save_diagnostics()

            # If the next AWG trace would be unsafe, don't apply it and quit
            if not self.is_safe():
                return self._finish(
                    Outcome.UNSAFE, "Quitting loop: proposed curve would exceed peak power"
                )
            if should_stop():
                return self._finish(Outcome.STOPPED, "Quitting loop: user stop")

            try:
                self.apply(cancel=should_stop)
            except WriteCancelled as e:
                return self._finish(Outcome.STOPPED, "Quitting loop: {0}".format(e))
            except AwgWriteError as e:
                return self._finish(
                    Outcome.WRITE_ERROR, "Quitting loop: AWG write failed\n\n{0}".format(e)
                )
            except FeedbackError as e:
                return self._finish(
                    Outcome.FEEDBACK_ERROR,
                    "Quitting loop: couldn't update feedback curve\n\n{0}".format(e),
                )
        return self._finish(Outcome.COMPLETED, "Loop ended")

    def _finish(self, outcome, message):
        if outcome in (Outcome.COMPLETED, Outcome.PAUSED, Outcome.ABORTED):
            log.info(message)
        else:
            log.warning(message)
        return LoopResult(outcome, message)
