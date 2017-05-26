from epics import caput
from time import sleep

shiftWidth = 0.125 #ns
pulseLength = 10.0 #ns

steps = int(pulseLength / shiftWidth)

print steps
caput('DIP-AWG:SetShiftWidth', shiftWidth)
sleep(1.0)
val = 0
dx = 0.0125
x = 0
step = 0
while True:
    pvName = 'DIP-AWG:Sample' + str(step)
    print pvName
    caput(pvName, x)
    sleep(1.0)
    #sleep(2.0)
    x+=dx
    print step
    step += 1
    if step >= steps:
        caput('DIP-AWG:SetWaveform', 1)
        break