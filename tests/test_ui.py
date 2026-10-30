"""The Qt GUI, driven in simulation mode with fake scope PVs (no network, no display)."""

import functools
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QMessageBox

import beam_shaper.ui.setup_window as setup_window_module
from beam_shaper.core.config import AppConfig
from beam_shaper.core.loop import Outcome
from beam_shaper.session import build_engine
from beam_shaper.ui.config_dialog import ConfigDialog
from beam_shaper.ui.file_editor import FileEditDialog
from beam_shaper.ui.setup_window import SetupWindow
from beam_shaper.ui.state import SetupState

REPO = Path(__file__).resolve().parents[1]
TIMEOUT = 15000


class FakePV:
    def __init__(self, connected=False, value=None):
        self.connected = connected
        self.value = value
        self.connection_callbacks = []

    def get(self):
        return self.value

    def clear_callbacks(self):
        pass

    def disconnect(self):
        pass


@pytest.fixture
def messages(monkeypatch):
    """Record message boxes instead of blocking on them."""
    shown = []
    for kind in ("critical", "warning"):
        monkeypatch.setattr(
            QMessageBox, kind, staticmethod(lambda parent, caption, text, k=kind: shown.append((k, caption, text)))
        )
    return shown


@pytest.fixture
def make_setup(tmp_path, monkeypatch, qtbot, messages):
    scope = FakePV()
    monkeypatch.setattr(
        setup_window_module, "open_scope_pvs", lambda name, on_conn, on_res: (scope, FakePV())
    )
    # Simulated AWG writes happen instantly
    monkeypatch.setattr(setup_window_module, "build_engine", functools.partial(build_engine, sim_write_time=0))

    background = tmp_path / "bkg.txt"
    np.savetxt(background, 0.01 * np.ones(1000))

    def make(**config_values):
        config = AppConfig(
            sim=True,
            auto_loop=True,
            auto_loop_wait=0,
            scope_wait=0,
            curve=str(REPO / "curve_library"),
            filter=str(REPO / "user_filter.py"),
            algorithm=str(REPO / "user_algorithm.py"),
            diag=str(tmp_path / "diag"),
        )
        for name, value in config_values.items():
            setattr(config, name, value)
        state_file = tmp_path / "state.txt"
        if not state_file.exists():
            SetupState(
                bkg_path=str(background),
                library_index=3,
                slice_start=273,
                slice_length=410,
                pulse_length=10.25,
                gain=0.5,
                iterations=4,
                tolerance=0.01,
                save_files=False,
            ).save(str(state_file))
        window = SetupWindow(config, str(tmp_path / "config.ini"), str(state_file))
        qtbot.addWidget(window)
        window.fake_scope = scope
        window.show()
        return window

    return make


def finish(qtbot, loop_window):
    qtbot.waitUntil(lambda: loop_window.last_result is not None and not loop_window.worker.running, timeout=TIMEOUT)
    return loop_window.last_result


def close_loop(qtbot, setup):
    setup.loop_window.close()
    qtbot.waitUntil(lambda: setup.loop_window is None, timeout=TIMEOUT)


def test_setup_window_restores_and_saves_state(make_setup, tmp_path):
    setup = make_setup()
    assert setup.windowTitle() == "Beam Profiling (simulation)"
    assert setup.library.currentText() == "square"  # restored index, after filling the list
    assert setup.gain.value() == 0.5

    setup.gain.setValue(0.3)
    setup.close()
    assert SetupState.load(str(tmp_path / "state.txt")).gain == 0.3


def test_auto_loop_runs_to_completion(make_setup, qtbot, messages):
    setup = make_setup()
    setup.go_button.click()
    loop = setup.loop_window
    assert loop is not None
    assert not setup.centralWidget().isEnabled()

    result = finish(qtbot, loop)
    assert result.outcome is Outcome.COMPLETED
    assert loop.worker.engine.i == 4
    assert "Iteration: 4" in loop.status_label.text()
    assert len(loop.current_line.getData()[1]) == 82
    assert "Loop ended" in loop.log.toPlainText()
    assert messages == []

    close_loop(qtbot, setup)
    assert setup.centralWidget().isEnabled()


def test_stop_during_countdown_prevents_write(make_setup, qtbot):
    setup = make_setup(auto_loop_wait=30)
    setup.go_button.click()
    loop = setup.loop_window
    qtbot.waitUntil(lambda: loop.cancel_button.isEnabled(), timeout=TIMEOUT)
    before = loop.worker.engine.awg.read_normalised_shape()

    loop.stop_button.click()
    assert finish(qtbot, loop).outcome is Outcome.STOPPED
    assert loop.worker.engine.i == 0
    np.testing.assert_array_equal(loop.worker.engine.awg.read_normalised_shape(), before)
    close_loop(qtbot, setup)


