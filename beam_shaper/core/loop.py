"""The closed feedback loop: measure the pulse, compute a new AWG trace, apply it, repeat.

LoopEngine knows nothing about any GUI. The GUI supplies callbacks to approve each
step, to request a stop, and to redraw; it also supplies a Progress for slow hardware.
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from beam_shaper.core import correction as corr
from beam_shaper.core.interfaces import FeedbackError, NullProgress

log = logging.getLogger(__name__)


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


@dataclass
class LoopResult:
    outcome: Outcome
    message: str

    @property
    def is_error(self):
        return self.outcome in (Outcome.UNSAFE, Outcome.FEEDBACK_ERROR)


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
        target: normalised target shape, one value per AWG point
        awg, feedback: hardware (see beam_shaper.core.interfaces)
        diagnostics: a DiagnosticWriter, or None to not save files
        on_warning: called with (message, caption) for non-fatal problems
        """
        self.target = np.asarray(target) / np.max(target)
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

    # ------------------------------------------------------------------ state

    def rms_error(self):
        return corr.rms_error(self.target, self.current_output)

    def peak_power(self):
        return corr.peak_power(self.awg_next_norm)

    def is_safe(self):
        return self.peak_power() <= self.params.pulse_peak_power

    def limits_reached(self):
        return not (self.i < self.params.iterations and self.rms_error() >= self.params.tolerance)

    def should_continue(self):
        # When not auto looping, loop until the user pauses or aborts
        return (not self.params.auto_loop) or not self.limits_reached()

    # ------------------------------------------------------------------ steps

    def start(self):
        """Take the first measurement. Raises FeedbackError."""
        self.current_output = self.feedback.measure(self.progress)
        self.awg_now = self._read_awg()

    def calculate(self):
        """Work out the next AWG trace from the latest measurement, without applying it."""
        self.awg_now = self._read_awg()
        correction = self.correction_fn(self.target, self.current_output, self.gain)
        self.correction_factor = corr.limit_correction(
            correction, self.params.max_percent_change
        )
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
            awg_next = self.filter_fn(awg_next)
        except Exception:
            log.exception("Error when applying user-defined filter")
            self.on_warning("Error when applying user-defined filter\n Ignoring filter", "Filter error")
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

    def apply(self):
        """Write the calculated trace to the AWG and measure the result.

        Raises RuntimeError if the trace is unsafe, FeedbackError if measuring fails."""
        if not self.is_safe():
            raise RuntimeError("Proposed AWG trace would exceed peak power")
        # On the first pass only, set any AWG samples outside the pulse to zero
        self.awg.write(self.awg_next_norm, zero_to_end=self.i == 0, progress=self.progress)
        log.info("Applied correction for iteration %i", self.i + 1)
        self.current_output = self.feedback.measure(self.progress)
        self.i += 1

    def _read_awg(self):
        # Extract the number of points used for this pulse
        return self.awg.read_normalised_shape()[: self.num_points]

    # ------------------------------------------------------------------ loop

    def run(self, approve, should_stop=lambda: False, on_update=lambda engine: None):
        """
        Run iterations until a limit is reached or the user intervenes.

        approve(engine) -> (Decision, gain): asked before every write to the AWG.
            RECALC recalculates with the returned gain and asks again.
        should_stop() -> bool: polled before writing, e.g. for a Stop button.
        on_update(engine): called whenever there is new data to show.
        """
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
                self.apply()
            except FeedbackError as e:
                return self._finish(
                    Outcome.FEEDBACK_ERROR,
                    "Quitting loop: couldn't update feedback curve\n\n{0}".format(e),
                )
        return self._finish(Outcome.COMPLETED, "Loop ended")

    def _finish(self, outcome, message):
        log.info(message)
        return LoopResult(outcome, message)
