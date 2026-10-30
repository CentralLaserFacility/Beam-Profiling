import os
import sys
import time

import epics
import numpy as np

from beam_shaper.core.curve import Curve
from beam_shaper.core.interfaces import FeedbackError


def configure_epics(addr_list, auto_addr_list):
    """Set Channel Access environment. Must run before the first PV is created."""
    os.environ["EPICS_CA_ADDR_LIST"] = addr_list
    # libca only treats exactly "NO" or "no" as off - anything else, e.g. "No", means YES
    off = auto_addr_list.strip().lower() in ("no", "false", "0", "off")
    os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO" if off else "YES"
    # Add caRepeater to the path. The epics module does the hard work of finding
    # ca.dll and caRepeater is in the same dir
    try:
        ca_dir = os.path.dirname(str(epics.ca.find_lib("ca")))
    except epics.ca.ChannelAccessException:
        # Can't find library path. Try another way
        ca_dir = epics.__path__[0] + os.path.sep + sys.platform
    if ca_dir not in sys.path:
        sys.path.append(ca_dir)


def time_resolution_pv_name(scope_pv_name):
    return scope_pv_name.split(":")[0] + ":SetResolution"


def read_average(scope_pv, averages, wait, progress):
    """Average several traces from the scope waveform PV."""
    if not scope_pv.connected:
        raise FeedbackError("Can't connect to scope PV")
    datas = []
    progress.start("Getting scope data", "Reading trace 1", averages)
    try:
        for i in range(1, averages + 1):
            datas.append(scope_pv.get())
            time.sleep(wait)
            progress.update(i, "Reading trace %d" % i)
    finally:
        progress.finish()
    try:
        return np.average(np.array(datas), axis=0)
    except (TypeError, ValueError) as e:
        raise FeedbackError(
            "Scope may not be sending data. Check correct PV is connected "
            "and that the scope IOC is running"
        ) from e


class EpicsFeedback:
    """Measures the pulse shape from a scope, processed to line up with the AWG points."""

    def __init__(self, scope_pv, time_resolution_pv, background, crop, num_points, averages, wait):
        self.scope_pv = scope_pv
        self.time_resolution_pv = time_resolution_pv
        self.background = background
        self.crop = crop
        self.num_points = num_points
        self.averages = averages
        self.wait = wait
        self.time_res = time_resolution_pv.get()

    def measure(self, progress):
        # Check if scope settings have changed. We could deal with this if they have, but for now
        # just stop the loop
        if self.time_resolution_pv.get() != self.time_res:
            raise FeedbackError("Scope time resolution has changed since loop started")

        avg = read_average(self.scope_pv, self.averages, self.wait, progress)
        feedback_curve = Curve(curve_array=avg, name="Current")
        feedback_curve.process(
            clip=True,
            norm=True,
            bkg=self.background,
            crop=self.crop,
            resample=self.num_points,
        )
        return feedback_curve.get_processed()
