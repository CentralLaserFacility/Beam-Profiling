#!/usr/bin/env python
#
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
# in the config.ini file
#
#########################################################################################
import logging

import wx

from beam_shaper.core.config import AppConfig
from beam_shaper.hardware.epics_scope import configure_epics
from setupframe import SetupFrame
from wx_adapters import MESSAGE_TIME_FORMAT

# Avoids wx._core.wxAssertionError:
# C++ assertion "strcmp(setlocale(LC_ALL, NULL), "C") == 0"
import locale
locale.setlocale(locale.LC_ALL, 'C')

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s: %(message)s", datefmt=MESSAGE_TIME_FORMAT
    )

    app = wx.App()
    config = AppConfig.load()
    configure_epics(config.epics_ca_addr_list, config.epics_ca_auto_addr_list)
    config.ensure_diag_folder()

    app.frame = SetupFrame(config, parent = None)
    app.frame.Show()
    app.MainLoop()
