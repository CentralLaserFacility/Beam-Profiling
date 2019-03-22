import epics, time, math, wx
import numpy as np
from datetime import datetime
from header import PAUSE_BETWEEN_AWG_WRITE, get_message_time

class  Awg(object):

    def __init__(self, prefix, pulse_size, max_percent_change_allowed=5):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_percent_change_allowed
    #    self._read_current_shape()

    def _read_current_shape(self):
        print(get_message_time()+"Read current shape...")
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
            print(get_message_time()+"Error: increment too big: %.1f percent of DAC - max is %.1f" % (incr, self.max_incr))

            if (val - self.wf[i] < 0):
                val = self.wf[i] - (self.max_incr/100.0) * self.dac
            else: 
                val = self.wf[i] + (self.max_incr/100.0) * self.dac

            incr = 100.0 * math.fabs(val - self.wf[i])/float(self.dac)

        print(get_message_time()+"Modifying point %d from %d to %d : %.1f percent of DAC" % (i, self.wf[i], val, incr))
        name = self.prefix + ":_SetSample" + str(i) + "_do"

        epics.caput(name,val)


    def apply_curve_point_by_point(self, points, zero_to_end=False):

        if (len(points) != self.pulse_size):
            print(get_message_time()+"Error: size of input list is " + len(points) + ". Expecting " + self.pulse_size) 
            return

        # Setup for a progress box
        progLength = len(points) if not zero_to_end else len(self.wf)
        prog= wx.ProgressDialog('Writing to AWG', 'Writing sample 1', progLength)

        for i, point in enumerate(points):
           val = int(point * self.dac) 
           if val > self.dac: continue
           self.modify_point(i, val)
           #print "simulation - point "+ str(i) + " - value " + str(val) 
           prog.Update(i, "Writing sample %d" % (i))
           time.sleep(PAUSE_BETWEEN_AWG_WRITE)
           #raw_input("continue")

        # If requested, zero anything outside the current range of pulse shaping algorithm
        # Not concerned about changed > max % change here as we're going to zero.
        if zero_to_end == True:
            i = len(points)
            while i < len(self.wf):
                prog.Update(i, "Writing sample %d" % (i))
                if self.wf[i] != 0:
                    print(get_message_time()+"Setting point %d to zero" % i)
                    epics.caput(self.prefix + ":_SetSample" + str(i) + "_do",0)
                    time.sleep(PAUSE_BETWEEN_AWG_WRITE)
                i+=1
        #prog.Destroy()
        

    def pause_scanning_PVS(self):
        epics.caput(self.prefix + ':_SelScanDisable', 1)

    def start_scanning_PVS(self):
        epics.caput(self.prefix + ':_SelScanDisable', 0)
    
    def get_message_time(self):
        return datetime.now().strftime("%b_%d_%H:%M.%S")+": "
