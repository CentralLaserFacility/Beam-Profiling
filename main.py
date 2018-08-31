#!/usr/bin/env python
# 
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
# in the header.py file
#
# Stuff remaining to be done:
#   - Validate entries for all the user defined numbers in the GUI
#   - Add config files so that fields are popluated with previous values and setups can be saved/loaded
#########################################################################################

from header import DIAG_FILE_LOCATION
from setupframe import SetupFrame
import os, wx

# Create folder for diagnostic files if necessary
if not os.path.exists(DIAG_FILE_LOCATION):
    os.makedirs(DIAG_FILE_LOCATION)

if __name__ == "__main__":  

    app = wx.App()
    app.frame = SetupFrame(None)
    app.frame.Show()
    app.MainLoop()