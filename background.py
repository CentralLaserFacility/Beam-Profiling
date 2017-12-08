import epics
import util
import time
import numpy as np


datas=[]
for i in range(1):
    data = epics.caget("TEST-SCOPE:CH2:ReadWaveform")
    datas.append(data)
    print len(datas)
    time.sleep(1)

result = np.average(np.array(datas),axis=0)

util.plotstart()
util.plot(result)
util.plotend()

util.save_to_txt(result,"ch2_background_booster_2017_10_13.dat")


