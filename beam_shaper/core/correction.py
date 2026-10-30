"""The maths of one loop iteration: from the measured pulse to the next AWG trace."""

import numpy as np


def default_correction(target, current, gain):
    """Multiplicative correction for each AWG point. 1 means no change."""
    # Errors if awg==0 and target!=0, but this is handled
    # by the awg_zero_shift in the first loop so safe to ignore
    with np.errstate(divide="ignore", invalid="ignore"):
        temp = target / current
    # replace any non-finite values in the correction with 1
    temp[np.isfinite(temp) == False] = 1
    return (temp - 1) * gain + 1


def no_filter(data):
    return data


def limit_correction(correction_factor, max_percent_change):
    """Stop any AWG point changing by more than max_percent_change in one step."""
    return np.clip(
        correction_factor,
        1.0 - max_percent_change / 100.0,
        1.0 + max_percent_change / 100.0,
    )


def next_awg_trace(
    awg_now,
    correction_factor,
    target,
    current,
    first_iteration,
    noise_threshold_percentage,
    awg_zero_shift,
):
    """Apply the correction to the current AWG trace (before filtering)."""
    awg_next = awg_now * correction_factor

    # If target is non-zero and output is just noise apply offset. First pass only.
    if first_iteration:
        threshold = noise_threshold_percentage / 100.0
        awg_next[np.logical_and(target != 0, current <= threshold)] += awg_zero_shift

    # If target is zero set AWG to zero directly
    awg_next[target == 0] = 0
    return awg_next


def normalise(data):
    return data / np.amax(data)


def rms_error(target, current):
    """RMS difference between target and measured shape, or -1 if they can't be compared."""
    try:
        return np.sqrt(np.mean(np.square(target - current)))
    except (TypeError, ValueError):
        return -1


def peak_power(awg_next_norm):
    """Peak power relative to a flat pulse of the same energy, or -1 if unknown."""
    try:
        return 1.0 / np.mean(awg_next_norm)
    except (TypeError, ValueError):
        return -1
