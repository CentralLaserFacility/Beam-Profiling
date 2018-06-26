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
SIMULATION = False
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

# Import from this repo
from awg import Awg
from curve import Curve, BkgCurve, TargetCurve


# begin wxGlade: dependencies
# end wxGlade

# begin wxGlade: extracode
# end wxGlade

class SetupFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: SetupFrame.__init__
        wx.Frame.__init__(self, *args, **kwds)
        self.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "Ubuntu"))
        self.bkg_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.bkg_path_text_ctrl = wx.TextCtrl(self.bkg_choice_panel, wx.ID_ANY, "Path to background file")
        self.bkg_browse_button = wx.BitmapButton(self.bkg_choice_panel, wx.ID_ANY, wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.bkgfile_sizer_staticbox = wx.StaticBox(self.bkg_choice_panel, wx.ID_ANY, "Background file")
        self.bkg_scaling_radio_box = wx.RadioBox(self, wx.ID_ANY, "Scaling", choices=["Resample", "Trim", "None"], majorDimension=3, style=wx.RA_SPECIFY_COLS)
        self.bkg_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0")
        self.bkg_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "82")
        self.bkg_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.bkg_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.target_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.target_path_text_ctrl = wx.TextCtrl(self.target_choice_panel, wx.ID_ANY, "Path to target file")
        self.target_browse_button = wx.BitmapButton(self.target_choice_panel, wx.ID_ANY, wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.target_file_sizer_staticbox = wx.StaticBox(self.target_choice_panel, wx.ID_ANY, "Target file")
        self.target_scaling_radio_box = wx.RadioBox(self, wx.ID_ANY, "Scaling", choices=["Resample", "Trim", "None"], majorDimension=3, style=wx.RA_SPECIFY_COLS)
        self.target_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0")
        self.target_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "82")
        self.target_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.target_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.library_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.library_combo_box = wx.ComboBox(self.library_choice_panel, wx.ID_ANY, choices=["Square pule, 10ns", "Square pulse, 7 ns", "Some other pulse shape..."], style=wx.CB_READONLY | wx.CB_SORT)
        self.library_file_sizer_staticbox = wx.StaticBox(self.library_choice_panel, wx.ID_ANY, "Pulse shape library")
        self.library_scaling_radio_box = wx.RadioBox(self, wx.ID_ANY, "Scaling", choices=["Resample", "Trim", "None"], majorDimension=3, style=wx.RA_SPECIFY_COLS)
        self.library_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0")
        self.library_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "82")
        self.library_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.library_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.scope_pv_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "TEST-SCOPE:CH2:ReadWaveform", style=wx.TE_PROCESS_ENTER)
        self.grab_trace_button = wx.Button(self, wx.ID_ANY, "Grab")
        self.average_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "5")
        self.sizer_6_staticbox = wx.StaticBox(self, wx.ID_ANY, "Avg")
        self.trace_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.save_trace_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/Save.png", wx.BITMAP_TYPE_ANY))
        self.sizer_2_staticbox = wx.StaticBox(self, wx.ID_ANY, "Scope PV")
        self.scope_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0")
        self.scope_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "82")
        self.scope_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.target_source_radio_box = wx.RadioBox(self, wx.ID_ANY, "Target source", choices=["File", "Lib"], majorDimension=2, style=wx.RA_SPECIFY_COLS)
        self.points_label = wx.StaticText(self, wx.ID_ANY, "#Pts", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.points_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "82")
        self.gain_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0.3")
        self.gain_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Gain")
        self.iterations_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "10")
        self.iterations_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Max iterations")
        self.tolerance_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, ".01")
        self.tolerance_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Tolerance")
        self.max_change_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "25")
        self.max_change_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Max % change")
        self.diag_files_radio_box = wx.RadioBox(self, wx.ID_ANY, "Save files each loop", choices=["Yes", "No"], majorDimension=2, style=wx.RA_SPECIFY_COLS)
        self.loop_settings_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Loop settings")
        self.go_button = wx.Button(self, wx.ID_ANY, "Go")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self.on_browse, self.bkg_browse_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.bkg_preview_button)
        self.Bind(wx.EVT_BUTTON, self.on_browse, self.target_browse_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.target_preview_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.library_preview_button)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_scope_pv, self.scope_pv_text_ctrl)
        self.Bind(wx.EVT_BUTTON, self.on_grab_trace, self.grab_trace_button)
        self.Bind(wx.EVT_BUTTON, self.on_preview, self.trace_preview_button)
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
        self.SetSize((1100, 380))
        self.bkg_browse_button.SetSize(self.bkg_browse_button.GetBestSize())
        self.bkg_browse_button.SetDefault()
        self.bkg_scaling_radio_box.SetSelection(0)
        self.target_browse_button.SetSize(self.target_browse_button.GetBestSize())
        self.target_browse_button.SetDefault()
        self.target_scaling_radio_box.SetSelection(0)
        #self.library_combo_box.SetFont(wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "Ubuntu"))
        self.library_combo_box.SetSelection(0)
        self.library_scaling_radio_box.SetSelection(0)
        self.save_trace_button.SetSize(self.save_trace_button.GetBestSize())
        self.target_source_radio_box.SetSelection(0)
        self.diag_files_radio_box.SetSelection(0)
        self.go_button.SetBackgroundColour(wx.Colour(10, 255, 5))
        self.go_button.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
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
        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        self.loop_settings_sizer_staticbox.Lower()
        loop_settings_sizer = wx.StaticBoxSizer(self.loop_settings_sizer_staticbox, wx.HORIZONTAL)
        self.max_change_sizer_staticbox.Lower()
        max_change_sizer = wx.StaticBoxSizer(self.max_change_sizer_staticbox, wx.HORIZONTAL)
        self.tolerance_sizer_staticbox.Lower()
        tolerance_sizer = wx.StaticBoxSizer(self.tolerance_sizer_staticbox, wx.HORIZONTAL)
        self.iterations_sizer_staticbox.Lower()
        iterations_sizer = wx.StaticBoxSizer(self.iterations_sizer_staticbox, wx.HORIZONTAL)
        self.gain_sizer_staticbox.Lower()
        gain_sizer = wx.StaticBoxSizer(self.gain_sizer_staticbox, wx.HORIZONTAL)
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_4 = wx.BoxSizer(wx.VERTICAL)
        self.scope_slice_sizer_staticbox.Lower()
        scope_slice_sizer = wx.StaticBoxSizer(self.scope_slice_sizer_staticbox, wx.HORIZONTAL)
        self.sizer_2_staticbox.Lower()
        sizer_2 = wx.StaticBoxSizer(self.sizer_2_staticbox, wx.HORIZONTAL)
        self.sizer_6_staticbox.Lower()
        sizer_6 = wx.StaticBoxSizer(self.sizer_6_staticbox, wx.VERTICAL)
        library_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.library_slice_sizer_staticbox.Lower()
        library_slice_sizer = wx.StaticBoxSizer(self.library_slice_sizer_staticbox, wx.HORIZONTAL)
        self.library_file_sizer_staticbox.Lower()
        library_file_sizer = wx.StaticBoxSizer(self.library_file_sizer_staticbox, wx.HORIZONTAL)
        target_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.target_slice_sizer_staticbox.Lower()
        target_slice_sizer = wx.StaticBoxSizer(self.target_slice_sizer_staticbox, wx.HORIZONTAL)
        self.target_file_sizer_staticbox.Lower()
        target_file_sizer = wx.StaticBoxSizer(self.target_file_sizer_staticbox, wx.HORIZONTAL)
        bkg_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bkg_slice_sizer_staticbox.Lower()
        bkg_slice_sizer = wx.StaticBoxSizer(self.bkg_slice_sizer_staticbox, wx.HORIZONTAL)
        self.bkgfile_sizer_staticbox.Lower()
        bkgfile_sizer = wx.StaticBoxSizer(self.bkgfile_sizer_staticbox, wx.HORIZONTAL)
        bkgfile_sizer.Add(self.bkg_path_text_ctrl, 4, wx.EXPAND, 0)
        bkgfile_sizer.Add(self.bkg_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.bkg_choice_panel.SetSizer(bkgfile_sizer)
        bkg_sizer.Add(self.bkg_choice_panel, 4, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_sizer.Add((30, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_sizer.Add(self.bkg_scaling_radio_box, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_slice_sizer.Add(self.bkg_start_text_ctrl, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        bkg_slice_sizer.Add(self.bkg_length_text_control, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        bkg_sizer.Add(bkg_slice_sizer, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_sizer.Add(self.bkg_preview_button, 1, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(bkg_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        target_file_sizer.Add(self.target_path_text_ctrl, 3, wx.EXPAND, 0)
        target_file_sizer.Add(self.target_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.target_choice_panel.SetSizer(target_file_sizer)
        target_sizer.Add(self.target_choice_panel, 4, wx.ALIGN_CENTER_VERTICAL, 0)
        target_sizer.Add((30, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        target_sizer.Add(self.target_scaling_radio_box, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        target_slice_sizer.Add(self.target_start_text_ctrl, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        target_slice_sizer.Add(self.target_length_text_control, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        target_sizer.Add(target_slice_sizer, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        target_sizer.Add(self.target_preview_button, 1, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(target_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        library_file_sizer.Add(self.library_combo_box, 2, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        self.library_choice_panel.SetSizer(library_file_sizer)
        library_sizer.Add(self.library_choice_panel, 4, wx.ALIGN_CENTER_VERTICAL, 0)
        library_sizer.Add((30, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        library_sizer.Add(self.library_scaling_radio_box, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        library_slice_sizer.Add(self.library_start_text_ctrl, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        library_slice_sizer.Add(self.library_length_text_control, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        library_sizer.Add(library_slice_sizer, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        library_sizer.Add(self.library_preview_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(library_sizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        main_sizer.Add((500, 20), 0, 0, 0)
        sizer_2.Add(self.scope_pv_text_ctrl, 3, wx.EXPAND, 0)
        sizer_2.Add(self.grab_trace_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        sizer_6.Add(self.average_text_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        sizer_2.Add(sizer_6, 0, 0, 0)
        sizer_2.Add(self.trace_preview_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        sizer_2.Add(self.save_trace_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 0)
        sizer_1.Add(sizer_2, 3, 0, 0)
        scope_slice_sizer.Add(self.scope_start_text_ctrl, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        scope_slice_sizer.Add(self.scope_length_text_control, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        sizer_1.Add(scope_slice_sizer, 0, 0,0)
        sizer_3.Add((20, 20), 0, 0, 0)
        sizer_3.Add(self.target_source_radio_box, 0, wx.ALIGN_CENTER | wx.EXPAND, 0)
        sizer_3.Add((20, 20), 0, 0, 0)
        sizer_4.Add(self.points_label, 1, wx.ALIGN_CENTER, 0)
        sizer_3.Add(sizer_4, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_3.Add(self.points_text_ctrl, 0, wx.ALIGN_CENTER, 0)
        sizer_1.Add(sizer_3, 1, 0, 0)
        main_sizer.Add(sizer_1, 1, 0, 0)
        main_sizer.Add((500, 20), 0, 0, 0)
        gain_sizer.Add(self.gain_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(gain_sizer, 1, wx.RIGHT, 0)
        iterations_sizer.Add(self.iterations_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(iterations_sizer, 1, 0, 0)
        tolerance_sizer.Add(self.tolerance_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(tolerance_sizer, 1, 0, 0)
        max_change_sizer.Add(self.max_change_txt_ctrl, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND, 0)
        loop_settings_sizer.Add(max_change_sizer, 1, 0, 0)
        loop_settings_sizer.Add(self.diag_files_radio_box, 1, wx.ALIGN_CENTER | wx.EXPAND, 0)
        sizer_5.Add(loop_settings_sizer, 4, wx.ALIGN_CENTER | wx.EXPAND, 0)
        sizer_5.Add(self.go_button, 1, wx.EXPAND, 0)
        main_sizer.Add(sizer_5, 1, wx.EXPAND, 0)
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
        curve.plot_all()


    def load(self, reason):
        num_points = int(self.points_text_ctrl.GetValue())
        trim_methods = ['resample', 'truncate', 'off']

        if reason == 'bkg':
            pathname = self.bkg_path_text_ctrl.GetValue()
            trim_method = trim_methods[int(self.bkg_scaling_radio_box.GetSelection())]
            start = int(self.bkg_start_text_ctrl.GetValue())
            length = int(self.bkg_length_text_control.GetValue())
            curve = self.cBackground
            clip_and_norm = False 
        elif reason == 'tgt_file':
            pathname = self.target_path_text_ctrl.GetValue()
            trim_method = trim_methods[int(self.target_scaling_radio_box.GetSelection())]
            start = int(self.target_start_text_ctrl.GetValue())
            length = int(self.target_length_text_control.GetValue())
            curve = self.cTargetFile
            clip_and_norm = True
        elif reason == 'library':
            return
        elif reason == 'trace':
            self.cTrace.plot_raw()
            return
        self.open_and_process(curve, clip_and_norm, num_points, pathname, trim_method, start, length)


    def open_and_process(self, curve, clip_and_norm, num_pts, pathname, trm_meth, start, length):
        curve.load(num_points=num_pts, trim_method = trm_meth, data = str(pathname))
        # Don't clip or normalise the background
        if clip_and_norm == True:
            curve.process('clip','norm', crop = (start, length), resample = num_pts)
        else:
            curve.process(crop = (start, length), resample = num_pts)
        return


    def on_grab_trace(self, event):  # wxGlade: SetupFrame.<event_handler>
        ''' Grabs a user defined number of traces from the scope'''
        num_to_average = int(self.average_text_ctrl.GetValue())        
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
        self.load('bkg')
        if self.target_source_radio_box.GetSelection() == 0:
            target_curve = self.cTargetFile
            self.load('tgt_file')
        else:
            target_curve = self.cLibrary
            self.load('library')
        iterations = int(self.iterations_txt_ctrl.GetValue())
        tolerance = float(self.tolerance_txt_ctrl.GetValue())
        max_percent_change = int(self.max_change_txt_ctrl.GetValue())
        self.run_loop(start_curve, target_curve, gain, iterations, tolerance, max_percent_change)


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
        self.max_percent_change = max_percent_change
        self.user_end = False
        #Matplotlib callbacks
        self.cid = self.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid = self.canvas.mpl_connect('key_press_event', self.on_key)
        self.Bind(wx.EVT_CLOSE, self.close_window)
        self.parent.go_button.Disable() # Stop the user launching another loop window until this one is closed
        self.Show()
        self.run_loop()


    def on_click(self,event):
        # Allows mouse click to start/stop the loop
        self.user_end =  not self.user_end
        if not self.user_end:
            self.run_loop()  


    def on_key(self,event):
        # Rereads parms from the main window 
        if event.key == "ctrl+r":
            self.reread_parms()


    def reread_parms(self):
        self.i=0
        self.gain = float(self.parent.gain_txt_ctrl.GetValue())
        num_points = int(self.parent.points_text_ctrl.GetValue())
        
        if SIMULATION:
            curve = Curve(curve_array = 0.5*np.ones(num_points))
            self.current = curve.get_processed()
        else:
            self.update_feedback_curve()

        # Reload curves
        self.parent.load('bkg')
        if self.parent.target_source_radio_box.GetSelection() == 0:
            target_curve = self.parent.cTargetFile
            self.parent.load('tgt_file')
        else:
            target_curve = self.parent.cLibrary
            self.parent.load('library')
        self.iterations = int(self.parent.iterations_txt_ctrl.GetValue())
        self.tolerance = float(self.parent.tolerance_txt_ctrl.GetValue())
        self.max_percent_change = int(self.parent.max_change_txt_ctrl.GetValue())
        self.correction_factor = np.zeros(np.alen(self.current))
        self.target=target_curve.get_processed()
        self.target_plot_data.set_ydata(self.target)


    def close_window(self, event):
        self.parent.go_button.Enable()
        self.Destroy()


    def init_plot(self):
        self.dpi = 100
        self.fig = plt.Figure((10.0, 5.0), dpi=self.dpi)
        self.curve_axis = self.fig.add_subplot(121)
        self.correction_axis = self.fig.add_subplot(122)
        pylab.setp(self.curve_axis.get_xticklabels(), fontsize=10)
        pylab.setp(self.curve_axis.get_yticklabels(), fontsize=10)
        pylab.setp(self.correction_axis.get_xticklabels(), fontsize=10)
        pylab.setp(self.correction_axis.get_yticklabels(), fontsize=10)
        pylab.setp(self.correction_axis, title = "Applied Correction")
        pylab.setp(self.curve_axis, title = "Pulse Shape")
        self.corr_plot_data = self.correction_axis.plot(self.correction_factor, label = 'Correction')[0]
        self.target_plot_data = self.curve_axis.plot(self.target, label = 'Target')[0]
        self.curve_plot_data = self.curve_axis.plot(self.current, label = 'Current')[0]
        self.curve_axis.legend()
        self.i_label = self.curve_axis.text(0.05,0.95, "Iteration: ",transform=self.curve_axis.transAxes, backgroundcolor='white')
        self.rms_label = self.curve_axis.text(0.05,0.9, "RMS: ",transform=self.curve_axis.transAxes, backgroundcolor='white')


    def rms_error(self):
        return np.sqrt(np.mean(np.square(self.target - self.current)))


    def draw_plots(self, rms = 0, i =0):
        self.corr_plot_data.set_ydata(self.correction_factor)
        self.curve_plot_data.set_ydata(self.current)
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        self.correction_axis.set_ybound(lower=0.9*np.amin(self.correction_factor), upper=1.1*np.amax(self.correction_factor))
        self.i_label.set_text("Iteration: %d" % i)
        self.rms_label.set_text("RMS: %.3f" % rms)
        self.canvas.draw()        


    def run_loop(self):
        if not SIMULATION:
            awg = Awg("DIP-AWG", self.num_points , self.max_percent_change)
        iterations = self.iterations
        gain = self.gain
        self.draw_plots(self.rms_error(),self.i)
        
        while self.i<iterations and self.rms_error()>=self.tolerance and not self.user_end:           
            self.correction_factor = np.nan_to_num(self.target/self.current)
            self.correction_factor = (self.correction_factor - 1) * gain + 1

            if SIMULATION: 
                self.current = self.current * self.correction_factor
                time.sleep(0.5)
            else: 
                current_trace = awg.get_normalised_shape()
                next_trace = current_trace[:self.num_points] * self.correction_factor
                next_trace_normalised = next_trace/np.amax(current_trace)
                awg.apply_curve_point_by_point(next_trace_normalised)
                time.sleep(1.1*self.num_points) #There is a wait time of 1 second for each point in the AWG module
                self.update_feedback_curve()

            self.i+=1
            self.draw_plots(self.rms_error(),self.i)
            wx.SafeYield(self) # Needed to allow processing events to stop loop
    
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
            

if __name__ == "__main__":  

    app = wx.App()
    app.frame = SetupFrame(None)
    app.frame.Show()
    app.MainLoop()