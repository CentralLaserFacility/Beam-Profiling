"""The refactored code must reproduce what the legacy code did (see golden/generate_legacy.py)."""

from pathlib import Path

import numpy as np
import pytest

from beam_shaper.core.correction import default_correction, no_filter
from beam_shaper.core.curve import BkgCurve, Curve, TargetCurve
from beam_shaper.core.loop import LoopEngine, LoopParameters, Decision, Outcome
from beam_shaper.core.plugins import load_awg_filter
from beam_shaper.hardware.sim import SimAwg, SimFeedback, simulated_start_shape

REPO = Path(__file__).resolve().parents[1]
GOLDEN = np.load(Path(__file__).parent / "golden" / "legacy_00d7a0f.npz")


@pytest.fixture(scope="module")
def gaussian_filter():
    filt, err = load_awg_filter(str(REPO / "user_filter.py"))
    assert err is None
    return filt


def params(**overrides):
    values = dict(
        gain=0.3,
        iterations=10,
        tolerance=0.01,
        max_percent_change=25,
        auto_loop=True,
        pulse_peak_power=20.0,
        noise_threshold_percentage=3.0,
        awg_zero_shift=0.1,
    )
    values.update(overrides)
    return LoopParameters(**values)


class FixedAwg:
    def __init__(self, shape):
        self.shape = shape

    def read_normalised_shape(self):
        return self.shape.copy()


def test_scope_trace_processing():
    bkg = BkgCurve(curve_array=GOLDEN["A_bkg_raw"])
    c = Curve(curve_array=GOLDEN["A_trace_raw"])
    c.process(clip=True, norm=True, bkg=bkg, crop=(273, 410), resample=82)
    np.testing.assert_allclose(c.get_processed(), GOLDEN["A_processed"])


def test_library_target_loading():
    t = TargetCurve()
    t.load(str(REPO / "curve_library" / "linExp.curve"), num_points=82, trim_method="resample")
    t.process(clip=True, norm=True, resample=82)
    np.testing.assert_allclose(t.get_processed(), GOLDEN["A_target_linExp_82"])


@pytest.mark.parametrize("label", ["gauss", "nofilt"])
@pytest.mark.parametrize("i", [0, 3])
def test_single_correction_step(label, i, gaussian_filter):
    engine = LoopEngine(
        GOLDEN["B_target"],
        params(gain=0.3),
        awg=FixedAwg(GOLDEN["B_awg_now"]),
        feedback=None,
        filter_fn=gaussian_filter if label == "gauss" else no_filter,
    )
    engine.current_output = GOLDEN["B_current"].copy()
    engine.i = i
    engine.calculate()
    np.testing.assert_allclose(engine.correction_factor, GOLDEN[f"B_{label}_i{i}_correction"])
    np.testing.assert_allclose(engine.awg_next_norm, GOLDEN[f"B_{label}_i{i}_awg_next"])


def test_simulated_auto_loop(gaussian_filter):
    background = BkgCurve(curve_array=GOLDEN["A_bkg_raw"])
    start = simulated_start_shape(background, crop=(273, 410), num_points=82)
    np.testing.assert_allclose(start, GOLDEN["C_start"])

    awg = SimAwg(start, write_time=0)
    engine = LoopEngine(
        GOLDEN["B_target"],
        params(gain=0.5, iterations=6),
        awg=awg,
        feedback=SimFeedback(awg),
        correction_fn=default_correction,
        filter_fn=gaussian_filter,
    )
    engine.start()
    corrections, awg_next = [], []

    def record(e):
        corrections.append(e.correction_factor.copy())
        awg_next.append(e.awg_next_norm.copy())

    result = engine.run(approve=lambda e: (Decision.APPLY, e.gain), on_update=record)

    assert result.outcome is Outcome.COMPLETED
    assert engine.i == GOLDEN["C_final_i"]
    np.testing.assert_allclose(np.array(corrections), GOLDEN["C_corrections"])
    np.testing.assert_allclose(np.array(awg_next), GOLDEN["C_awg_next"])
    np.testing.assert_allclose(engine.current_output, GOLDEN["C_final_output"])
    assert engine.rms_error() == pytest.approx(float(GOLDEN["C_final_rms"]))
