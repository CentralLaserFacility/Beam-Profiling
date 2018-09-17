from header import SCOPE_WAIT_TIME, AWG_PREFIX, SIMULATION, DIAG_FILE_LOCATION
from awg import Awg
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas
import time, math, pylab,wx
import numpy as np
import epics
from datetime import datetime
import matplotlib.pyplot as plt
from curve import Curve

class LoopFrame(wx.Frame):
    ''' Class to run the loop. It launches a new window'''

    _title = "Loop simulation" if SIMULATION == True else "Loop" 

    def __init__(self, parent,start_curve, target_curve, gain, iterations, tolerance, max_percent_change):
        wx.Frame.__init__(self, parent, size=(1000,400), title=self._title)
        self.parent = parent
        self.num_points = int(self.parent.points_text_ctrl.GetValue())
        self.current=start_curve.get_processed()
        self.correction_factor = np.zeros(np.alen(self.current))
        self.target=target_curve.get_processed()
        self.max_percent_change = max_percent_change
        if not SIMULATION:
            self.awg = Awg(AWG_PREFIX, self.num_points , self.max_percent_change)
        self.init_plot()
        self.canvas = FigCanvas(self, -1, self.fig)
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.canvas, 10, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.vbox)
        self.vbox.Fit(self)
        self.draw_plots()
        self.gain = gain
        self.iterations = iterations
        self.i = 0 #Store the loop count for stopping/restarting loop
        self.tolerance = tolerance
        self.user_end = False
        #Matplotlib callbacks
        self.cid = self.canvas.mpl_connect('button_press_event', self.on_click)
    #    self.cid = self.canvas.mpl_connect('key_press_event', self.on_key)
        self.Bind(wx.EVT_CLOSE, self.close_window)
        self.parent.go_button.Disable() # Stop the user launching another loop window until this one is closed
        self.save_diag_files = True if parent.diag_files_radio_box.GetSelection() == 0 else False
        self.Show()
        self.run_loop()


    def on_click(self,event):
        # Allows mouse click to start/stop the loop 
        if event.button == 1 and self.user_end == True:
            self.user_end = False
            self.run_loop()
        elif event.button == 3 and self.user_end == False:
            self.user_end = True

    # def on_key(self,event):
    #     # Rereads parms from the main window 
    #     if event.key == "ctrl+r":
    #         self.reread_parms()


    # def reread_parms(self):
    #     self.i=0
    #     self.gain = float(self.parent.gain_txt_ctrl.GetValue())
    #     num_points = int(self.parent.points_text_ctrl.GetValue())
        
    #     if SIMULATION:
    #         curve = Curve(curve_array = 0.5*np.ones(num_points))
    #         self.current = curve.get_processed()
    #     else:
    #         self.update_feedback_curve()

    #     # Reload curves
    #     self.parent.load('bkg')
    #     if self.parent.target_source_radio_box.GetSelection() == 0:
    #         target_curve = self.parent.cTargetFile
    #         self.parent.load('tgt_file')
    #     else:
    #         target_curve = self.parent.cLibrary
    #         self.parent.load('library')
    #     self.iterations = int(self.parent.iterations_txt_ctrl.GetValue())
    #     self.tolerance = float(self.parent.tolerance_txt_ctrl.GetValue())
    #     self.max_percent_change = int(self.parent.max_change_txt_ctrl.GetValue())
    #     self.correction_factor = np.zeros(np.alen(self.current))
    #     self.target=target_curve.get_processed()
    #     self.target_plot_data.set_ydata(self.target)


    def close_window(self, event):
        self.parent.go_button.Enable()
        self.Destroy()


    def init_plot(self):
        self.dpi = 100
        self.fig = plt.Figure((15.0, 5.0), dpi=self.dpi)
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
        self.target_plot_data = self.curve_axis.plot(self.target, label = 'Target')[0]
        self.curve_plot_data = self.curve_axis.plot(self.current, label = 'Current')[0]
        self.curve_axis.legend()
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        self.i_label = self.curve_axis.text(0.05,0.95, "Iteration: ",transform=self.curve_axis.transAxes, backgroundcolor='white')
        self.rms_label = self.curve_axis.text(0.05,0.9, "RMS: ",transform=self.curve_axis.transAxes, backgroundcolor='white')
        if not SIMULATION:
            awg_start = self.awg.get_normalised_shape()[:82]
        else: 
            awg_start = self.correction_factor
        self.awg_now_plot_data = self.awg_axis.plot(awg_start, label = 'AWG current')[0]
        self.awg_next_plot_data = self.awg_axis.plot(awg_start, label = 'AWG next')[0]
        self.awg_axis.legend()
        self.awg_axis.set_ybound(lower = -0.1, upper = 1.2)

    def rms_error(self):
        return np.sqrt(np.mean(np.square(self.target - self.current)))

    def draw_plots(self, rms = 0, i =0):
        self.corr_plot_data.set_ydata(self.correction_factor)
        self.curve_plot_data.set_ydata(self.current)
        self.correction_axis.set_ybound(lower=0.9*np.amin(self.correction_factor), upper=1.1*np.amax(self.correction_factor))
        self.i_label.set_text("Iteration: %d" % i)
        self.rms_label.set_text("RMS: %.3f" % rms)
        self.canvas.draw()     

    def draw_awg_plots(self, awg_current, awg_next):
        self.awg_now_plot_data.set_ydata(awg_current[:self.num_points])
        self.awg_next_plot_data.set_ydata(awg_next[:self.num_points])
        self.canvas.draw()
        
        proceed = wx.MessageDialog(self, "Apply the next correction?", style=wx.YES_NO|wx.YES_DEFAULT)
        return 1 if proceed.ShowModal()==wx.ID_YES else 0
             

    def run_loop(self):    
        iterations = self.iterations
        gain = self.gain
        self.draw_plots(self.rms_error(),self.i)
        wx.SafeYield(self) # Lets the plot update
        
        while self.i<iterations and self.rms_error()>=self.tolerance and not self.user_end:           
            self.correction_factor = np.nan_to_num(self.target/self.current)
            self.correction_factor = (self.correction_factor - 1) * gain + 1
            
            if SIMULATION: 
                awg_now = self.current
                awg_next = self.current * self.correction_factor

                self.draw_plots(self.rms_error(),self.i)
                cont = self.draw_awg_plots(self.current, awg_next) 		             
                wx.SafeYield(self)
                
                #Apply correction
                self.current = self.current * self.correction_factor
                self.current[self.target==0]=0
                
                if not cont: 
                    print "Quitting loop: AWG curve will not be applied\n"
                    break
                time.sleep(1)
                

                if self.save_diag_files:
                    self.save_files(DIAG_FILE_LOCATION, awg_now, awg_next)
                
                #self.update_feedback_curve()

            else: 
                awg_now = self.awg.get_normalised_shape()
                awg_now = awg_now[:self.num_points]
                awg_next = awg_now * self.correction_factor
                awg_next[self.target==0]=0 # If the target point is zero, set the AWG to zero directly
                awg_next_norm = awg_next/np.amax(awg_next)
                
                self.draw_plots(self.rms_error(),self.i)
                cont = self.draw_awg_plots(awg_now, awg_next_norm)
                wx.SafeYield(self)
              
                if not cont: 
                    print "Quitting loop: AWG curve will not be applied\n"
                    break
                
                self.awg.pause_scanning_PVS() #Stop IDIL/AWG comms while writing curve
                if self.i==1:
                    # On the first pass only, set any AWG samples outside the pulse to zero
                    self.awg.apply_curve_point_by_point(awg_next_norm, zero_to_end=True)
                else:
                    self.awg.apply_curve_point_by_point(awg_next_norm, zero_to_end=False)
                self.awg.start_scanning_PVS() #Restart the comms now finished writing
                self.update_feedback_curve()

                if self.save_diag_files:
                    self.save_files(DIAG_FILE_LOCATION, awg_now, awg_next_norm)
   
            self.i+=1
        self.draw_plots(self.rms_error(),self.i)
        wx.SafeYield(self) # Needed to allow processing events to stop loop and let plot update
        print "Loop ended"
    
    def update_feedback_curve(self):
        start = int(self.parent.scope_start_text_ctrl.GetValue())
        length = int(self.parent.scope_length_text_control.GetValue())
        cropping = (start, start+length)

        if not SIMULATION:
            data = epics.caget(self.parent.scope_pv_name)
            time.sleep(SCOPE_WAIT_TIME)
        else:
            data = self._resample(self.current, np.size(self.parent.cBackground.get_raw()))
            cropping = (0,1000)
        
        
        feedback_curve = Curve(curve_array = data, name = 'Current')
        feedback_curve.process('clip','norm',bkg=self.parent.cBackground, 
            crop = cropping , resample = self.num_points)
        self.current = feedback_curve.get_processed()
            
    # This is only here for use with the simulation, to simluate a new 1000 point
    # curve being taken from the scope
    def _resample(self, data, npoints):
        im = np.arange(0,len(data))
        factor = len(data)/float(npoints)
        ip = np.arange(0, len(data), factor)
        p = np.interp(ip, im, data)
        return p

    def save_files(self, location, awg_now, awg_next):

        fileroot=datetime.now().strftime("%Y_%d_%m_%Hh%M")

        if self.i == 0:
            np.savetxt(location + fileroot + '_target.txt', self.target)
            np.savetxt(location + fileroot + '_background.txt', self.parent.cBackground.get_raw())
            np.savetxt(location + fileroot + '_initial_AWG_shape.txt', awg_now)
        
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_applied_AWG_shape.txt', awg_next)
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_applied_correction.txt', self.correction_factor)
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_scope_trace.txt', self.current)