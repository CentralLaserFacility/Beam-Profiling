from awg import Awg
from scope import Scope
import util
import sys

util.plotstart()

# set up scope and read input trace
#scope = Scope("TCPIP::192.168.41.51::5025::SOCKET", "chan2")
#scope.setPulse(0, +12e-9)
#scope.fetch()
#scope.savePulse()
#trace = scope.getPulse()
#scope.close()
trace = util.read_from_csv("/media/sf_VirtualBoxShare/RefCurve_2017-06-08_0_112339.Wfm.csv")
#trace = util.read_from_csv("/media/sf_VirtualBoxShare/RefCurve_2017-06-08_0_123032.Wfm.csv")
#trace = util.read_from_csv("/media/sf_VirtualBoxShare/RefCurve_2017-06-08_1_130918.Wfm.csv")
util.plotpause(trace)

# clip negative at 0
trace = util.clipnegative(trace)
util.plotpause(trace)

# crop trace
trace_start = 570
trace_end = 885
output = trace[trace_start : trace_end]
util.plotpause(output)

#resample and normalise trace
output = util.resample(output, 82)
output = util.normalise(output)
util.plotpause(output)

# set desired shape

desired = util.ramp(0.0,1.0,82)
desired[0] = 0.0
desired[81] = 0.0
util.plotpause(desired, clear=False)

# calculate correction factor
cf = desired/output

print desired
print output
print cf

#d = 1.0
#cf = (cf-1)*d + 1
util.plotpause(cf, clear=False)

# get current shape
#awg = Awg("DIP-AWG", 82, max_percent_change_allowed=20)
#inp = awg.get_normalised_shape()
inp = util.custom("./awg2.dat")
inp = inp[:82]
util.plotpause(inp, clear=False)

# calculate new shape
new = inp * cf
util.plotpause(new, clear=False)

#apply new shape
util.save_to_txt(new,"new.dat")
awg.apply_curve_point_by_point(new)


