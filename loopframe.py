from header import (SCOPE_WAIT_TIME, 
                    AWG_PREFIX, 
                    SIMULATION, 
                    DIAG_FILE_LOCATION, 
                    AWG_ZERO_SHIFT,
                    PULSE_PEAK_POWER, 
                    get_message_time)
from awg import Awg
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas
import time, math, pylab, wx, sys
import numpy as np
import epics
from datetime import datetime
import matplotlib.pyplot as plt
from curve import Curve
from scipy.ndimage.filters import gaussian_filter1d


class LoopFrame(wx.Frame):
    ''' Class to run the loop. It launches a new window'''
    _title = "Loop simulation" if SIMULATION == True else "Loop" 
    
    def __init__(self, parent ,start_curve, target_curve, gain, iterations, tolerance, max_percent_change):

        # A bit of work to position this window below the main setup window
        parent_x, parent_y = parent.GetPosition().Get()
        parent_height = parent.GetSize().GetHeight()
        position = wx.Point(parent_x, parent_y+parent_height)
        
        wx.Frame.__init__(self, parent, size=(1000,400), title=self._title, pos=position)
        self.parent = parent
        self.Bind(wx.EVT_CLOSE, self.close_window)

        # Set up the parameters for the AWG and the looping
        self.max_percent_change = max_percent_change
        self.num_points = int(self.parent.points_text_ctrl.GetValue())
        self.current_output=start_curve.get_processed()
        self.correction_factor = np.zeros(np.alen(self.current_output))
        if not SIMULATION:
            self.awg = Awg(AWG_PREFIX, self.num_points , self.max_percent_change)
        self.gain = gain
        self.tolerance = tolerance
        self.iterations = iterations
        self.i = 0 #Store the loop count for stopping/restarting loop
        self.save_diag_files = True if parent.diag_files_radio_box.GetSelection() == 0 else False
        
        # Filter the target curve and renormalise
        #self.target=target_curve.get_processed()
        self.target=gaussian_filter1d(target_curve.get_processed(), sigma=1, order=0)
        self.target=self.target/np.max(self.target)
        
        # Create a panel to hold a log output
        log_panel = wx.Panel(self, wx.ID_ANY)
        log = wx.TextCtrl(log_panel, size=(1000,100),
                          style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(log, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        log_panel.SetSizer(sizer)

        # Point stdout to the log window
        log_stream = RedirectText(log)
        self.standard_stdout = sys.stdout
        sys.stdout=log_stream
        
        # Canvas to hold the plots
        self.init_plot()
        self.canvas = FigCanvas(self, -1, self.fig)
        self.vbox = wx.BoxSizer(wx.VERTICAL)

        # Add canvas and log window to sizer
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.vbox.Add(log_panel, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.vbox)
        self.vbox.Fit(self)
        
        # Draw the window and display
        self.draw_plots()
        self.parent.Disable() # Stop the user launching another loop window until this one is closed
        self.Show()
        self.run_loop()


    def close_window(self, event):
        # Restore stdout to normal, and enable the parent before closing
        sys.stdout = self.standard_stdout
        self.parent.Enable()
        self.Destroy()


    def init_plot(self):
        self.dpi = 100
        self.fig = plt.Figure((12.0, 4.0), dpi=self.dpi)
        self.curve_axis = self.fig.add_subplot(131)
        self.correction_axis = self.fig.add_subplot(132)
        self.awg_axis = self.fig.add_subplot(133)
        pylab.setp(self.curve_axis.get_xticklabels(), fontsize=8)
        pylab.setp(self.curve_axis.get_yticklabels(), fontsize=8)
        pylab.setp(self.correction_axis.get_xticklabels(), fontsize=8)
        pylab.setp(self.correction_axis.get_yticklabels(), fontsize=8)
        pylab.setp(self.awg_axis.get_xticklabels(), fontsize=8)
        pylab.setp(self.awg_axis.get_xticklabels(), fontsize=8)
        pylab.setp(self.correction_axis, title = "Applied Correction")
        pylab.setp(self.curve_axis, title = "Pulse Shape")
        pylab.setp(self.awg_axis, title="AWG")
        self.corr_plot_data = self.correction_axis.plot(self.correction_factor, label = 'Correction')[0]
        self.curve_plot_data = self.curve_axis.plot(self.current_output, label = 'Current')[0]
        self.target_plot_data = self.curve_axis.plot(self.target, label = 'Target')[0]
        self.curve_axis.legend(loc=8, prop={'size':8})
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        if not SIMULATION:
            awg_start = self.awg.get_normalised_shape()[:self.num_points]
        else: 
            awg_start = self.correction_factor
        self.awg_now_plot_data = self.awg_axis.plot(awg_start, label = 'AWG current')[0]
        self.awg_next_plot_data = self.awg_axis.plot(awg_start, label = 'AWG next')[0]
        self.awg_axis.legend(loc=8, prop={'size':8})
        self.awg_axis.set_ybound(lower = -0.1, upper = 1.2)
        self.statusBar = wx.StatusBar(self, -1)
        self.statusBar.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "Ubuntu"))
        self.SetStatusBar(self.statusBar)


    def rms_error(self):
        return np.sqrt(np.mean(np.square(self.target - self.current_output)))


    def peak_power(self, awg_curve):
        return 1.0/np.mean(awg_curve)


    def draw_plots(self, rms = 0, i =0, peak_power=0):
        self.corr_plot_data.set_ydata(self.correction_factor)
        self.curve_plot_data.set_ydata(self.current_output)
        self.correction_axis.set_ybound(lower=0.9*np.amin(self.correction_factor), upper=1.1*np.amax(self.correction_factor)+0.001)
        self.statusBar.SetStatusText("Iteration: {0:d}\tRMS: {1:.3f}\tPeak Power: {2:.2f}".format(i,rms,peak_power))
        self.canvas.draw()     


    def draw_awg_plots(self, awg_current, awg_next):
        self.awg_now_plot_data.set_ydata(awg_current[:self.num_points])
        self.awg_next_plot_data.set_ydata(awg_next[:self.num_points])
        self.canvas.draw()
        
        #proceed = wx.MessageDialog(self, "Apply the next correction?", style=wx.YES_NO|wx.YES_DEFAULT)
        proceed = wx.TextEntryDialog(self.parent, "Gain for next iteration?","Apply?")
        proceed.SetValue(str(self.gain))
        #return 1 if proceed.ShowModal()==wx.ID_YES else 0
        if proceed.ShowModal() == wx.ID_OK:
            try:
                gain = float(proceed.GetValue())
            except:
                gain = self.gain
            self.gain = np.clip(gain,0,1)
            return 1
        else:
            return 0  
             

    def run_loop(self):    
        iterations = self.iterations
        self.draw_plots(self.rms_error(),self.i)
        wx.SafeYield(self) # Lets the plot update
        
        while self.i<iterations and self.rms_error()>=self.tolerance:                     
                
            awg_now = self.get_awg_now(SIMULATION)
            self.calc_correction_factor(awg_now)

            # Apply correction factor. 
            awg_next = awg_now * self.correction_factor
            
            # Apply max % change 
            max_allowed = (1.0 + self.max_percent_change/100.0) * awg_now
            min_allowed = (1.0 - self.max_percent_change/100.0) * awg_now
            awg_next = np.clip(awg_next, min_allowed, max_allowed)

            # If target is non-zero but AWG is zero apply offset of AWG_ZERO_SHIFT
            # If target is zero set AWG to zero directly
            awg_next[np.logical_and(self.target!=0,awg_now==0)]=AWG_ZERO_SHIFT 
            awg_next[self.target==0]=0 

            # Normalise output
            awg_next_norm = awg_next/np.amax(awg_next)

            # Draw plots and check if the user wants to continue
            self.draw_plots(self.rms_error(),self.i, self.peak_power(awg_next_norm))
            cont = self.draw_awg_plots(awg_now, awg_next_norm) 		             
            wx.SafeYield(self)
                            
            if not cont: 
                print(get_message_time()+"Quitting loop. AWG curve will not be applied")
                break
            
            if self.save_diag_files:
                self.save_files(DIAG_FILE_LOCATION, awg_now)
            
            # If the next AWG trace would be unsafe, don't apply it and quit
            if self.peak_power(awg_next_norm) > PULSE_PEAK_POWER:
                print(get_message_time()+"Quitting loop: proposed curve would exceed peak power")
                self.show_power_warning_message()
                break

            self.apply_correction(SIMULATION, awg_next_norm)
            self.update_feedback_curve(SIMULATION)

            # Increase the iteration number and loop again
            self.i+=1

        # After the loop has finished plot the final data. Use the applied AWG trace from the last iteration
        # rather than re-read the AWG values from hardware. The two shouldn't differ unless there was a problem.
        self.draw_plots(self.rms_error(),self.i, -1)
        wx.SafeYield(self) # Needed to allow processing events to stop loop and let plot update
        print(get_message_time()+"Loop ended")
    

    def calc_correction_factor(self, awg_now):
        # Errors if AWG==0 and target!=0, but we handle that later so ignore them
        with np.errstate(divide='ignore', invalid='ignore'): 
            temp=self.target/self.current_output
        self.correction_factor=np.nan_to_num(temp)   
        
        # Apply the gain 
        self.correction_factor = (self.correction_factor - 1) * self.gain + 1

        # When the target!0 and the AWG==0, the correction multiplier is not applied (as it would be infinity)
        # In stead there is a constant offset applied the loop. To avoid displaying false info in the plot of the 
        # correction factor, set those regions to zero in the output
        self.correction_factor = self.correction_factor*(np.logical_not(np.logical_and(self.target!=0,awg_now==0)).astype(int))


    def show_power_warning_message(self):        
        err = wx.MessageDialog(self, "Quitting loop: proposed curve would exceed peak power", caption="Quitting loop")
        err.ShowModal()


    def update_feedback_curve(self, is_simulation):
        start = int(self.parent.scope_start_text_ctrl.GetValue())
        length = int(self.parent.scope_length_text_control.GetValue())
        cropping = (start, start+length)

        if is_simulation:
            data = self.resample(self.current_output, np.size(self.parent.cBackground.get_raw()))
            cropping = (0,1000)
        else:
            data = epics.caget(self.parent.scope_pv_name)
            time.sleep(SCOPE_WAIT_TIME)

        feedback_curve = Curve(curve_array = data, name = 'Current')
        feedback_curve.process('clip','norm',bkg=self.parent.cBackground, 
            crop = cropping , resample = self.num_points)
        self.current_output = feedback_curve.get_processed()
            

    # This is only here for use with the simulation, to simluate a new 1000 point
    # curve being taken from the scope
    def resample(self, data, npoints):
        im = np.arange(0,len(data))
        factor = len(data)/float(npoints)
        ip = np.arange(0, len(data), factor)
        p = np.interp(ip, im, data)
        return p

    
    def save_files(self, location, awg_now):
        fileroot=datetime.now().strftime("%Y_%m_%d_%Hh%M")
        if self.i == 0:
            np.savetxt(location + fileroot + '_target.txt', self.target)
            np.savetxt(location + fileroot + '_background.txt', self.parent.cBackground.get_raw())       
        np.savetxt((location + fileroot + '_i_%0.5d_AWG_shape.txt' % self.i), awg_now)
        np.savetxt((location + fileroot + '_i_%0.5d_g_%.2f_correction.txt' % (self.i+1,self.gain)), self.correction_factor)
        np.savetxt((location + fileroot + '_i_%0.5d_scope_trace.txt' % self.i), self.current_output)


    def apply_correction(self, is_simulation, awg_next_norm):
        if is_simulation:
            self.current_output = awg_next_norm
            print(get_message_time()+"Correction applied for iteration %d" % self.i)
        else:
            # Write the new AWG trace to the hardware
            self.awg.pause_scanning_PVS() #Stop IDIL/AWG comms while writing curve
            if self.i==0:
                # On the first pass only, set any AWG samples outside the pulse to zero
                self.awg.apply_curve_point_by_point(awg_next_norm, zero_to_end=True)
            else:
                self.awg.apply_curve_point_by_point(awg_next_norm, zero_to_end=False)
            self.awg.start_scanning_PVS() #Restart the comms now finished writing


    def get_awg_now(self, is_simulation):
        if is_simulation:
            # Assume 1 to 1 mapping of AWG to output for simulation
            return self.current_output
        else:
            # Read from the AWG and extract the number of points used for this pulse
            return self.awg.get_normalised_shape()[:self.num_points]



# This is used in the constructor of loop frame to redirect output from
# stdout to log panel
class RedirectText(object):
    def __init__(self,aWxTextCtrl):
        self.out=aWxTextCtrl
 
    def write(self,string):
        self.out.WriteText(string)
                