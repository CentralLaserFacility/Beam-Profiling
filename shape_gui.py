#!/usr/bin/env python
# 
# Run closed loop pulse-shaping on the AWG. Feedback comes from a waveform PV from a
# scope. To test the software without hardware connected set the SIMULATION flag to TRUE
#
# Stuff remaining to be done:
#   - Validate entries for all the user defined numbers in the GUI
#   - Warn the user if no background file has been defined
#   - Add config files so that fields are popluated with previous values and setups can be saved/loaded
#########################################################################################

#########################################################################################
#Any constants that are needed
SCOPE_WAIT_TIME = 2.1 # Seconds to wait for a caget from the scope to return
SIMULATION = True
DIAG_FILE_LOCATION = "./diag_files/test/"
AWG_PREFIX = "AWG"
DEFAULT_SCOPE_PV="SCOPE:CH2:ReadWaveform"
NO_ERR = 0
#########################################################################################

# Imports from installed packages
import wx
import numpy as np
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas
import matplotlib.pyplot as plt
import time
import pylab
import epics
from epics.wx import EpicsFunction, DelayedEpicsCallback
import os
from datetime import datetime

# Import from this repo
from awg import Awg
from curve import Curve, BkgCurve, TargetCurve

# Create folder for diagnostic files if necessary
if not os.path.exists(DIAG_FILE_LOCATION):
    os.makedirs(DIAG_FILE_LOCATION)


# begin wxGlade: dependencies
# end wxGlade

# begin wxGlade: extracode
# end wxGlade

class SetupFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: SetupFrame.__init__
        wx.Frame.__init__(self, *args, **kwds)
        self.bkg_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.bkg_path_text_ctrl = wx.TextCtrl(self.bkg_choice_panel, wx.ID_ANY, "Path to background file")
        self.bkg_browse_button = wx.BitmapButton(self.bkg_choice_panel, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.bkgfile_sizer_staticbox = wx.StaticBox(self.bkg_choice_panel, wx.ID_ANY, "Background file")
        self.bkg_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.target_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.target_path_text_ctrl = wx.TextCtrl(self.target_choice_panel, wx.ID_ANY, "Path to target file")
        self.target_browse_button = wx.BitmapButton(self.target_choice_panel, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.target_file_sizer_staticbox = wx.StaticBox(self.target_choice_panel, wx.ID_ANY, "Target file")
        self.trace_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.library_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.library_combo_box = wx.ComboBox(self.library_choice_panel, wx.ID_ANY, choices=["Square pule, 10ns", "Square pulse, 7 ns", "Some other pulse shape..."], style=wx.CB_READONLY | wx.CB_SORT)
        self.library_file_sizer_staticbox = wx.StaticBox(self.library_choice_panel, wx.ID_ANY, "Pulse shape library")
        self.library_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.scope_pv_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, DEFAULT_SCOPE_PV, style=wx.TE_PROCESS_ENTER)
        self.grab_trace_button = wx.Button(self, wx.ID_ANY, "Grab")
        self.trc_avg = wx.TextCtrl(self, wx.ID_ANY, "1", style=wx.TE_CENTRE)
        self.trc_avg_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Average")
        self.target_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.save_trace_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("/home/swdev/repos/beamprofiling/gui_files/Save.png", wx.BITMAP_TYPE_ANY))
        self.scope_pv_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Scope PV")
        self.scope_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "290", style=wx.TE_CENTRE)
        self.scope_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "410", style=wx.TE_CENTRE)
        self.scope_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.tgt_src_cb = wx.ComboBox(self, wx.ID_ANY, choices=["File", "Library"], style=wx.CB_READONLY)
        self.src_cb_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Target source")
        self.points_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "82", style=wx.TE_CENTRE)
        self.point_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Num points")
        self.gain_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0.1", style=wx.TE_CENTRE)
        self.gain_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Gain")
        self.iterations_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "10", style=wx.TE_CENTRE)
        self.iterations_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Max iterations")
        self.tolerance_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, ".01", style=wx.TE_CENTRE)
        self.tolerance_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Tolerance")
        self.max_change_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "25", style=wx.TE_CENTRE)
        self.max_change_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Max % change")
        self.diag_files_radio_box = wx.RadioBox(self, wx.ID_ANY, "Save files?", choices=["Yes", "No"], majorDimension=2, style=wx.RA_SPECIFY_COLS)
        self.go_button = wx.Button(self, wx.ID_ANY, "Go")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self.on_browse, self.bkg_browse_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.bkg_preview_button)
        self.Bind(wx.EVT_BUTTON, self.on_browse, self.target_browse_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.trace_preview_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.library_preview_button)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_scope_pv, self.scope_pv_text_ctrl)
        self.Bind(wx.EVT_BUTTON, self.on_grab_trace, self.grab_trace_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.target_preview_button)
        self.Bind(wx.EVT_BUTTON, self.on_trace_save, self.save_trace_button)
        self.Bind(wx.EVT_BUTTON, self.on_go, self.go_button)
        # end wxGlade
        self.Bind(wx.EVT_CLOSE, self.closeWindow)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_scope_pv, self.scope_pv_text_ctrl)

        # Instantiate Curve objects to hold data
        self.cBackground = BkgCurve(name = 'Background')
        self.cTargetFile = TargetCurve(name = 'Target')
        self.cLibrary = Curve(name = 'Library')
        self.cTrace = Curve(name = 'Scope') # Used to hold data from a 'grab'
        self.cFeedback = Curve(name = 'Current') # Holds data from the scope for the loop
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()


    def __set_properties(self):
        # begin wxGlade: SetupFrame.__set_properties
        self.SetTitle("Beam Profiling")
        self.SetSize((1049, 447))
        self.bkg_browse_button.SetSize(self.bkg_browse_button.GetBestSize())
        self.bkg_browse_button.SetDefault()
        self.bkg_preview_button.SetSize(self.bkg_preview_button.GetBestSize())
        self.bkg_preview_button.SetDefault()
        self.target_browse_button.SetSize(self.target_browse_button.GetBestSize())
        self.target_browse_button.SetDefault()
        self.trace_preview_button.SetSize(self.trace_preview_button.GetBestSize())
        self.trace_preview_button.SetDefault()
        self.library_combo_box.SetFont(wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "Ubuntu"))
        self.library_combo_box.SetSelection(0)
        self.library_preview_button.SetSize(self.library_preview_button.GetBestSize())
        self.library_preview_button.SetDefault()
        self.target_preview_button.SetSize(self.target_preview_button.GetBestSize())
        self.target_preview_button.SetDefault()
        self.save_trace_button.SetSize(self.save_trace_button.GetBestSize())
        self.tgt_src_cb.SetSelection(0)
        self.diag_files_radio_box.SetSelection(1)
        self.go_button.SetBackgroundColour(wx.Colour(10, 255, 5))
        self.go_button.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        # end wxGlade
        self.bkg_preview_button.SetName('bkg_prv')
        self.bkg_browse_button.SetName('bkg_browse')
        self.target_browse_button.SetName('tgt_browse')
        self.target_preview_button.SetName('tgt_prv')
        self.library_preview_button.SetName('lby_prv')
        self.trace_preview_button.SetName('trace_prv')

    def __do_layout(self):
        # begin wxGlade: SetupFrame.__do_layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        loop_szr = wx.BoxSizer(wx.HORIZONTAL)
        loop_settings_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.max_change_sizer_staticbox.Lower()
        max_change_sizer = wx.StaticBoxSizer(self.max_change_sizer_staticbox, wx.HORIZONTAL)
        self.tolerance_sizer_staticbox.Lower()
        tolerance_sizer = wx.StaticBoxSizer(self.tolerance_sizer_staticbox, wx.HORIZONTAL)
        self.iterations_sizer_staticbox.Lower()
        iterations_sizer = wx.StaticBoxSizer(self.iterations_sizer_staticbox, wx.HORIZONTAL)
        self.gain_sizer_staticbox.Lower()
        gain_sizer = wx.StaticBoxSizer(self.gain_sizer_staticbox, wx.HORIZONTAL)
        scope_szr = wx.BoxSizer(wx.HORIZONTAL)
        tgt_src_szr = wx.BoxSizer(wx.HORIZONTAL)
        self.point_szr_staticbox.Lower()
        point_szr = wx.StaticBoxSizer(self.point_szr_staticbox, wx.HORIZONTAL)
        self.src_cb_szr_staticbox.Lower()
        src_cb_szr = wx.StaticBoxSizer(self.src_cb_szr_staticbox, wx.HORIZONTAL)
        self.scope_slice_sizer_staticbox.Lower()
        scope_slice_sizer = wx.StaticBoxSizer(self.scope_slice_sizer_staticbox, wx.HORIZONTAL)
        self.scope_pv_szr_staticbox.Lower()
        scope_pv_szr = wx.StaticBoxSizer(self.scope_pv_szr_staticbox, wx.HORIZONTAL)
        self.trc_avg_szr_staticbox.Lower()
        trc_avg_szr = wx.StaticBoxSizer(self.trc_avg_szr_staticbox, wx.HORIZONTAL)
        library_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.library_file_sizer_staticbox.Lower()
        library_file_sizer = wx.StaticBoxSizer(self.library_file_sizer_staticbox, wx.HORIZONTAL)
        target_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.target_file_sizer_staticbox.Lower()
        target_file_sizer = wx.StaticBoxSizer(self.target_file_sizer_staticbox, wx.HORIZONTAL)
        bkg_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bkgfile_sizer_staticbox.Lower()
        bkgfile_sizer = wx.StaticBoxSizer(self.bkgfile_sizer_staticbox, wx.HORIZONTAL)
        bkgfile_sizer.Add(self.bkg_path_text_ctrl, 2, wx.EXPAND, 0)
        bkgfile_sizer.Add(self.bkg_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.bkg_choice_panel.SetSizer(bkgfile_sizer)
        bkg_sizer.Add(self.bkg_choice_panel, 2, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        bkg_sizer.Add((20, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_sizer.Add(self.bkg_preview_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        main_sizer.Add(bkg_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        main_sizer.Add((20, 10), 0, 0, 0)
        target_file_sizer.Add(self.target_path_text_ctrl, 2, wx.EXPAND, 0)
        target_file_sizer.Add(self.target_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.target_choice_panel.SetSizer(target_file_sizer)
        target_sizer.Add(self.target_choice_panel, 2, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        target_sizer.Add((20, 20), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        target_sizer.Add(self.target_preview_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        main_sizer.Add(target_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        main_sizer.Add((20, 10), 0, 0, 0)
        library_file_sizer.Add(self.library_combo_box, 4, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        self.library_choice_panel.SetSizer(library_file_sizer)
        library_sizer.Add(self.library_choice_panel, 2, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        library_sizer.Add((20, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        library_sizer.Add(self.library_preview_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        main_sizer.Add(library_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        main_sizer.Add((500, 10), 0, 0, 0)
        scope_pv_szr.Add(self.scope_pv_text_ctrl, 2, wx.EXPAND, 0)
        scope_pv_szr.Add(self.grab_trace_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        trc_avg_szr.Add(self.trc_avg, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        scope_pv_szr.Add(trc_avg_szr, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        scope_pv_szr.Add(self.trace_preview_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        scope_pv_szr.Add(self.save_trace_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        scope_szr.Add(scope_pv_szr, 3, wx.EXPAND, 0)
        scope_slice_sizer.Add(self.scope_start_text_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        scope_slice_sizer.Add(self.scope_length_text_control, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        scope_szr.Add(scope_slice_sizer, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        tgt_src_szr.Add((10, 20), 0, 0, 0)
        src_cb_szr.Add(self.tgt_src_cb, 1, wx.EXPAND, 0)
        tgt_src_szr.Add(src_cb_szr, 1, wx.EXPAND, 0)
        tgt_src_szr.Add((10, 20), 0, 0, 0)
        point_szr.Add(self.points_text_ctrl, 1, wx.EXPAND, 0)
        tgt_src_szr.Add(point_szr, 1, wx.EXPAND, 0)
        scope_szr.Add(tgt_src_szr, 1, 0, 0)
        main_sizer.Add(scope_szr, 1, wx.EXPAND, 0)
        main_sizer.Add((500, 30), 0, 0, 0)
        gain_sizer.Add(self.gain_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(gain_sizer, 1, wx.BOTTOM | wx.EXPAND | wx.RIGHT, 0)
        iterations_sizer.Add(self.iterations_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(iterations_sizer, 1, wx.EXPAND, 0)
        tolerance_sizer.Add(self.tolerance_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(tolerance_sizer, 1, wx.EXPAND, 0)
        max_change_sizer.Add(self.max_change_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(max_change_sizer, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(self.diag_files_radio_box, 0, wx.ALIGN_CENTER | wx.EXPAND, 0)
        loop_szr.Add(loop_settings_sizer, 4, wx.ALL | wx.EXPAND, 0)
        loop_szr.Add(self.go_button, 1, wx.EXPAND, 0)
        main_sizer.Add(loop_szr, 1, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        self.Layout()
        
        # end wxGlade


    @EpicsFunction
    def on_scope_pv(self,event): # wxGlade: SetupFrame.<event_handler>
        """ Connects to pv when user hits enter. Uses PyEpics. """
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()
        self.scope_pv = epics.PV(self.scope_pv_name, connection_callback=self.on_pv_connect)
        #Change the colour after connection attempt, and set the on/off pv  
        if self.scope_pv.connected:
            self.scope_pv_text_ctrl.SetBackgroundColour('#0aff05')
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour('Red')
        self.scope_pv_text_ctrl.Refresh()
        event.Skip()


    @DelayedEpicsCallback
    def on_pv_connect(self, pvname=None, conn=None, **kwargs):
        """ Change the colour of the field to reflect connetion status. Uses PyEpics """
        if conn:
            self.scope_pv_text_ctrl.SetBackgroundColour('#0aff05')
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour('Red')
        self.scope_pv_text_ctrl.Refresh()


    def closeWindow(self, event):
        self.Destroy()    


    def on_browse(self, event):  # wxGlade: SetupFrame.<event_handler>

        frame = wx.Frame(None, -1, "Load a curve")
        frame.SetDimensions(0,0,200,50)

        with wx.FileDialog(frame, "Load Curve", 
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return    # Quit with no file loaded

        pathname = fileDialog.GetPath()

        if event.GetEventObject().GetName() == 'bkg_browse':
            self.bkg_path_text_ctrl.SetValue(pathname)
        elif event.GetEventObject().GetName() == 'tgt_browse':
            self.target_path_text_ctrl.SetValue(pathname)
            
        
    def on_preview(self, event):  # wxGlade: SetupFrame.<event_handler>   
        if event.GetEventObject().GetName() == 'bkg_prv':
            reason = 'bkg'
            curve = self.cBackground
        elif event.GetEventObject().GetName() == 'tgt_prv':
            reason = 'tgt_file'
            curve = self.cTargetFile
        elif event.GetEventObject().GetName() == 'lby_prv':
            reason = 'library'
            curve = self.cLibrary
        elif event.GetEventObject().GetName() == 'trace_prv':
            reason = 'trace'
            curve = self.cTrace
        self.load(reason)
        curve.plot_processed()


    def load(self, reason):
        num_pts = int(self.points_text_ctrl.GetValue())

        if reason == 'bkg':
            pathname = self.bkg_path_text_ctrl.GetValue()
            err = self.cBackground.load(num_points=num_pts, trim_method = 'off', data = str(pathname))
        elif reason == 'tgt_file':
            pathname = self.target_path_text_ctrl.GetValue()
            err = self.cTargetFile.load(num_points=num_pts, trim_method = 'resample', data = str(pathname))
            self.cTargetFile.process('clip','norm', resample = num_pts)
        elif reason == 'library':
            pass
            err = 0
        elif reason == 'trace':
            pass
            err = 0
        return err
            
        


    # def open_and_process(self, curve, clip_and_norm, num_pts, pathname, trm_meth):
    #     curve.load(num_points=num_pts, trim_method = trm_meth, data = str(pathname))
    #     # Don't clip or normalise the background
    #     if clip_and_norm == True:
    #         curve.process('clip','norm', resample = num_pts)
    #     else:
    #         curve.process(resample = num_pts)
    #     return


    def on_grab_trace(self, event):  # wxGlade: SetupFrame.<event_handler>
        ''' Grabs a user defined number of traces from the scope'''
        num_to_average = int(self.trc_avg.GetValue())        
        datas=[]
        i=0
        while i < num_to_average:
            data = epics.caget(self.scope_pv_name)
            datas.append(data)
            time.sleep(SCOPE_WAIT_TIME)
            i+=1
        result = np.average(np.array(datas),axis=0)
        self.cTrace = Curve(curve_array = result, name = 'Scope')


    def on_trace_save(self, event):  # wxGlade: SetupFrame.<event_handler>
        self.cTrace.save(raw = True)


    def on_go(self, event):  # wxGlade: SetupFrame.<event_handler>
        gain = float(self.gain_txt_ctrl.GetValue())
        num_points = int(self.points_text_ctrl.GetValue())
        start = int(self.scope_start_text_ctrl.GetValue())
        length = int(self.scope_length_text_control.GetValue())
        cropping = (start, start+length)
        if SIMULATION:
            start_curve = Curve(curve_array = 0.5*np.ones(num_points))
        else:
            data = epics.caget(self.scope_pv_name)
            time.sleep(SCOPE_WAIT_TIME)
            self.cFeedback = Curve(curve_array = data, name = 'Current')
            self.cFeedback.process('clip','norm',bkg=self.cBackground, 
                crop = cropping , resample = num_points)
            start_curve = self.cFeedback


        # Reload curves
        bkg_loaded = self.load('bkg')
        if self.tgt_src_cb.GetSelection() == 0:
            target_curve = self.cTargetFile
            target_loaded = self.load('tgt_file')
        else:
            target_curve = self.cLibrary
            target_loaded = self.load('library')

        if bkg_loaded == NO_ERR and target_loaded == NO_ERR :   
            iterations = int(self.iterations_txt_ctrl.GetValue())
            tolerance = float(self.tolerance_txt_ctrl.GetValue())
            max_percent_change = int(self.max_change_txt_ctrl.GetValue())
            self.run_loop(start_curve, target_curve, gain, iterations, tolerance, max_percent_change)
        else:
            err = wx.MessageDialog(self, "Couldn't open the background and/or target files", caption="File open error",
              style=wx.ICON_ERROR)
            err.ShowModal()


    def run_loop(self, start_curve, target_curve, gain, iterations, tolerance, max_percent_change):
        self.loop = LoopFrame(self,start_curve, target_curve, gain, iterations, tolerance, max_percent_change)

# end of class SetupFrame

class LoopFrame(wx.Frame):
    ''' Class to run the loop. It launches a new window. A mouse click in the window will stop/start the loop,
        and ctrl+r will reload the parms for the loop from the main window (need to pause close loop before 
        doing this)'''
    def __init__(self, parent,start_curve, target_curve, gain, iterations, tolerance, max_percent_change):
        wx.Frame.__init__(self, parent, size=(1000,400), title='Loop')
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

    # Needs mod to include the AWG axis
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
       
        #temp = raw_input("q to quit, any other key to continue\n") #User must press key to continue, q will stop the loop
        #return 0 if temp == 'q' else  1
        

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
                
                if not cont: 
                    print "Quitting loop: AWG curve will not be applied\n"
                    break
                time.sleep(2)
                
                #Apply correction
                self.current = self.current * self.correction_factor
                self.current[self.target==0]=0

                if self.save_diag_files:
                    self.save_files(DIAG_FILE_LOCATION, awg_now, awg_next)

            else: 
                awg_now = self.awg.get_normalised_shape()
                awg_next = awg_now[:self.num_points] * self.correction_factor
                awg_next[self.target==0]=0 # If the target point is zero, set the AWG to zero directly
                awg_next_norm = awg_next/np.amax(awg_next)
                
                self.draw_plots(self.rms_error(),self.i)
                cont = self.draw_awg_plots(awg_now, awg_next_norm)
                wx.SafeYield(self)
              
                if not cont: 
                    print "Quitting loop: AWG curve will not be applied\n"
                    break
                
                self.awg.apply_curve_point_by_point(awg_next_norm)
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
        data = epics.caget(self.parent.scope_pv_name)
        time.sleep(SCOPE_WAIT_TIME)
        self.parent.cFeedback = Curve(curve_array = data, name = 'Current')
        self.parent.cFeedback.process('clip','norm',bkg=self.parent.cBackground, 
            crop = cropping , resample = self.num_points)
        self.current = self.parent.cFeedback.get_processed()
            

    def save_files(self, location, awg_now, awg_next):

        fileroot=datetime.now().strftime("%Y_%d_%m_%Hh%M")

        if self.i == 0:
            np.savetxt(location + fileroot + '_target.txt', self.target)
            np.savetxt(location + fileroot + '_background.txt', self.parent.cBackground.get_raw())
            np.savetxt(location + fileroot + '_initial_AWG_shape.txt', awg_now)
        
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_applied_AWG_shape.txt', awg_next)
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_applied_correction.txt', self.correction_factor)
        np.savetxt(location + fileroot + '_i_' + str(self.i) + '_scope_trace.txt', self.current)

if __name__ == "__main__":  

    app = wx.App()
    app.frame = SetupFrame(None)
    app.frame.Show()
    app.MainLoop()
