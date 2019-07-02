from header import (SCOPE_WAIT_TIME, 
                    AWG_PREFIX, 
                    AWG_WRITE_METHOD, 
                    SIMULATION, 
                    DIAG_FILE_LOCATION, 
                    AWG_ZERO_SHIFT,
                    AWG_NS_PER_POINT,
                    PULSE_PEAK_POWER,
                    AUTO_LOOP,
                    AUTO_LOOP_WAIT,
                    get_message_time,
                    CODES)
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
from dialogs import LoopControlDialog
#from scipy.ndimage.filters import gaussian_filter1d


class LoopFrame(wx.Frame):
    ''' Class to run the loop. It launches a new window'''
    _title = "Loop simulation" if SIMULATION == True else "Loop" 
    
    def __init__(self, parent ,target, background, pulse_length, start, length, scope_pv, time_res_pv, 
                  averages, gain, iterations, tolerance, max_percent_change, save_diag_files):

        # A bit of work to position this window below the main setup window
        parent_x, parent_y = parent.GetPosition().Get()
        parent_height = parent.GetSize().GetHeight()
        position = wx.Point(parent_x, parent_y+parent_height)
        
        wx.Frame.__init__(self, parent, size=(1000,400), title=self._title, pos=position)
        self.parent = parent
        self.Bind(wx.EVT_CLOSE, self.close_window)

        # Set up the parameters for the AWG and the looping
        self.target = target.get_processed()
        self.target=self.target/np.max(self.target) #Normalise
        #self.target=gaussian_filter1d(target_curve.get_processed(), sigma=1, order=0) #filter to smooth edges
        self.background = background
        self.pulse_length = pulse_length
        self.slice_start = start
        self.slice_length = length
        self.scope_pv = scope_pv
        self.time_resolution_pv = time_res_pv
        self.time_res = self.time_resolution_pv.get()
        self.scope_averages = averages
        self.gain = gain
        self.iterations = iterations
        self.tolerance = tolerance
        self.max_percent_change = max_percent_change
        self.save_diag_files = save_diag_files
        self.num_points = int(float(self.pulse_length/AWG_NS_PER_POINT))
        self.i = 0 #Store the loop count for stopping/restarting loop
        self.update_feedback_curve()  
        if SIMULATION:
            self.current_output = self.simulate_start_data()    
        self.correction_factor = np.zeros(np.alen(self.current_output))
        if 1: #not SIMULATION:
            self.awg = Awg(AWG_PREFIX, self.num_points , self.max_percent_change)
        
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
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Add canvas and log window to sizer. Add stop button if auto-looping.
        vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        hbox.Add(log_panel, 5, flag=wx.LEFT | wx.TOP | wx.GROW)
        if AUTO_LOOP:
            # Add a stop button for breaking out of auto-loop
            self.stop_button = wx.Button(self, wx.ID_ANY, "Stop")
            self.stop_button.SetBackgroundColour(wx.Colour(255, 40, 40))
            self.stop_button.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
            self.Bind(wx.EVT_BUTTON, self.on_stop, self.stop_button)
            hbox.Add(self.stop_button, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.stop_loop = False
        vbox.Add(hbox, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(vbox)
        vbox.Fit(self)
                
        # Draw the window and display
        self.draw_plots()
        self.parent.Disable() # Stop the user launching another loop window until this one is closed
        self.Show()
        self.run_loop()


    def on_stop(self, event):
        self.stop_loop = True


    def close_window(self, event):
        # Restore stdout to normal, and enable the parent before closing
        self.stop_loop = True
        sys.stdout = self.standard_stdout
        self.parent.Enable()
        self.Destroy()


    def init_plot(self):       
        # create the plots and add some labels
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
        pylab.setp(self.awg_axis.get_yticklabels(), fontsize=8)
        self.correction_axis.set_xlabel('Time (ns)', fontsize=8)
        self.correction_axis.set_title('Applied Correction')
        self.curve_axis.set_xlabel('Time (ns)', fontsize=8)
        self.curve_axis.set_title('Pulse Shape')
        self.awg_axis.set_xlabel('Time (ns)', fontsize=8)
        self.awg_axis.set_title('AWG')
        
        # setup the values to use on the time axis
        time_axis = np.arange(0, self.num_points*AWG_NS_PER_POINT, AWG_NS_PER_POINT)

        # add data to the plots
        self.corr_plot_data = self.correction_axis.plot(
            time_axis,self.correction_factor, label = 'Correction')[0]        
        self.curve_plot_data = self.curve_axis.plot(
            time_axis,self.current_output, label = 'Current')[0]
        self.target_plot_data = self.curve_axis.plot(
            time_axis,self.target, label = 'Target')[0]
        self.curve_axis.legend(loc=8, prop={'size':8})
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        if not SIMULATION:
            awg_start = self.awg.get_normalised_shape()[:self.num_points]
        else: 
            awg_start = self.correction_factor
        self.awg_now_plot_data = self.awg_axis.plot(
            time_axis,awg_start, label = 'AWG current')[0]
        self.awg_next_plot_data = self.awg_axis.plot(
            time_axis,awg_start, label = 'AWG next')[0]
        self.awg_axis.legend(loc=8, prop={'size':8})
        self.awg_axis.set_ybound(lower = -0.1, upper = 1.2)
        self.statusBar = wx.StatusBar(self, -1)
        self.statusBar.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "Ubuntu"))
        self.SetStatusBar(self.statusBar)


    def rms_error(self):
        try:
            rms = np.sqrt(np.mean(np.square(self.target - self.current_output)))
        except:
            rms=-1
        return rms 


    def peak_power(self):
        try:
            power = 1.0/np.mean(self.awg_next_norm)
        except:
            power = -1
        return power


    def draw_plots(self):
        self.corr_plot_data.set_ydata(self.correction_factor)
        self.curve_plot_data.set_ydata(self.current_output)
        self.correction_axis.set_ybound(lower=0.9*np.amin(self.correction_factor), upper=1.1*np.amax(self.correction_factor)+0.001)
        self.statusBar.SetStatusText("Iteration: {0:d}\tRMS: {1:.3f}\tPeak Power: {2:.2f}\tGain: {3:.2f}".format(
            self.i,
            self.rms_error(),
            self.peak_power(),
            self.gain))
        self.canvas.draw()     


    def draw_awg_plots(self):
        try:
            self.awg_now_plot_data.set_ydata(self.awg_now[:self.num_points])
            self.awg_next_plot_data.set_ydata(self.awg_next_norm[:self.num_points])
            self.canvas.draw()
        except:
            pass


    def check_proceed(self): 
        if AUTO_LOOP:
            i = 0 
            proceed = 1
            prog = wx.ProgressDialog("Ready to write to AWG", "Writing in %i seconds" % AUTO_LOOP_WAIT, 
                        AUTO_LOOP_WAIT, style=wx.PD_AUTO_HIDE|wx.PD_CAN_ABORT, parent=self.parent)
            while (AUTO_LOOP_WAIT - i >= 0):
                if (prog.Update(i, "Writing in %i seconds" % (AUTO_LOOP_WAIT-i))[0]) == False:
                    # User pressed cancel
                    proceed = 0
                    prog.Destroy()
                    break
                i+=1
                time.sleep(1)
            wx.SafeYield(self) # Allow other UI events to process in case user pressed stop button rather than cancel
            return proceed
  
        
        choice = LoopControlDialog(self.parent, title = "Gain for next iteration")
        choice.SetValue(str(self.gain))
        proceed = choice.ShowModal()
        self.gain = float(choice.GetValue())
        
        # If replot is chosen, recalculate, refresh graphs and ask again
        while proceed == CODES.Recalc:
            self.calculate_parms_for_loop()
            self.draw_plots()
            self.draw_awg_plots()
            wx.SafeYield()
            proceed = choice.ShowModal()
            self.gain = float(choice.GetValue())
        choice.Destroy()
        return proceed
            
             

    def run_loop(self):   
        iterations = self.iterations
        self.draw_plots()
        wx.SafeYield(self) # Lets the plot update
        
        while self.i<iterations and self.rms_error()>=self.tolerance:                      


            self.calculate_parms_for_loop()

            # Draw plots and check if the user wants to continue
            self.draw_plots()
            self.draw_awg_plots() 		             
            wx.SafeYield(self)
            proceed = self.check_proceed()                

            if proceed != CODES.Proceed: 
                print(get_message_time()+"Quitting loop. AWG curve will not be applied")
                break
            
            if self.save_diag_files:
                self.save_files()
            
            # If the next AWG trace would be unsafe, don't apply it and quit
            if self.peak_power() > PULSE_PEAK_POWER:
                print(get_message_time()+"Quitting loop: proposed curve would exceed peak power")
                self.show_error("Quitting loop: proposed curve would exceed peak power", "Quitting loop")
                break

            # Check if user stopped the loop
            if self.stop_loop:
                print(get_message_time()+"Quitting loop: user stop")
                break

            self.apply_correction()
            err = self.update_feedback_curve()
            if err == CODES.Error:
                print(get_message_time()+"Quitting loop: couldn't update feedback curve")
                self.show_error("Quitting loop: couldn't update feedback curve", "Quitting loop")
                break

            # Increase the iteration number and loop again
            self.i+=1

        # After the loop has finished plot the final data. Use the applied AWG trace from the last iteration
        # rather than re-read the AWG values from hardware. The two shouldn't differ unless there was a problem.
        self.draw_plots()
        wx.SafeYield(self) # Needed to allow processing events to stop loop and let plot update
        print(get_message_time()+"Loop ended")
    

    def calc_correction_factor(self):
        # Errors if AWG==0 and target!=0, but we handle that later so ignore them
        with np.errstate(divide='ignore', invalid='ignore'): 
            temp=self.target/self.current_output
        temp[np.isfinite(temp) == False] = 1
        #self.correction_factor=np.nan_to_num(temp)       
        
        # Apply the gain 
        self.correction_factor = (temp - 1) * self.gain + 1

        # When the target!0 and the AWG==0, the correction multiplier is not applied (as it would be infinity)
        # Instead there is a constant offset applied the loop. To avoid displaying false info in the plot of the 
        # correction factor, set those regions to zero in the output
        # This shouldn't be necessary if the correction factor is clipped at max% change 
        # self.correction_factor = self.correction_factor*(np.logical_not(np.logical_and(self.target!=0,awg_now==0)).astype(int))


    def calculate_parms_for_loop(self):    
        self.awg_now = self.get_awg_now()
        self.calc_correction_factor()

        # Apply max % change to the correction factor
        self.correction_factor = np.clip(self.correction_factor, 1.0-self.max_percent_change/100.0, 1.0+self.max_percent_change/100.0)

        # Apply correction factor 
        awg_next = self.awg_now * self.correction_factor

        # If target is non-zero but output is zero apply offset of AWG_ZERO_SHIFT
        awg_next[np.logical_and(self.target!=0,self.current_output==0)]+=AWG_ZERO_SHIFT 
        
        # If target is zero set AWG to zero directly
        awg_next[self.target==0]=0 

        # Normalise output
        self.awg_next_norm = awg_next/np.amax(awg_next)


    def apply_correction(self):
        if SIMULATION:
            self.current_output = self.awg_next_norm
            self.awg.sim_write(self.parent)
        else:
            # Write the new AWG trace to the hardware
            self.awg.pause_scanning_PVS() #Stop IDIL/AWG comms while writing curve
            time.sleep(1) #Let the message buffer clear
            if self.i==0:
                # On the first pass only, set any AWG samples outside the pulse to zero
                self.awg.write(self.awg_next_norm, parent=self.parent, zero_to_end=True)
            else:
                self.awg.write(self.awg_next_norm, parent=self.parent, zero_to_end=False)
            self.awg.start_scanning_PVS() #Restart the comms now finished writing
        wx.SafeYield(self)


    def update_feedback_curve(self):
        if SIMULATION:
            # Don't bother with background correction for simulation mode, so 
            # just return
            return CODES.NoError
        
        # Check if scope settings have changed. We could deal with this if they have, but for now
        # just warn user and exit
        if self.time_resolution_pv.get() != self.time_res:
            print(get_message_time()+"Scope time resolution has changed since loop started")
            self.show_error("Scope time resolution has changed since loop started", "Scope settings")
            return CODES.Error

        cropping = (self.slice_start, self.slice_length)      
        datas=[]
        i=0
        if self.scope_pv.connected:
            prog = wx.ProgressDialog("Getting scope data", "Reading trace 1", self.scope_averages, 
                                     style=wx.PD_AUTO_HIDE, parent=self.parent)
            while i < self.scope_averages:
                data = self.scope_pv.get()
                datas.append(data)
                time.sleep(SCOPE_WAIT_TIME)
                i+=1
                prog.Update(i,"Reading trace %d" % (i))                                   
        else:
            self.show_error("Can't connect to scope PV", "Scope read error")
            return CODES.Error

        avg = np.average(np.array(datas),axis=0)  
        feedback_curve = Curve(curve_array = avg, name = 'Current')
        feedback_curve.process('clip','norm',bkg=self.background, 
            crop = cropping , resample = self.num_points)
        self.current_output = feedback_curve.get_processed()
        wx.SafeYield(self)
        return CODES.NoError

    
    def save_files(self):
        location=DIAG_FILE_LOCATION
        fileroot=datetime.now().strftime("%Y_%m_%d_%Hh%M")
        if self.i == 0:
            np.savetxt(location + fileroot + '_target.txt', self.target)
            np.savetxt(location + fileroot + '_background.txt', self.background.get_raw())       
        np.savetxt((location + fileroot + '_i_%0.5d_AWG_shape.txt' % self.i), self.awg_now)
        np.savetxt((location + fileroot + '_i_%0.5d_g_%.2f_correction.txt' % (self.i+1,self.gain)), self.correction_factor)
        np.savetxt((location + fileroot + '_i_%0.5d_scope_trace.txt' % self.i), self.current_output)


    def get_awg_now(self):
        if SIMULATION:
            # Assume 1 to 1 mapping of AWG to output for simulation
            return self.current_output
        else:
            # Read from the AWG and extract the number of points used for this pulse
            return self.awg.get_normalised_shape()[:self.num_points]


    def simulate_start_data(self):
        temp=0.5*np.ones(np.size(self.background.get_raw()))
        temp[250:350]=0
        temp[400:500]=0
        cropping = (self.slice_start, self.slice_length)
        
        sim_curve = Curve(curve_array = temp)
        sim_curve.process('clip','norm',bkg=self.background,
                crop = cropping , resample = self.num_points)
        return sim_curve.get_processed()


    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap,
            style=wx.ICON_ERROR)
        err.ShowModal()

# This is used in the constructor of loop frame to redirect output from
# stdout to log panel
class RedirectText(object):
    def __init__(self,aWxTextCtrl):
        self.out=aWxTextCtrl
 
    def write(self,string):
        self.out.WriteText(string)

