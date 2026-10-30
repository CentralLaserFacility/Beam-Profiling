#!/usr/bin/env python
#
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
# in the config.ini file
#
#########################################################################################
import sys

from beam_shaper.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