def test_cancel_write_aborts(make_setup, qtbot):
    setup = make_setup(auto_loop_wait=30)
    setup.go_button.click()
    loop = setup.loop_window
    qtbot.waitUntil(lambda: loop.cancel_button.isEnabled(), timeout=TIMEOUT)
    loop.cancel_button.click()
    assert finish(qtbot, loop).outcome is Outcome.ABORTED
    assert loop.worker.engine.i == 0
    close_loop(qtbot, setup)


def test_closing_while_running_stops_safely(make_setup, qtbot):
    setup = make_setup(auto_loop_wait=30)
    setup.go_button.click()
    loop = setup.loop_window
    qtbot.waitUntil(lambda: loop.cancel_button.isEnabled(), timeout=TIMEOUT)
    engine = loop.worker.engine

    loop.close()  # should stop the loop first, then close by itself
    qtbot.waitUntil(lambda: setup.loop_window is None, timeout=TIMEOUT)
    assert engine.i == 0
    assert not loop.worker.thread.isRunning()


def test_closing_setup_window_closes_running_loop(make_setup, qtbot):
    setup = make_setup(auto_loop_wait=30)
    setup.go_button.click()
    qtbot.waitUntil(lambda: setup.loop_window.cancel_button.isEnabled(), timeout=TIMEOUT)
    setup.close()
    qtbot.waitUntil(lambda: not setup.isVisible(), timeout=TIMEOUT)
    assert setup.loop_window is None


def test_manual_loop_apply_replot_pause_continue(make_setup, qtbot):
    setup = make_setup(auto_loop=False)
    assert not setup.iterations.isEnabled()
    setup.go_button.click()
    loop = setup.loop_window
    engine = loop.worker.engine

    def wait_for_approval():
        qtbot.waitUntil(lambda: loop.apply_button.isEnabled(), timeout=TIMEOUT)

    wait_for_approval()
    loop.apply_button.click()
    wait_for_approval()
    assert engine.i == 1

    loop.gain_spin.setValue(0.2)
    loop.replot_button.click()
    wait_for_approval()
    assert engine.gain == 0.2
    assert engine.i == 1

    loop.pause_button.click()
    assert finish(qtbot, loop).outcome is Outcome.PAUSED
    assert loop.continue_button.isEnabled()

    loop.continue_button.click()
    wait_for_approval()
    loop.apply_button.click()
    wait_for_approval()
    assert engine.i == 2

    # Closing while waiting for approval aborts without writing
    loop.close()
    qtbot.waitUntil(lambda: setup.loop_window is None, timeout=TIMEOUT)
    assert engine.i == 2


def test_go_reports_missing_background(make_setup, messages):
    setup = make_setup()
    setup.bkg_path.setText("no_such_file.txt")
    setup.go_button.click()
    assert setup.loop_window is None
    assert messages == [("critical", "File error", "Can't load background curve")]


def test_grab_trace_averages_scope(make_setup, qtbot, messages):
    setup = make_setup()
    setup.fake_scope.connected = True
    setup.fake_scope.value = np.arange(10.0)
    setup.averages.setValue(3)
    setup.grab_button.click()
    qtbot.waitUntil(lambda: setup.task is None, timeout=TIMEOUT)
    np.testing.assert_array_equal(setup.scope_curve.get_raw(), np.arange(10.0))
    assert messages == []


def test_grab_trace_reports_disconnected_scope(make_setup, qtbot, messages):
    setup = make_setup()
    setup.grab_button.click()
    qtbot.waitUntil(lambda: setup.task is None, timeout=TIMEOUT)
    assert messages == [("critical", "Scope read error", "Can't connect to scope PV")]


def test_config_dialog_saves_typed_values(tmp_path, qtbot, messages):
    config = AppConfig(diag=str(tmp_path / "diag"))
    path = tmp_path / "config.ini"
    dialog = ConfigDialog(config, str(path))
    qtbot.addWidget(dialog)

    dialog.widgets["auto_loop_wait"].setText("not a number")
    dialog.apply()
    assert messages and messages[0][1] == "Invalid value"
    assert not path.exists()

    dialog.widgets["auto_loop_wait"].setText("7")
    dialog.widgets["sim"].setChecked(False)
    dialog.apply()
    assert config.auto_loop_wait == 7 and config.sim is False
    assert AppConfig.load(str(path)).auto_loop_wait == 7


def test_file_editor_saves(tmp_path, qtbot):
    path = tmp_path / "alg.py"
    path.write_text("x = 1\n")
    dialog = FileEditDialog(str(path))
    qtbot.addWidget(dialog)
    assert dialog.editor.toPlainText() == "x = 1\n"
    dialog.editor.setPlainText("x = 2\n")
    dialog.save()
    assert path.read_text() == "x = 2\n"
