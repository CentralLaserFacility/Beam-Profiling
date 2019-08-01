import epics, time, math, wx
import numpy as np
from datetime import datetime
from header import PAUSE_BETWEEN_AWG_WRITE, AWG_WRITE_METHOD, get_message_time

class  Awg(object):

    def __init__(self, prefix, pulse_size, max_percent_change_allowed=5):
        self.prefix = prefix
        self.pulse_size = pulse_size
        self.max_incr = max_percent_change_allowed
        self.write_method = AWG_WRITE_METHOD
        self.check_write_method()
    #    self._read_current_shape()

    def _read_current_shape(self):
        print(get_message_time()+"Read current shape...")
        epics.caput(self.prefix + ':ReadWaveform_ascii_do.PROC', 1)
        time.sleep(2)
        self.wf = epics.caget(self.prefix + ':ReadWaveform_ascii_do')
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
        

    def pause_scanning_PVS(self):
        epics.caput(self.prefix + ':_SelScanDisable', 1)


    def start_scanning_PVS(self):
        epics.caput(self.prefix + ':_SelScanDisable', 0)


    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap,
            style=wx.ICON_ERROR)
        err.ShowModal()


    def get_message_time(self):
        return datetime.now().strftime("%b_%d_%H:%M.%S")+": "


    def check_write_method(self):
        if not (self.write_method == "wfm" or self.write_method == "pts"):
            msg = ("""Invalid choice of AWG write method in config.ini: \n\nValid choices:\n   - wfm (write whole waveform in one go)\n   - pts (write values point by point)\n\nDefaulting to point by point""")
            cap = "Config file error"
            self.show_error(msg, cap)
            self.write_method = "pts"


    def write(self, points, parent=None, zero_to_end=False):
        # Wrapper to choose the method to use to write data to hardware
        if self.write_method == "pts":
            self.apply_curve_point_by_point(points, parent, zero_to_end)
        elif self.write_method == "wfm":
            self.write_waveform(points, parent)
        else:
            self.show_error("Unknow method for AWG writing: '%s'" % (self.write_method), "AWG write failed")

    def write_waveform(self, points, parent=None):
        # Build the waveform
        data = np.zeros(len(self.wf))
        data[0:len(points)]=points
        
        prog = wx.ProgressDialog("Sending waveform", "Buffering values", parent=parent, style=wx.PD_AUTO_HIDE)

        # Send each of the points to the correct record
        pv_prefix = self.prefix+":HoldSampleNorm"
        for i in range(0, len(data)):
            pv_name = pv_prefix + str(i)
            epics.caput(pv_name , data[i])
        time.sleep(1)

        prog.Pulse("Writing waveform to AWG")
        # Write the whole waveform to the AWG
        epics.caput(self.prefix+":SetWaveform.PROC", 1)
        
        # Wait for the IOC to send not busy before continuing
        while epics.caget(self.prefix + ":SetWaveformBusy"):
            prog.Pulse("Waiting for AWG response")
            time.sleep(0.2)
        prog.Destroy()

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


    def apply_curve_point_by_point(self, points, parent=None, zero_to_end=False):
        if (len(points) != self.pulse_size):
            print(get_message_time()+"Error: size of input list is " + len(points) + ". Expecting " + self.pulse_size) 
            return

        # Setup for a progress box
        progLength = len(points) if not zero_to_end else len(self.wf)
        prog= wx.ProgressDialog('Writing to AWG', 'Writing sample 1', progLength, parent=parent, style=wx.PD_AUTO_HIDE)

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
        prog.Destroy()


    def sim_write(self, parent=None):
            i=0
            prog = wx.ProgressDialog("Simulated write data", "", self.pulse_size, parent=parent, style=wx.PD_AUTO_HIDE)
            while i < self.pulse_size:
                time.sleep(3.0/self.pulse_size)
                i+=1
                prog.Update(i, "Write %i of %i" % (i,self.pulse_size))
            