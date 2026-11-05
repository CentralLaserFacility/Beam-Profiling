"""Simulated hardware for testing without a scope or AWG.

The simulated pulse shape is exactly the AWG trace (a 1 to 1 mapping)."""

import time

import numpy as np

from beam_shaper.core.curve import Curve
from beam_shaper.core.interfaces import WriteCancelled, never_cancel


def simulated_start_shape(background, crop, num_points):
    """A flat pulse with two weak sections, processed like a real scope trace."""
    n = np.size(background.get_raw())
    temp = 0.5 * np.ones(n)
    # Weak sections at the same relative positions for any trace length
    temp[n * 250 // 1000 : n * 350 // 1000] = 0.01
    temp[n * 400 // 1000 : n * 500 // 1000] = 0.03
    sim_curve = Curve(curve_array=temp)
    sim_curve.process(clip=True, norm=True, bkg=background, crop=crop, resample=num_points)
    return sim_curve.get_processed()


class SimAwg:
    def __init__(self, initial_shape, write_time=3.0):
        self.shape = np.asarray(initial_shape, dtype=float).copy()
        self.write_time = write_time

    def read_normalised_shape(self):
        return self.shape.copy()

    def write(self, points, zero_to_end, progress, cancel=never_cancel):
        n = len(points)
        progress.start("Simulated write data", "", n)
        try:
            for i in range(1, n + 1):
                if cancel():
                    # Nothing has been applied yet, so the AWG is unchanged
                    raise WriteCancelled("Simulated AWG write stopped; trace unchanged")
                time.sleep(self.write_time / n)
                progress.update(i, "Write %i of %i" % (i, n))
        finally:
            progress.finish()
        self.shape = np.asarray(points, dtype=float).copy()


class SimFeedback:
    def __init__(self, awg):
        self.awg = awg

    def measure(self, progress):
        return self.awg.read_normalised_shape()
