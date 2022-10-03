#!/usr/bin/env python
# 
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
# in the config.ini file
#
#########################################################################################
import os, wx

from configuration import Configuration
from setupframe import SetupFrame

# Avoids wx._core.wxAssertionError:
# C++ assertion "strcmp(setlocale(LC_ALL, NULL), "C") == 0"
import locale
locale.setlocale(locale.LC_ALL, 'C')

if __name__ == "__main__":  

    app = wx.App()
    config = Configuration(None)
    
    app.frame = SetupFrame(config, parent = None)
    app.frame.Show()
    app.MainLoop()
