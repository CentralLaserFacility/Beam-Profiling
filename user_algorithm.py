#######################################################################
#
# The correction algorithm that calculates the multiplication
# factor to be applied to each point in the AWG trace for the
# next iteration of the loop.
#
# A value of 1 means no change to that AWG point.
#
# Inputs to the function:
#    Target: A 1-D array of floats that specify the target shape
#    Current: A 1-D array of floats, normalised to 1, that describe
#             the current pulse shape
#    Gain: A user-defined float between 0.1 and 1
#
# Output from the function:
#    A 1-D array of floats of the same length as the Target
#
#
# To use your function, assign it to the name calc_correction
#
# Note - if the AWG value is 0, and the target is non-zero, then
# your algorithm shouldn't throw an error and you need to manage that.
# On the first iteration of the loop, the software will detect the
# problem and apply an offset to the AWG of 'awg_zero_shift' as defined
# in the config file.
#
# ######################################################################

import numpy as np


def default_correction_calc(target, current, gain):
    # Errors if awg==0 and target!=0, but this is handled
    # by the awg_zero_shift in the first loop so safe to ignore
    with np.errstate(divide="ignore", invalid="ignore"):
        temp = target / current
    # replace any non-finite values in the correction with 1
    temp[np.isfinite(temp) == False] = 1
    # Apply the gain
    correction_factor = (temp - 1) * gain + 1
    return correction_factor


calc_correction = default_correction_calc
