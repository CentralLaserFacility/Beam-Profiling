"""The EPICS drivers against a fake IOC (tests/fake_ioc.py) on localhost."""

import logging

import epics
import numpy as np
import pytest

from beam_shaper.core.config import AppConfig
from beam_shaper.core.curve import BkgCurve, load_target
from beam_shaper.core.interfaces import AwgWriteError, FeedbackError, NullProgress, WriteCancelled
from beam_shaper.core.loop import Decision, Outcome
from beam_shaper.core.settings import LoopSettings
from beam_shaper.hardware.epics_awg import EpicsAwg
from beam_shaper.hardware.epics_scope import EpicsFeedback
from beam_shaper.session import build_engine
from tests.test_session_state import REPO

N = 82


@pytest.fixture(autouse=True)
def fast_awg(monkeypatch):
    monkeypatch.setattr(EpicsAwg, "READ_SETTLE_TIME", 0.2)
    monkeypatch.setattr(EpicsAwg, "BUFFER_CLEAR_TIME", 0)


@pytest.fixture
def ioc(fake_ioc):
    """The fake IOC, reset to its initial AWG trace with no faults."""
    assert epics.caput("FAKE:Reset", 1, wait=True)
    return fake_ioc


def make_awg(ioc, method="pts", max_change=100, wait=0.0):
    return EpicsAwg(ioc["prefix"], N, max_change, method, wait)


def counting_cancel(after):
    """A cancel() that becomes true after it has been asked `after` times."""
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > after

    return cancel


@pytest.mark.parametrize("method", ["pts", "wfm"])
def test_write_is_verified(ioc, method):
    awg = make_awg(ioc, method)
    awg.read_normalised_shape()
    trace = np.linspace(0.2, 1.0, N)
    awg.write(trace, zero_to_end=True, progress=NullProgress())

    raw = awg.read_raw_shape()
    np.testing.assert_allclose(raw[:N], trace * ioc["dac"], atol=1.01)
    assert np.all(raw[N:] == 0)


def test_large_changes_are_limited_and_reported(ioc, caplog):
    awg = make_awg(ioc, max_change=5)
    before = awg.read_raw_shape().copy()
    with caplog.at_level(logging.WARNING):
        awg.write(np.ones(N), zero_to_end=False, progress=NullProgress())
    after = awg.read_raw_shape()
    # Each sample may only move by 5% of the DAC
    assert np.all(after[:N] - before[:N] <= 0.05 * ioc["dac"] + 1)
    assert "limited to a change of 5.0%" in caplog.text


@pytest.mark.parametrize("method", ["pts", "wfm"])
def test_stuck_sample_is_detected(ioc, method):
    epics.caput("FAKE:StuckSample", 10, wait=True)
    awg = make_awg(ioc, method)
    awg.read_normalised_shape()
    with pytest.raises(AwgWriteError, match="sample 10"):
        awg.write(np.linspace(0.2, 1.0, N), zero_to_end=False, progress=NullProgress())


def test_stop_part_way_restores_previous_trace(ioc):
    awg = make_awg(ioc)
    before = awg.read_raw_shape().copy()
    with pytest.raises(WriteCancelled, match="restored"):
        awg.write(
            np.linspace(0.2, 1.0, N),
            zero_to_end=True,
            progress=NullProgress(),
            cancel=counting_cancel(after=30),
        )
    np.testing.assert_array_equal(awg.read_raw_shape(), before)


def test_waveform_stop_before_sending_leaves_awg_unchanged(ioc):
    awg = make_awg(ioc, "wfm")
    before = awg.read_raw_shape().copy()
    with pytest.raises(WriteCancelled, match="unchanged"):
        awg.write(
            np.linspace(0.2, 1.0, N),
            zero_to_end=False,
            progress=NullProgress(),
            cancel=counting_cancel(after=30),
        )
    np.testing.assert_array_equal(awg.read_raw_shape(), before)


def make_feedback(ioc):
    scope = epics.PV(ioc["scope"])
    resolution = epics.PV(ioc["resolution_pv"])
    assert scope.wait_for_connection(5) and resolution.wait_for_connection(5)
    background = BkgCurve(curve_array=np.full(1000, 0.01))
    crop = (ioc["slice_start"], ioc["slice_len"])
    return EpicsFeedback(scope, resolution, background, crop, N, averages=2, wait=0)


