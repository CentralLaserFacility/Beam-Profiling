"""Writes per-iteration diagnostic files so a loop run can be analysed later.

Each run gets its own folder, named by its start time, holding the run settings
and one set of files per iteration."""

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime

import numpy as np


class DiagnosticWriter:
    def __init__(self, location, run_info=None):
        """
        location: folder in which to create the run folder
        run_info: dict (values may be dataclasses) saved as run.json, e.g. settings and config
        """
        self.location = location
        self.run_info = run_info or {}
        self.folder = None

    def _run_folder(self):
        # Created when the first file is written, so cancelled runs leave nothing behind
        if self.folder is None:
            base = os.path.join(self.location, datetime.now().strftime("run_%Y_%m_%d_%Hh%Mm%S"))
            folder, n = base, 1
            while os.path.exists(folder):
                n += 1
                folder = "{0}_{1}".format(base, n)
            os.makedirs(folder)
            info = {k: asdict(v) if is_dataclass(v) else v for k, v in self.run_info.items()}
            with open(os.path.join(folder, "run.json"), "w") as f:
                json.dump(info, f, indent=2, default=str)
            self.folder = folder
        return self.folder

    def save_iteration(self, i, gain, target, background_raw, awg_now, correction, current):
        folder = self._run_folder()
        if i == 0:
            np.savetxt(os.path.join(folder, "target.txt"), target)
            if background_raw is not None:
                np.savetxt(os.path.join(folder, "background.txt"), background_raw)
        np.savetxt(os.path.join(folder, "i_%0.5d_AWG_shape.txt" % i), awg_now)
        np.savetxt(
            os.path.join(folder, "i_%0.5d_g_%.2f_correction.txt" % (i + 1, gain)), correction
        )
        np.savetxt(os.path.join(folder, "i_%0.5d_scope_trace.txt" % i), current)
