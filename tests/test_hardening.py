"""Safety checks, bug fixes and configuration added on the hardening branch."""

import json
import os
import sys

import numpy as np
import pytest

from beam_shaper import paths
from beam_shaper.core.config import AppConfig
from beam_shaper.core.curve import BkgCurve, Curve, load_target
from beam_shaper.core.diagnostics import DiagnosticWriter
from beam_shaper.core.interfaces import NullProgress, WriteCancelled
from beam_shaper.core.loop import Decision, LoopEngine, LoopParameters, Outcome
from beam_shaper.core.settings import coerce_pulse_length, num_points, scope_slice_length
from beam_shaper.hardware.sim import SimAwg, SimFeedback, simulated_start_shape

N = 20


def make_engine(correction_fn=None, filter_fn=None, on_warning=None, target=None, **overrides):
    values = dict(
        gain=0.5,
        iterations=3,
        tolerance=0.0,
        max_percent_change=25,
        auto_loop=True,
        pulse_peak_power=20.0,
        noise_threshold_percentage=3.0,
        awg_zero_shift=0.1,
    )
    values.update(overrides)
    awg = SimAwg(0.5 * np.ones(N), write_time=0)
    kwargs = {"on_warning": on_warning}
    if correction_fn:
        kwargs["correction_fn"] = correction_fn
    if filter_fn:
        kwargs["filter_fn"] = filter_fn
    target = np.linspace(0.2, 1.0, N) if target is None else target
    engine = LoopEngine(target, LoopParameters(**values), awg, SimFeedback(awg), **kwargs)
    engine.start()
    return engine


def apply_always(engine):
    return Decision.APPLY, engine.gain


# ---------------------------------------------------------------- algorithm checks


@pytest.mark.parametrize(
    "returned, message",
    [
        (np.ones(N - 1), "returned 19 values; expected 20"),
        (np.full(N, np.nan), "NaN or infinite values at 20 point"),
        ("oops", "not an array of numbers"),
    ],
)
def test_bad_algorithm_output_stops_the_loop_before_writing(returned, message):
    engine = make_engine(correction_fn=lambda t, c, g: returned)
    before = engine.awg.read_normalised_shape()
    result = engine.run(apply_always)
    assert result.outcome is Outcome.ALGORITHM_ERROR and result.is_error
    assert message in result.message
    np.testing.assert_array_equal(engine.awg.read_normalised_shape(), before)


def test_algorithm_exception_is_reported():
    def broken(target, current, gain):
        raise KeyError("x")

    result = make_engine(correction_fn=broken).run(apply_always)
    assert result.outcome is Outcome.ALGORITHM_ERROR
    assert "Error in the correction algorithm" in result.message


def test_bad_filter_output_is_ignored_with_a_warning():
    warnings = []
    engine = make_engine(filter_fn=lambda d: d[:-1], on_warning=lambda m, c: warnings.append(m))
    assert engine.run(apply_always).outcome is Outcome.COMPLETED
    assert len(warnings) == 1 and "The filter returned 19 values" in warnings[0]


@pytest.mark.parametrize("target", [np.zeros(N), np.full(N, np.nan), np.array([])])
def test_unusable_target_is_rejected(target):
    with pytest.raises(ValueError, match="target"):
        make_engine(target=target)


def test_all_zero_target_file_is_rejected(tmp_path):
    path = tmp_path / "zero.curve"
    np.savetxt(path, np.zeros(10))
    with pytest.raises(ValueError, match="all zero"):
        load_target(str(path), 82)


# ---------------------------------------------------------------- stopping writes


def test_stop_during_simulated_write_leaves_awg_unchanged():
    engine = make_engine()
    before = engine.awg.read_normalised_shape()
    stops = iter([False] + [True] * 100)  # not before the write, but during it
    result = engine.run(apply_always, should_stop=lambda: next(stops))
    assert result.outcome is Outcome.STOPPED and "unchanged" in result.message
    assert engine.i == 0
    np.testing.assert_array_equal(engine.awg.read_normalised_shape(), before)


def test_sim_awg_write_can_be_cancelled():
    awg = SimAwg(np.ones(5), write_time=0)
    with pytest.raises(WriteCancelled):
        awg.write(np.zeros(5), False, NullProgress(), cancel=lambda: True)
    np.testing.assert_array_equal(awg.read_normalised_shape(), np.ones(5))


def test_rms_history_records_every_measurement():
    engine = make_engine(iterations=3)
    engine.run(apply_always)
    assert len(engine.rms_history) == 4
    assert engine.snapshot().rms_history == tuple(engine.rms_history)
    assert engine.rms_history[-1] < engine.rms_history[0]


# ---------------------------------------------------------------- bug fixes


@pytest.mark.parametrize(
    "length, step, points",
    [(10.25, 0.125, 82), (10.2, 0.1, 102), (0.3, 0.1, 3), (10.3, 0.125, 82)],
)
def test_num_points_is_not_one_short(length, step, points):
    assert num_points(length, step) == points