def test_feedback_measures_the_awg_shape(ioc):
    awg = make_awg(ioc)
    awg.read_normalised_shape()
    trace = np.linspace(0.2, 1.0, N)
    awg.write(trace, zero_to_end=False, progress=NullProgress())

    shape = make_feedback(ioc).measure(NullProgress())
    expected = trace**1.5  # the fake laser's non-linearity
    np.testing.assert_allclose(shape, expected / expected.max(), atol=0.01)


def test_feedback_stops_if_scope_resolution_changes(ioc):
    feedback = make_feedback(ioc)
    try:
        epics.caput(ioc["resolution_pv"], 5e-11, wait=True)
        with pytest.raises(FeedbackError, match="resolution"):
            feedback.measure(NullProgress())
    finally:
        epics.caput(ioc["resolution_pv"], ioc["resolution"], wait=True)


def hardware_engine(ioc, tmp_path, iterations=5, awg_wait=0.0):
    config = AppConfig(
        sim=False,
        awg_prefix=ioc["prefix"],
        awg_wait=awg_wait,
        scope_wait=0,
        curve=str(REPO / "curve_library"),
        filter=str(REPO / "user_filter.py"),
        algorithm=str(REPO / "user_algorithm.py"),
        diag=str(tmp_path / "diag"),
    )
    settings = LoopSettings(
        gain=0.5,
        iterations=iterations,
        tolerance=0.001,
        max_percent_change=25,
        pulse_length=10.25,
        slice_start=ioc["slice_start"],
        slice_length=ioc["slice_len"],
        averages=1,
        save_diag_files=True,
    )
    feedback = make_feedback(ioc)
    target = load_target(str(REPO / "curve_library" / "linExp.curve"), N)
    engine, warnings = build_engine(
        config,
        settings,
        target,
        feedback.background,
        feedback.scope_pv,
        feedback.time_resolution_pv,
    )
    assert warnings == []
    return engine


def test_loop_converges_on_fake_hardware(ioc, tmp_path):
    engine = hardware_engine(ioc, tmp_path)
    engine.start()
    result = engine.run(lambda e: (Decision.APPLY, e.gain))

    assert result.outcome is Outcome.COMPLETED
    assert engine.i == 5
    history = engine.rms_history
    assert len(history) == 6 and history[-1] < history[0] / 2
    run_folders = list((tmp_path / "diag").iterdir())
    assert len(run_folders) == 1 and (run_folders[0] / "run.json").exists()


def test_gui_loop_uses_channel_access_from_worker_thread(ioc, tmp_path, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from beam_shaper.ui.loop_window import LoopWindow

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a: None))
    engine = hardware_engine(ioc, tmp_path, iterations=2)
    window = LoopWindow(engine, True, 0, 0.125, sim=False)
    window.show()
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.last_result is not None, timeout=60000)
    assert window.last_result.outcome is Outcome.COMPLETED
    assert engine.i == 2
    window.close()


def test_gui_stop_during_write_restores_awg(ioc, tmp_path, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from beam_shaper.ui.loop_window import LoopWindow

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a: None))
    # A slow point-by-point write, so there is time to press Stop part way through
    engine = hardware_engine(ioc, tmp_path, iterations=3, awg_wait=0.05)
    window = LoopWindow(engine, True, 0, 0.125, sim=False)
    window.show()
    qtbot.addWidget(window)
    qtbot.waitUntil(
        lambda: window.progress_bar.isVisible() and window.progress_bar.value() > 10, timeout=30000
    )
    before = engine.awg_now.copy()

    window.stop_button.click()
    qtbot.waitUntil(lambda: window.last_result is not None, timeout=60000)
    assert window.last_result.outcome is Outcome.STOPPED
    assert "restored" in window.last_result.message
    assert engine.i == 0
    np.testing.assert_allclose(engine.awg.read_normalised_shape()[:N], before, atol=1.5 / 4095)
    window.close()
