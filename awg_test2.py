import epics
import time

wf = epics.caget('DIP-AWG:ReadWaveform_do')
print wf

#normalise it
wf = wf/1475.0
print wf

dac = epics.caget("DIP-AWG:DAC")

#modify it a bit...
for i in range(0,30):
    val = int(wf[i] * 1 * dac)
    name = "DIP-AWG:_SetSample" + str(i) + "_do"
    epics.caput(name,val)
    time.sleep(1)

print "done"