def test_pulse_length_rounds_down_to_whole_points():
    assert coerce_pulse_length(10.2, 0.1) == pytest.approx(10.2)
    assert coerce_pulse_length(10.3, 0.125) == pytest.approx(10.25)
    assert scope_slice_length(10.25, 2.5e-11) == 410


def test_clip_handles_all_negative_trace():
    c = Curve(curve_array=-np.ones(5))
    c.process(clip=True)
    np.testing.assert_array_equal(c.get_processed(), np.zeros(5))


@pytest.mark.parametrize("length", [200, 1000, 2500])
def test_simulated_start_shape_works_for_any_trace_length(length):
    background = BkgCurve(curve_array=np.zeros(length))
    shape = simulated_start_shape(background, crop=(0, length), num_points=82)
    assert shape.shape == (82,) and shape.max() == pytest.approx(1.0)
    assert shape.min() < 0.1  # the weak sections are present


def test_diagnostics_go_in_a_folder_per_run(tmp_path):
    first = DiagnosticWriter(str(tmp_path), {"settings": {"gain": 0.5}})
    second = DiagnosticWriter(str(tmp_path))
    for writer in (first, second):
        writer.save_iteration(0, 0.5, np.ones(3), np.zeros(3), np.ones(3), np.ones(3), np.ones(3))
    assert first.folder != second.folder  # same start time, separate folders
    files = sorted(os.listdir(first.folder))
    assert "run.json" in files and "i_00000_AWG_shape.txt" in files
    assert json.loads((tmp_path / os.path.basename(first.folder) / "run.json").read_text()) == {
        "settings": {"gain": 0.5}
    }


def test_diagnostics_folder_only_created_when_writing(tmp_path):
    DiagnosticWriter(str(tmp_path))
    assert os.listdir(tmp_path) == []


# ---------------------------------------------------------------- config and paths


def test_local_config_overrides_defaults(tmp_path):
    (tmp_path / "config.ini").write_text("[sim]\nsim = True\n\n[timing]\nauto_loop_wait = 3\n")
    (tmp_path / "config.local.ini").write_text("[sim]\nsim = False\n")
    config = AppConfig.load(tmp_path / "config.ini", tmp_path / "config.local.ini")
    assert config.sim is False and config.auto_loop_wait == 3
    assert config.base_dir == str(tmp_path)


def test_missing_local_config_is_fine(tmp_path):
    (tmp_path / "config.ini").write_text("[timing]\nauto_loop_wait = 4\n")
    config = AppConfig.load(tmp_path / "config.ini", tmp_path / "config.local.ini")
    assert config.auto_loop_wait == 4


def test_relative_locations_resolve_from_config_folder(tmp_path):
    config = AppConfig(diag="./diag_files/", base_dir=str(tmp_path))
    assert config.path("diag") == os.path.normpath(str(tmp_path / "diag_files"))
    config.ensure_diag_folder()
    assert (tmp_path / "diag_files").is_dir()


def test_absolute_locations_are_kept(tmp_path):
    config = AppConfig(curve=str(tmp_path), base_dir="somewhere/else")
    assert config.path("curve") == os.path.normpath(str(tmp_path))


def test_base_dir_is_not_saved_or_shown(tmp_path):
    AppConfig(base_dir=str(tmp_path)).save(str(tmp_path / "out.ini"))
    assert "base_dir" not in (tmp_path / "out.ini").read_text()
    assert "base_dir" not in [o.name for o in AppConfig.options()]


def test_app_dir_is_the_repo_root(monkeypatch, tmp_path):
    assert (paths.app_dir() / "main.py").exists()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "main.exe"))
    assert paths.app_dir() == tmp_path.resolve()


def test_repo_config_has_every_option():
    """config.ini holds a default for every option, so a missing local file is safe."""
    import configparser

    parser = configparser.RawConfigParser()
    parser.read(paths.app_dir() / paths.DEFAULT_CONFIG)
    missing = [
        o.name for o in AppConfig.options() if not parser.has_option(o.metadata["section"], o.name)
    ]
    assert missing == []


# ---------------------------------------------------------------- installation check


def test_check_passes_for_the_repo(capsys):
    from beam_shaper.ui.app import main

    assert main(argv=["--check"]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out and "AWG filter" in out


def test_check_reports_problems(tmp_path):
    from beam_shaper.session import check_installation

    (tmp_path / "user_filter.py").write_text("def awg_filter(d):\n    raise ValueError('bad')\n")
    config = AppConfig(
        curve=str(tmp_path / "no_curves"),
        filter=str(tmp_path / "user_filter.py"),
        algorithm=str(tmp_path / "missing.py"),
        diag=str(tmp_path / "diag"),
    )
    lines = []
    assert check_installation(config, out=lines.append) is False
    failures = [line for line in lines if line.startswith("FAIL")]
    assert len(failures) == 3  # no curves, missing algorithm, failing filter
