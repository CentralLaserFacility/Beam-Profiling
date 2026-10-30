"""Writes per-iteration diagnostic files so a loop run can be analysed later."""

import os
from datetime import datetime

import numpy as np


class DiagnosticWriter:
    def __init__(self, location):
        self.location = location

    def save_iteration(self, i, gain, target, background_raw, awg_now, correction, current):
        fileroot = os.path.join(self.location, datetime.now().strftime("%Y_%m_%d_%Hh%M"))
        if i == 0:
            np.savetxt(fileroot + "_target.txt", target)
            np.savetxt(fileroot + "_background.txt", background_raw)
        np.savetxt(fileroot + "_i_%0.5d_AWG_shape.txt" % i, awg_now)
        np.savetxt(fileroot + "_i_%0.5d_g_%.2f_correction.txt" % (i + 1, gain), correction)
        np.savetxt(fileroot + "_i_%0.5d_scope_trace.txt" % i, current)
