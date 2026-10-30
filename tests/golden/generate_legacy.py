"""Captures behaviour of the legacy wx-coupled code as golden data.

Only runs against a checkout of commit 00d7a0f (before the core/GUI split):
    git worktree add ../bp-legacy 00d7a0f
    python tests/golden/generate_legacy.py ../bp-legacy tests/golden/legacy_00d7a0f.npz
"""
import sys, os
repo = sys.argv[1]
out = sys.argv[2]
sys.path.insert(0, repo)
os.chdir(repo)
import numpy as np
import wx
import loopframe
from loopframe import LoopFrame
from curve import Curve, BkgCurve, TargetCurve
from util import CODES
import user_filter

rng = np.random.default_rng(1234)
g = {}

# --- A: curve processing -------------------------------------------------
n_raw = 1000
bkg_raw = 0.02 * rng.standard_normal(n_raw)
trace_raw = np.zeros(n_raw)
trace_raw[300:650] = np.linspace(0.2, 1.0, 350) ** 2
trace_raw += 0.03 * rng.standard_normal(n_raw)
bkg = BkgCurve(curve_array=bkg_raw.copy())
c = Curve(curve_array=trace_raw.copy())
c.process("clip", "norm", bkg=bkg, crop=(273, 410), resample=82)
g["A_bkg_raw"] = bkg_raw
g["A_trace_raw"] = trace_raw
g["A_processed"] = c.get_processed()

t = TargetCurve()
t.load(num_points=82, trim_method="resample", data="curve_library/linExp.curve")
t.process("clip", "norm", resample=82)
g["A_target_linExp_82"] = t.get_processed()

# --- B: single correction step -------------------------------------------
target = t.get_processed() / np.max(t.get_processed())
current = np.clip(target + 0.1 * rng.standard_normal(82), 0, None)
current[:5] = 0.0
current = current / current.max()
awg_now = np.clip(0.5 + 0.2 * rng.standard_normal(82), 0, 1)
awg_now[10:14] = 0.0
g["B_target"], g["B_current"], g["B_awg_now"] = target, current, awg_now

def default_algorithm(target, current, gain):
    with np.errstate(divide="ignore", invalid="ignore"):
        temp = target / current
    temp[np.isfinite(temp) == False] = 1
    return (temp - 1) * gain + 1

def make_frame(filt):
    f = LoopFrame.__new__(LoopFrame)
    f.awg_filter = filt
    f.calc_correction_factor = default_algorithm
    f.max_percent_change = 25
    f.noise_threshold_percentage = 3.0
    f.awg_zero_shift = 0.1
    f.sim = False
    return f

for label, filt in [("gauss", user_filter.gaussian_filter), ("nofilt", lambda d: d)]:
    for i in (0, 3):
        f = make_frame(filt)
        f.target, f.current_output, f.gain, f.i = target, current.copy(), 0.3, i
        f.get_awg_now = lambda: awg_now.copy()
        f.calculate_parms_for_loop()
        g[f"B_{label}_i{i}_correction"] = f.correction_factor
        g[f"B_{label}_i{i}_awg_next"] = f.awg_next_norm

# --- C: simulated auto loop ----------------------------------------------
loopframe.wx.SafeYield = lambda *a, **k: None
class StubAwg:
    def sim_write(self, parent=None): pass

f = LoopFrame.__new__(LoopFrame)
f.awg_filter = user_filter.gaussian_filter
f.calc_correction_factor = default_algorithm
f.sim = True
f.auto_loop = True
f.awg_zero_shift = 0.1
f.pulse_peak_power = 20.0
f.noise_threshold_percentage = 3.0
f.target = target
f.background = BkgCurve(curve_array=bkg_raw.copy())
f.slice_start, f.slice_length = 273, 410
f.num_points = 82
f.gain = 0.5
f.iterations = 6
f.tolerance = 0.01
f.max_percent_change = 25
f.save_diag_files = False
f.i = 0
f.stop_loop = False
f.parent = None
f.current_output = f.simulate_start_data()
f.correction_factor = np.zeros(82)
f.awg = StubAwg()
f.draw_plots = lambda: None
f.draw_awg_plots = lambda: None
f.check_proceed = lambda: CODES.Proceed
f.show_error = lambda msg, cap: (_ for _ in ()).throw(RuntimeError(msg))
g["C_start"] = f.current_output.copy()
corr, nxt = [], []
orig = f.calculate_parms_for_loop
def wrapped():
    orig()
    corr.append(f.correction_factor.copy()); nxt.append(f.awg_next_norm.copy())
f.calculate_parms_for_loop = wrapped
f.run_loop()
g["C_corrections"] = np.array(corr)
g["C_awg_next"] = np.array(nxt)
g["C_final_output"] = f.current_output
g["C_final_i"] = np.array(f.i)
g["C_final_rms"] = np.array(f.rms_error())
np.savez(out, **g)
print("iterations", f.i, "rms", f.rms_error(), "keys", len(g))
