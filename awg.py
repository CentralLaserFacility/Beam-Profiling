import epics
import time
import math
import numpy as np

class  Awg(object):

    def __init__(self, prefix, pulse_size, max_percent_change_allowed=5):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_percent_change_allowed
        self._read_current_shape()

    def _read_current_shape(self):
        print "read current shape..."
        epics.caput(self.prefix + ':ReadWaveform.PROC', 1)
        time.sleep(2)
        self.wf = epics.caget(self.prefix + ':ReadWaveform_do')
        self.dac = epics.caget(self.prefix + ':DAC')
        self.wf = np.clip(self.wf,0,self.dac)
        self.nwf = self.wf/float(self.dac)

    def get_raw_shape(self):
        self._read_current_shape()
        return self.wf

    def get_normalised_shape(self):
        self._read_current_shape()
        return self.nwf


    def save_normalised_shape(self, filename):
        with open(filename, 'w') as f:
            for n in self.nwf:
                f.write(str(n) + '\n')
            f.close()


    def get_dac(self):
        return self.dac

    def modify_point(self, i, val):

        incr = 100.0 * math.fabs(val - self.wf[i])/float(self.dac)

        if(incr >= self.max_incr):
            print "Error: increment too big: %.1f percent of DAC - max is %.1f" % (incr, self.max_incr)

            if (val - self.wf[i] < 0):
                val = self.wf[i] - (self.max_incr/100.0) * self.dac
            else: 
                val = self.wf[i] + (self.max_incr/100.0) * self.dac

            incr = 100.0 * math.fabs(val - self.wf[i])/float(self.dac)

        print "modifying point %d from %f to %f - %.1f percent of DAC" % (i, self.wf[i], val, incr)
        name = self.prefix + ":_SetSample" + str(i) + "_do"

        epics.caput(name,val)


    def multiply_point_by_point(self, prange, multiplier):
        for i in prange:
            val = int(self.nwf[i] * multiplier * self.dac)   
            self.modify_point(i,val)
            time.sleep(1)


    def apply_curve_point_by_point(self, points):

        if (len(points) != self.pulse_size):
            print "Error: size of input list is " + len(points) + ". Expecting " + self.pulse_size 
            return

        for i, point in enumerate(points):
           val = int(point * self.dac) 
           if val > self.dac: continue
           self.modify_point(i, val)
           #print "simulation - point "+ str(i) + " - value " + str(val) 
           time.sleep(1)
           #raw_input("continue")

    
