import epics
import time
import math

class  Awg(object):

    def __init__(self, prefix, pulse_size, max_incr):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_incr
        self._read_current_shape()

    def _read_current_shape(self):
        self.wf = epics.caget(self.prefix + ':ReadWaveform_do')
        self.dac = epics.caget(self.prefix + ':DAC')
        self.nwf = self.wf/float(self.dac)

    def get_raw_shape(self):
        return self.wf

    def get_normalised_shape(self):
        return self.nwf

    def get_dac(self):
        return self.dac

    def modify_point(self, i, val):

        incr = 100.0 * math.fabs(val - self.wf[i])/float(self.dac)

        if(incr >= self.max_incr):
            print "Error: increment too big: %.1f percent of DAC - max is %.1f" % (incr, self.max_incr)
            return

        print "modifying point %d from %d to %d - %.1f percent of DAC" % (i, self.wf[i], val, incr)
        name = self.prefix + ":_SetSample" + str(i) + "_do"
        #epics.caput(name,val)


    def multiply_point_by_point(self, prange, multiplier):
        for i in prange:
            val = int(self.nwf[i] * multiplier * self.dac)   
            self.modify_point(i,val)
            time.sleep(1)


    def apply_curve_point_by_point(self, points):
        #todo: normalise if it isn't already

        if (len(points) != self.pulse_size):
            print "Error: size of input list is " + len(points) + ". Expecting " + self.pulse_size 
            return

        for point in enumerate(points):
           self.modify_point(i,point)
           time.sleep(1)


if __name__ == '__main__':

    prefix = 'DIP-AWG'
    pulse_size = 80 #number of points
    max_incr = 5 #percent of DAC
    awg = Awg(prefix, pulse_size, max_incr)

    print awg.get_normalised_shape()

    # multiply the first 2 points by 1.2
    awg.multiply_point_by_point(range(0,20), 1.2)

    
