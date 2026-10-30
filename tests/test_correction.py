import numpy as np
import pytest

from beam_shaper.core import correction as corr


def test_default_correction_moves_towards_target_by_gain():
    target = np.array([1.0, 0.5, 0.2])
    current = np.array([0.5, 0.5, 0.4])
    np.testing.assert_allclose(
        corr.default_correction(target, current, 0.5), [1.5, 1.0, 0.75]
    )


def test_default_correction_is_one_where_current_is_zero():
    target = np.array([1.0, 0.0])
    current = np.array([0.0, 0.0])
    np.testing.assert_array_equal(corr.default_correction(target, current, 1.0), [1.0, 1.0])


def test_limit_correction_clips_to_max_percent():
    np.testing.assert_allclose(
        corr.limit_correction(np.array([0.5, 1.0, 1.1, 2.0]), 25), [0.75, 1.0, 1.1, 1.25]
    )


def test_zero_shift_only_on_first_iteration_and_only_where_signal_is_noise():
    awg_now = np.array([0.5, 0.0, 0.0, 0.5])
    target = np.array([1.0, 1.0, 0.0, 1.0])
    current = np.array([0.5, 0.01, 0.01, 0.5])
    ones = np.ones(4)
    first = corr.next_awg_trace(awg_now, ones, target, current, True, 3.0, 0.1)
    later = corr.next_awg_trace(awg_now, ones, target, current, False, 3.0, 0.1)
    np.testing.assert_allclose(first, [0.5, 0.1, 0.0, 0.5])
    np.testing.assert_allclose(later, [0.5, 0.0, 0.0, 0.5])


def test_awg_is_zero_wherever_target_is_zero():
    out = corr.next_awg_trace(
        np.ones(3), np.ones(3), np.array([1.0, 0.0, 1.0]), np.ones(3), False, 3.0, 0.1
    )
    np.testing.assert_array_equal(out, [1.0, 0.0, 1.0])


def test_peak_power_and_rms():
    assert corr.peak_power(np.array([1.0, 0.5, 0.5, 0.0])) == pytest.approx(2.0)
    assert corr.rms_error(np.array([1.0, 0.0]), np.array([0.0, 0.0])) == pytest.approx(
        np.sqrt(0.5)
    )


def test_unknown_values_are_minus_one():
    assert corr.peak_power(None) == -1
    assert corr.rms_error(np.ones(3), np.ones(4)) == -1
