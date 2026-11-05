from pathlib import Path

import numpy as np

from beam_shaper.core.config import AppConfig
from beam_shaper.core.curve import BkgCurve, library_curves, load_target
from beam_shaper.core.settings import LoopSettings
from beam_shaper.hardware.sim import SimAwg
from beam_shaper.session import build_engine
from beam_shaper.ui.state import SetupState

REPO = Path(__file__).resolve().parents[1]


def sim_config(tmp_path, **overrides):
    config = AppConfig(
        sim=True,
        curve=str(REPO / "curve_library"),
        filter=str(REPO / "user_filter.py"),
        algorithm=str(REPO / "user_algorithm.py"),
        diag=str(tmp_path / "diag"),
    )
    for name, value in overrides.items():
        setattr(config, name, value)
    return config


def loop_settings(**overrides):
    values = dict(
        gain=0.5,
        iterations=3,
        tolerance=0.01,
        max_percent_change=25,
        pulse_length=10.25,
        slice_start=273,
        slice_length=410,
        averages=1,
        save_diag_files=False,
    )
    values.update(overrides)
    return LoopSettings(**values)


def test_library_lists_curves_sorted():
    assert library_curves(str(REPO / "curve_library")) == [
        "flat_ramp_up",
        "linExp",
        "rampDown",
        "square",
    ]
    assert library_curves(str(REPO / "no_such_folder")) == []


def test_build_engine_in_simulation(tmp_path):
    target = load_target(str(REPO / "curve_library" / "square.curve"), 82)
    background = BkgCurve(curve_array=np.zeros(1000))
    engine, warnings = build_engine(
        sim_config(tmp_path), loop_settings(), target, background, sim_write_time=0
    )
    assert warnings == []
    assert isinstance(engine.awg, SimAwg)
    assert engine.num_points == 82
    assert engine.diagnostics is None


def test_build_engine_reports_broken_plugins(tmp_path):
    config = sim_config(tmp_path, filter=str(tmp_path / "missing.py"))
    target = load_target(str(REPO / "curve_library" / "square.curve"), 82)
    _, warnings = build_engine(
        config, loop_settings(), target, BkgCurve(curve_array=np.zeros(1000)), sim_write_time=0
    )
    assert [caption for _, caption in warnings] == ["Filter error"]


def test_snapshot_is_a_copy(tmp_path):
    target = load_target(str(REPO / "curve_library" / "square.curve"), 82)
    engine, _ = build_engine(
        sim_config(tmp_path), loop_settings(), target, BkgCurve(curve_array=np.zeros(1000)), sim_write_time=0
    )
    engine.start()
    snap = engine.snapshot()
    engine.current_output[:] = -1
    assert snap.current.min() >= 0
    assert snap.awg_next is None


def test_state_round_trip(tmp_path):
    path = tmp_path / "state.txt"
    state = SetupState(bkg_path="b.txt", library_index=2, gain=0.3, target_from_file=True)
    state.save(str(path))
    assert SetupState.load(str(path)) == state


def test_state_reads_old_wx_file_with_placeholders(tmp_path):
    path = tmp_path / "state.txt"
    path.write_text(
        "[Traces]\nbkg_path = x.txt\ntkg_path = \nlib_index = 3\n\n"
        "[Scope]\nscope_pv = A:B\naverages = 2\nstart = 89\nlength = 205\n\n"
        "[Parms]\ntgt_src = 0\npulse_length = 10.25\ngain = 1.0\niterations = N/A\n"
        "tolerance = N/A\nmax_change = 25\nsave_files = 1\n"
    )
    state = SetupState.load(str(path))
    assert (state.bkg_path, state.library_index, state.slice_start) == ("x.txt", 3, 89)
    assert state.iterations == SetupState().iterations  # "N/A" keeps the default
    assert state.save_files is False
    assert state.target_from_file is False


def test_missing_state_file_gives_defaults(tmp_path):
    assert SetupState.load(str(tmp_path / "none.txt")) == SetupState()
