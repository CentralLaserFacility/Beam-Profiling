from awg import Awg
from scope import Scope
import util
import sys
import epics
import numpy as np

util.plotstart()

iteration = 0
location = "./2017-10-13/"
prefix = "awg_trig"

# set up scope and read input trace
trace = epics.caget("TEST-SCOPE:CH2:ReadWaveform")
util.plotpause(trace)
util.save_to_txt(trace, location + prefix + "__scope" + "__i%d" % iteration)

#substract background
background = util.custom("./ch2_background_booster_2017_10_13.dat")
trace = trace - background
util.plotpause(trace)
util.save_to_txt(trace, location + prefix + "__woback" + "__i%d" % iteration)

# clip negative at 0
trace = util.clipnegative(trace)
util.plotpause(trace)
util.save_to_txt(trace, location + prefix + "__clip" + "__i%d" % iteration)

# crop trace
trace_start = 370
trace_end = 780
output = trace[trace_start : trace_end]
util.plotpause(output)
util.save_to_txt(output, location + prefix + "__crop" + "__i%d" % iteration)

#resample and normalise trace
output = util.resample(output, 82)
output = util.normalise(output)
util.plotpause(output)
util.save_to_txt(output, location + prefix + "__resampled" + "__i%d" % iteration)

# set desired shape
#desired = util.ramp(0.0,1.0,82)
desired = util.square(82)

# rounding the edges
desired[0] = 0.0
desired[1] = 0.04
desired[2] = 0.23
desired[3] = 0.49
desired[4] = 0.69
desired[5] = 0.93
desired[6] = 1.0

desired[75] = 1.0
desired[76] = 0.93
desired[77] = 0.69
desired[78] = 0.49
desired[79] = 0.23
desired[80] = 0.04
desired[81] = 0.0

util.plotpause(desired, clear=False)
util.save_to_txt(desired, location + prefix + "__desired" + "__i%d" % iteration)

#measure error
print util.error(output, desired)

# calculate correction factor
cf = desired/output
cf = np.nan_to_num(cf)

gain = 0.5
cf = (cf-1)*gain + 1
util.plotpause(cf, clear=False)
util.save_to_txt(cf, location + prefix + "__correction_g%f" % gain + "__i%d" % iteration)

# get current shape
awg = Awg("DIP-AWG", 82, max_percent_change_allowed=25)
inp = awg.get_normalised_shape()
#inp = util.custom("./awg2.dat")
inp = inp[:82]
util.plotpause(inp, clear=False)
util.save_to_txt(inp, location + prefix + "__lastinput" + "__i%d" % iteration)

# calculate new shape
new = inp * cf
new_normalised = util.normalise(new)
util.plotpause(new, clear=False)
util.save_to_txt(new, location + prefix + "__newinput" + "__i%d" % iteration)

util.plotpause(new_normalised, clear=False)
util.save_to_txt(new_normalised, location + prefix + "__newinput_normalised" + "__i%d" % iteration)


#apply new shape
#util.save_to_txt(new,"new.dat")
awg.apply_curve_point_by_point(new_normalised)


