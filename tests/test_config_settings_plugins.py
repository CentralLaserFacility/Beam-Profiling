import os
import subprocess
import sys
from pathlib import Path

import pytest

from beam_shaper.core import settings
from beam_shaper.core.config import AppConfig
from beam_shaper.core.correction import default_correction, no_filter
from beam_shaper.core.plugins import load_awg_filter, load_correction_algorithm

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- config


def test_repo_config_loads_with_types():
    config = AppConfig.load(str(REPO / "config.ini"))
    assert isinstance(config.auto_loop_wait, int)
    assert isinstance(config.awg_ns_per_point, float)
    assert isinstance(config.sim, bool)


def test_config_round_trip_keeps_unknown_keys(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[extra]\nkeep = me\n\n[timing]\nauto_loop_wait = 7\n")
    config = AppConfig.load(str(path))
    assert config.auto_loop_wait == 7
    config.set_from_string("sim", "False")
    config.set_from_string("auto_loop_wait", "4")
    config.save(str(path))

    reloaded = AppConfig.load(str(path))
    assert reloaded.sim is False
    assert reloaded.auto_loop_wait == 4
    assert "keep = me" in path.read_text()


@pytest.mark.parametrize(
    "name,text", [("auto_loop_wait", "3.5"), ("scope_wait", "abc"), ("awg_write_method", "x")]
)
def test_config_rejects_bad_values(name, text):
    with pytest.raises(ValueError):
        AppConfig().set_from_string(name, text)


# ---------------------------------------------------------------- settings


def test_num_points_and_pulse_length():
    assert settings.num_points(10.25, 0.125) == 82
    assert settings.coerce_pulse_length(10.3, 0.125) == pytest.approx(10.25)
    assert settings.scope_slice_length(10.0, 50e-12) == 200


def test_coercion_limits():
    assert settings.coerce_gain("5") == 1.0
    assert settings.coerce_gain("0") == 0.05
    assert settings.coerce_iterations("1e2") == 100
    assert settings.coerce_iterations("0") == 1
    assert settings.coerce_tolerance("0") == 0.01
    assert settings.coerce_max_percentage_change("500") == 100
    with pytest.raises(ValueError):
        settings.coerce_gain("N/A")


# ---------------------------------------------------------------- plugins


def test_repo_plugins_load():
    algorithm, err = load_correction_algorithm(str(REPO / "user_algorithm.py"))
    assert err is None and callable(algorithm)
    filt, err = load_awg_filter(str(REPO / "user_filter.py"))
    assert err is None and callable(filt)


def test_missing_plugin_falls_back(tmp_path):
    algorithm, err = load_correction_algorithm(str(tmp_path / "nope.py"))
    assert algorithm is default_correction
    assert "Can't find file" in err


@pytest.mark.parametrize("source", ["x = 1\n", "def broken(:\n", "raise RuntimeError('boom')\n"])
def test_broken_plugin_falls_back(tmp_path, source):
    path = tmp_path / "filt.py"
    path.write_text(source)
    filt, err = load_awg_filter(str(path))
    assert filt is no_filter
    assert err


def test_plugin_is_reloaded_after_edit(tmp_path):
    path = tmp_path / "alg.py"
    path.write_text("def calc_correction(t, c, g):\n    return 1\n")
    first, _ = load_correction_algorithm(str(path))
    path.write_text("def calc_correction(t, c, g):\n    return 2\n")
    second, _ = load_correction_algorithm(str(path))
    assert (first(0, 0, 0), second(0, 0, 0)) == (1, 2)


# ---------------------------------------------------------------- layering


def test_core_does_not_import_gui_or_epics():
    code = (
        "import sys, pkgutil, importlib, beam_shaper.core as c\n"
        "for m in pkgutil.iter_modules(c.__path__): importlib.import_module('beam_shaper.core.' + m.name)\n"
        "import beam_shaper.hardware.sim\n"
        "bad = [m for m in ('wx', 'epics', 'matplotlib', 'PySide6') if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == ""


# ---------------------------------------------------------------- startup


def test_epics_configuration(monkeypatch):
    # main.py runs this at startup; it relies on pyepics internals that change between versions
    from beam_shaper.hardware.epics_scope import configure_epics

    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv("EPICS_CA_ADDR_LIST", raising=False)
    monkeypatch.delenv("EPICS_CA_AUTO_ADDR_LIST", raising=False)
    configure_epics("192.168.0.255", "No")

    assert os.environ["EPICS_CA_ADDR_LIST"] == "192.168.0.255"
    assert os.environ["EPICS_CA_AUTO_ADDR_LIST"] == "No"
    assert os.path.isdir(sys.path[-1])
