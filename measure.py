import util
import shaper
import math

import numpy as np
import sys
import time


m = shaper.custom("data.txt")
im = np.arange(0,len(m))

factor = len(m)/float(80)
print factor

ip = np.arange(0, len(m), factor)
p = np.interp(ip, im, m)

util.plotstart()
util.plotx(im, m, point='.', linestyle='-')
util.plotx(ip, p, point='x', linestyle='-')
util.plotend()


