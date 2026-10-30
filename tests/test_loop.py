"""Control flow of LoopEngine.run: approvals, stops and safety."""

import numpy as np
import pytest

from beam_shaper.core.interfaces import FeedbackError
from beam_shaper.core.loop import Decision, LoopEngine, LoopParameters, Outcome
from beam_shaper.hardware.sim import SimAwg, SimFeedback

N = 20


def make_engine(target=None, on_warning=None, filter_fn=None, **overrides):
    values = dict(
        gain=0.5,
        iterations=5,
        tolerance=0.0,
        max_percent_change=25,
        auto_loop=True,
        pulse_peak_power=20.0,
        noise_threshold_percentage=3.0,
        awg_zero_shift=0.1,
    )
    values.update(overrides)
    if target is None:
        target = np.linspace(0.2, 1.0, N)
    awg = SimAwg(0.5 * np.ones(N), write_time=0)
    kwargs = {"on_warning": on_warning}
    if filter_fn is not None:
        kwargs["filter_fn"] = filter_fn
    engine = LoopEngine(target, LoopParameters(**values), awg, SimFeedback(awg), **kwargs)
    engine.start()
    return engine


def apply_always(engine):
    return Decision.APPLY, engine.gain


def test_auto_loop_stops_at_max_iterations():
    engine = make_engine(iterations=3)
    result = engine.run(apply_always)
    assert result.outcome is Outcome.COMPLETED
    assert engine.i == 3


def test_auto_loop_stops_when_within_tolerance():
    engine = make_engine(iterations=100, tolerance=0.05)
    result = engine.run(apply_always)
    assert result.outcome is Outcome.COMPLETED
    assert engine.i < 100
    assert engine.rms_error() < 0.05


def test_abort_does_not_write_to_awg():
    engine = make_engine()
    before = engine.awg.read_normalised_shape()
    result = engine.run(lambda e: (Decision.ABORT, e.gain))
    assert result.outcome is Outcome.ABORTED
    assert engine.i == 0
    np.testing.assert_array_equal(engine.awg.read_normalised_shape(), before)


def test_manual_mode_runs_until_paused_and_can_resume():
    engine = make_engine(auto_loop=False, iterations=1)
    answers = iter([Decision.APPLY, Decision.APPLY, Decision.APPLY, Decision.PAUSE])
    result = engine.run(lambda e: (next(answers), e.gain))
    assert result.outcome is Outcome.PAUSED
    assert engine.i == 3  # iterations limit is ignored in manual mode

    answers = iter([Decision.APPLY, Decision.PAUSE])
    engine.run(lambda e: (next(answers), e.gain))
    assert engine.i == 4


def test_recalc_uses_new_gain_before_applying():
    engine = make_engine(iterations=1)
    gains_seen = []

    def approve(e):
        gains_seen.append(e.gain)
        return (Decision.RECALC, 0.2) if len(gains_seen) == 1 else (Decision.APPLY, e.gain)

    engine.run(approve)
    assert gains_seen == [0.5, 0.2]
    assert engine.gain == 0.2
    assert engine.i == 1


def test_unsafe_trace_is_never_written():
    # A narrow spike in the target means a very high peak power
    target = np.zeros(N)
    target[5] = 1.0
    engine = make_engine(target=target, pulse_peak_power=2.0)
    before = engine.awg.read_normalised_shape()
    result = engine.run(apply_always)
    assert result.outcome is Outcome.UNSAFE
    assert result.is_error
    np.testing.assert_array_equal(engine.awg.read_normalised_shape(), before)
    with pytest.raises(RuntimeError):
        engine.apply()


def test_user_stop_prevents_write():
    engine = make_engine()
    result = engine.run(apply_always, should_stop=lambda: True)
    assert result.outcome is Outcome.STOPPED
    assert engine.i == 0


def test_feedback_failure_ends_loop():
    engine = make_engine()

    class BrokenFeedback:
        def measure(self, progress):
            raise FeedbackError("scope gone")

    engine.feedback = BrokenFeedback()
    result = engine.run(apply_always)
    assert result.outcome is Outcome.FEEDBACK_ERROR
    assert "scope gone" in result.message


def test_broken_filter_warns_once_and_is_dropped():
    warnings = []

    def bad_filter(data):
        raise ZeroDivisionError

    engine = make_engine(on_warning=lambda m, c: warnings.append(c), filter_fn=bad_filter)
    engine.run(apply_always)
    assert warnings == ["Filter error"]
    assert engine.i == 5


def test_progress_is_reported_for_hardware_operations():
    events = []

    class RecordingProgress:
        def start(self, title, message, maximum=None):
            events.append(("start", title))

        def update(self, value, message):
            pass

        def finish(self):
            events.append(("finish",))

    engine = make_engine(iterations=1)
    engine.progress = RecordingProgress()
    engine.run(apply_always)
    assert events == [("start", "Simulated write data"), ("finish",)]
