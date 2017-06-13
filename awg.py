import epics
import time
import math

class  Awg(object):

    def __init__(self, prefix, pulse_size, max_percent_change_allowed=5):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_percent_change_allowed
        self._read_current_shape()

    def _read_current_shape(self):
        print "read current shape..."
        self.wf = epics.caget(self.prefix + ':ReadWaveform_do')
        self.dac = epics.caget(self.prefix + ':DAC')
        self.nwf = self.wf/float(self.dac)

    def get_raw_shape(self):
        return self.wf

    def get_normalised_shape(self):
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
            val = (self.max_incr/100.0) * self.dac + self.wf[i]
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
           self.modify_point(i, val)
           time.sleep(1)


if __name__ == '__main__':

    awg = Awg('DIP-AWG', 82)
    print awg.get_normalised_shape()
    awg.save_normalised_shape("./awg3.dat")

    # multiply the first 2 points by 1.2
    #awg.multiply_point_by_point(range(0,20), 1.2)

    
