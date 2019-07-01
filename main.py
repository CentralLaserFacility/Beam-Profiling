#!/usr/bin/env python
# 
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
# in the config.ini file
#
#########################################################################################
import os, wx

from header import  (DIAG_FILE_LOCATION,
                     EPICS_CA_AUTO_ADDR_LIST,
                     EPICS_CA_ADDR_LIST,
                     epics_setup)

from setupframe import SetupFrame

# Avoids wx._core.wxAssertionError:
# C++ assertion "strcmp(setlocale(LC_ALL, NULL), "C") == 0"
import locale
locale.setlocale(locale.LC_ALL, 'C')

# Peform any setup needed for EPICS (e.g. writing env. variables)
epics_setup(EPICS_CA_ADDR_LIST, EPICS_CA_AUTO_ADDR_LIST)

# Create folder for diagnostic files if necessary
if not os.path.exists(DIAG_FILE_LOCATION):
    os.makedirs(DIAG_FILE_LOCATION)

if __name__ == "__main__":  

    app = wx.App()
    
    app.frame = SetupFrame(None)
    app.frame.Show()
    app.MainLoop()
