"""Per-run loop settings chosen by the user, and the rules that bound them."""

from dataclasses import dataclass

import numpy as np

GAIN_RANGE = (0.05, 1.0)
MIN_ITERATIONS = 1
MIN_TOLERANCE = 0.01
MAX_CHANGE_RANGE = (1, 100)


@dataclass
class LoopSettings:
    gain: float
    iterations: int
    tolerance: float
    max_percent_change: float
    pulse_length: float
    slice_start: int
    slice_length: int
    averages: int
    save_diag_files: bool


def num_points(pulse_length, ns_per_point):
    """Number of AWG points that make up a pulse of the given length (ns)."""
    return int(float(pulse_length / ns_per_point))


def coerce_pulse_length(desired_length, ns_per_point):
    """Round a pulse length (ns) down to a whole number of AWG points."""
    return desired_length - desired_length % ns_per_point


def scope_slice_length(pulse_length, time_resolution):
    """Number of scope samples covering the pulse. time_resolution is in seconds."""
    return int(pulse_length * 1e-9 / time_resolution)


# Each coerce_* function raises ValueError if the text isn't a number, and
# otherwise clamps the value into its allowed range.


def coerce_gain(text):
    return float(np.clip(float(text), *GAIN_RANGE))


def coerce_iterations(text):
    # Read as float and convert to int to allow scientific notation
    return int(max(MIN_ITERATIONS, float(text)))


def coerce_tolerance(text):
    return float(max(MIN_TOLERANCE, float(text)))


def coerce_max_percentage_change(text):
    return int(np.clip(int(text), *MAX_CHANGE_RANGE))
