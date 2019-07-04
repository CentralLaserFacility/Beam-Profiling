
from loopframe import LoopFrame #Must import LoopFrame first as it sets correct matplotlib backend.
from curve import Curve, BkgCurve, TargetCurve
import numpy as np
import wx, time, os, sys
from header import (SCOPE_WAIT_TIME, 
                    SIMULATION, 
                    DEFAULT_SCOPE_PV,
                    LIBRARY_FILES_LOCATION, 
                    AWG_NS_PER_POINT,
                    CODES)

if sys.version_info[0] < 3:
    import ConfigParser as cp
else:
    import configparser as cp

import epics
from epics.wx import EpicsFunction, DelayedEpicsCallback


class SetupFrame(wx.Frame):
    def __init__(self, *args, **kwds):

        wx.Frame.__init__(self, *args, pos=wx.Point(50,50)) # *args, **kwds)
        self.bkg_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.bkg_path_text_ctrl = wx.TextCtrl(self.bkg_choice_panel, wx.ID_ANY, "Path to background file")
        self.bkg_browse_button = wx.BitmapButton(self.bkg_choice_panel, wx.ID_ANY, wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.bkgfile_sizer_staticbox = wx.StaticBox(self.bkg_choice_panel, wx.ID_ANY, "Background file")
        self.bkg_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.target_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.target_path_text_ctrl = wx.TextCtrl(self.target_choice_panel, wx.ID_ANY, "Path to target file")
        self.target_browse_button = wx.BitmapButton(self.target_choice_panel, wx.ID_ANY, wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY))
        self.target_file_sizer_staticbox = wx.StaticBox(self.target_choice_panel, wx.ID_ANY, "Target file")
        self.trace_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.library_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.library_combo_box = wx.ComboBox(self.library_choice_panel, wx.ID_ANY, choices=[], style=wx.CB_READONLY | wx.CB_SORT)
        self.library_file_sizer_staticbox = wx.StaticBox(self.library_choice_panel, wx.ID_ANY, "Pulse shape library")
        self.scope_pv_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, DEFAULT_SCOPE_PV, style=wx.TE_PROCESS_ENTER)
        self.library_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.grab_trace_button = wx.Button(self, wx.ID_ANY, "Grab")
        self.trc_avg = wx.TextCtrl(self, wx.ID_ANY, "1", style=wx.TE_CENTRE)
        self.trc_avg_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Average")
        self.target_preview_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY))
        self.save_trace_button = wx.BitmapButton(self, wx.ID_ANY, wx.Bitmap("./gui_files/Save.png", wx.BITMAP_TYPE_ANY))
        self.scope_pv_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Scope PV")
        self.scope_start_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "273", style=wx.TE_CENTRE)
        self.scope_length_text_control = wx.TextCtrl(self, wx.ID_ANY, "410", style=wx.TE_CENTRE|wx.TE_READONLY)
        self.scope_slice_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Start point / length")
        self.tgt_src_cb = wx.ComboBox(self, wx.ID_ANY, choices=["Library", "File"], style=wx.CB_READONLY)
        self.src_cb_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Target source")
        self.plength_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "10", style=wx.TE_CENTRE)
        self.plength_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Pulse length (ns)")
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

        # Set windows layout and properties
        self.__set_properties()
        self.__do_layout()
        
        # Event bindings
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
        self.Bind(wx.EVT_CLOSE, self.closeWindow)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_scope_pv, self.scope_pv_text_ctrl)
        self.plength_text_ctrl.Bind(wx.EVT_KILL_FOCUS, self.coerce_pulse_length)
        self.gain_txt_ctrl.Bind(wx.EVT_KILL_FOCUS, self.coerce_value)

        # Instantiate Curve objects to hold data
        self.cBackground = BkgCurve(name = 'Background')
        self.cTargetFile = TargetCurve(name = 'Target')
        self.cTrace = Curve(name = 'Scope') # Used to hold data from a 'grab'
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()

        # Find the library curves
        self.popluate_library_combobox()

        # Create scope pvs and connect
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()
        self.time_resolution_pv_name = self.scope_pv_name.split(':')[0] + ":SetResolution"
        self.time_resolution_pv = epics.PV(self.time_resolution_pv_name)
        self.scope_pv = epics.PV(self.scope_pv_name, connection_callback=self.on_pv_connect)
        if self.scope_pv.connected:
            self.scope_pv_text_ctrl.SetBackgroundColour('#0aff05')
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour('#cc99ff')

        # Load old parameters
        self.load_state()
        

#####################################################################################
# Event handlers
#####################################################################################

    def coerce_pulse_length(self, event):
        desired_length = float(self.plength_text_ctrl.GetValue())
        remainder = desired_length % AWG_NS_PER_POINT
        coerced_length = desired_length - remainder
        self.plength_text_ctrl.SetValue(str(coerced_length))
        # Set the correct slice length
        if not self.time_resolution_pv.connected:
            event.Skip()
            return
        self.scope_length_text_control.SetValue(
            str(int(coerced_length*1e-9/self.time_resolution_pv.get())))
        event.Skip()
    
    def coerce_value(self, event):
        obj = event.GetEventObject()        
        if obj.GetName() == 'gain_ctrl':
            min=0.05
            max=1        
        val = np.clip(float(obj.GetValue()),min,max)
        obj.SetValue(str(val))
        event.Skip()

    @EpicsFunction
    def on_scope_pv(self,event): 
        """ Connects to pv when user hits enter. Uses PyEpics. """
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()
        self.scope_pv = epics.PV(self.scope_pv_name, connection_callback=self.on_pv_connect)
        #Change the colour after connection attempt, and set the on/off pv
        if self.scope_pv.connected:
            self.scope_pv_text_ctrl.SetBackgroundColour('#0aff05')
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour('#cc99ff')
        self.scope_pv_text_ctrl.Refresh()
        event.Skip()


    @DelayedEpicsCallback
    def on_pv_connect(self, pvname=None, conn=None, **kwargs):
        """ Change the colour of the field to reflect connetion status. Uses PyEpics """
        if conn:
            self.scope_pv_text_ctrl.SetBackgroundColour('#0aff05')
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour('#cc99ff')
        self.scope_pv_text_ctrl.Refresh()


    def closeWindow(self, event):
        self.save_state()
        self.Destroy()


    def on_browse(self, event):  

        frame = wx.Frame(None, -1, "Load a curve")

        with wx.FileDialog(frame, "Load Curve",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            fileDialog.ShowModal()
            if fileDialog == wx.ID_CANCEL: return
            pathname = fileDialog.GetPath()

        if event.GetEventObject().GetName() == 'bkg_browse':
            self.bkg_path_text_ctrl.SetValue(pathname)
        elif event.GetEventObject().GetName() == 'tgt_browse':
            self.target_path_text_ctrl.SetValue(pathname)
        frame.Destroy()


    def on_preview(self, event):  
        if event.GetEventObject().GetName() == 'bkg_prv':
            reason = 'bkg'
            curve = self.cBackground
        elif event.GetEventObject().GetName() == 'tgt_prv':
            reason = 'tgt_file'
            curve = self.cTargetFile
        elif event.GetEventObject().GetName() == 'lby_prv':
            reason = 'library'
            curve = self.cTargetFile
        elif event.GetEventObject().GetName() == 'trace_prv':
            reason = 'trace'
            curve = self.cTrace
        err = self.load(reason)
        if err == CODES.NoError:
            curve.plot_processed()
        else:
            self.show_error("Couldn't read the curve", "Preview error")
  
  
    def on_grab_trace(self, event):  
        ''' Grabs a user defined number of traces from the scope'''
        num_to_average = int(self.trc_avg.GetValue())
        datas=[]
        i=0
        self.on_scope_pv(event)
        if self.scope_pv.connected:
            prog = wx.ProgressDialog("Getting scope data", "Reading trace 1", num_to_average)
            while i < num_to_average:
                #data = epics.caget(self.scope_pv_name)
                data = self.scope_pv.get()
                datas.append(data)
                time.sleep(SCOPE_WAIT_TIME)
                i+=1
                prog.Update(i,"Reading trace %d" % (i))                                   
        else:
            self.show_error("Can't connect to scope PV", "Scope read error")
            return

        try:
            result = np.average(np.array(datas),axis=0)
            self.cTrace = Curve(curve_array = result, name = 'Scope')
        except:
            caption = """Scope may not be sending data.
            Check correct PV is connected and that the scope IOC is running"""
            self.show_error(caption, "Error when averaging scope data")


    def on_trace_save(self, event):  
        self.cTrace.save(raw = True)


    def on_go(self, event):  
        gain = float(self.gain_txt_ctrl.GetValue()) 
        num_points = int(float(self.plength_text_ctrl.GetValue())/AWG_NS_PER_POINT)
        start = int(self.scope_start_text_ctrl.GetValue())
        length = int(self.scope_length_text_control.GetValue())
        cropping = (start, start+length)

        # Reload curves
        bkg_loaded = self.load('bkg')
        if bkg_loaded != CODES.NoError:
            self.show_error("Can't load background curve", "File error")
            return
        if self.tgt_src_cb.GetSelection() == 1:
            target_loaded = self.load('tgt_file')
        else:
            target_loaded = self.load('library')

        # Get the latest data for the feedback curve
        if SIMULATION:
            temp=0.5*np.ones(np.size(self.cBackground.get_raw()))
            temp[250:350]=0
            temp[400:500]=0
            start_curve = Curve(curve_array = temp)
            start_curve.process('clip','norm',bkg=self.cBackground,
                crop = cropping , resample = num_points)           
        else:
            if not self.scope_pv.connected:
                self.show_error("Can't connect to scope PV", "Scope read error")
                return

        # Run the loop if files whre succefully loaded
        if bkg_loaded == CODES.NoError and target_loaded == CODES.NoError :
            self.run_loop()
        else:
            self.show_error("Couldn't open the background and/or target files", "File open error")




#####################################################################################
# 
#####################################################################################

    def load(self, reason):
        num_pts = int(float(self.plength_text_ctrl.GetValue())/AWG_NS_PER_POINT)

        if reason == 'bkg':
            pathname = self.bkg_path_text_ctrl.GetValue()
            err = self.cBackground.load(num_points=num_pts, trim_method = 'off', data = str(pathname))
        elif reason == 'tgt_file':
            pathname = self.target_path_text_ctrl.GetValue()
            err = self.cTargetFile.load(num_points=num_pts, trim_method = 'resample', data = str(pathname))
            self.cTargetFile.process('clip','norm', resample = num_pts)
        elif reason == 'library':
            pathname = LIBRARY_FILES_LOCATION + self.library_combo_box.GetStringSelection() + ".curve"
            err = self.cTargetFile.load(num_points=num_pts, trim_method = 'resample', data = str(pathname))
            self.cTargetFile.process('clip','norm', resample = num_pts)
        elif reason == 'trace':
            pass
            err = CODES.NoError
        return err


    def run_loop(self):
        iterations = int(self.iterations_txt_ctrl.GetValue())
        tolerance = float(self.tolerance_txt_ctrl.GetValue())
        max_percent_change = int(self.max_change_txt_ctrl.GetValue())
        gain = float(self.gain_txt_ctrl.GetValue()) 
        pulse_length = float(self.plength_text_ctrl.GetValue())
        start = int(self.scope_start_text_ctrl.GetValue())
        if not SIMULATION:
            length = int(int(pulse_length*1e-9/self.time_resolution_pv.get()))
        else:
            length = int(self.scope_length_text_control.GetValue())
        #length = int(self.scope_length_text_control.GetValue())
        scope_pv = self.scope_pv
        time_res_pv = self.time_resolution_pv
        target = self.cTargetFile
        background = self.cBackground
        save_diag_files = True if self.diag_files_radio_box.GetSelection() == 0 else False
        averages = int(self.trc_avg.GetValue())
        
        self.loop = LoopFrame(self, target, background, pulse_length, start, length, scope_pv, time_res_pv,
                                averages, gain, iterations, tolerance, max_percent_change, save_diag_files)


#####################################################################################
# Utility functions
#####################################################################################

    def save_state(self, filename = './state.txt'):
        config = cp.RawConfigParser()
        config.add_section('Traces')
        config.add_section('Scope')
        config.add_section('Parms')
        config.set('Traces', 'bkg_path', self.bkg_path_text_ctrl.GetValue())
        config.set('Traces', 'tkg_path', self.target_path_text_ctrl.GetValue())
        config.set('Traces', 'lib_index', self.library_combo_box.GetCurrentSelection())
        config.set('Scope', 'scope_pv', self.scope_pv_text_ctrl.GetValue())
        config.set('Scope', 'averages', self.trc_avg.GetValue())
        config.set('Scope', 'start', self.scope_start_text_ctrl.GetValue()) 
        config.set('Scope', 'length', self.scope_length_text_control.GetValue()) 
        config.set('Parms', 'tgt_src', self.tgt_src_cb.GetSelection())
        config.set('Parms', 'pulse_length', self.plength_text_ctrl.GetValue())
        config.set('Parms', 'gain', self.gain_txt_ctrl.GetValue())
        config.set('Parms', 'iterations', self.iterations_txt_ctrl.GetValue())
        config.set('Parms', 'tolerance', self.tolerance_txt_ctrl.GetValue())
        config.set('Parms', 'max_change', self.max_change_txt_ctrl.GetValue())
        config.set('Parms', 'save_files', self.diag_files_radio_box.GetSelection())

        with open(filename, 'w') as configfile:
            config.write(configfile)

    def load_state(self, filename = './state.txt'):
        config = cp.RawConfigParser()
        config.read(filename)
        try:
            self.bkg_path_text_ctrl.SetValue(config.get('Traces', 'bkg_path')) 
            self.target_path_text_ctrl.SetValue(config.get('Traces', 'tkg_path'))              
            self.scope_pv_text_ctrl.SetValue(config.get('Scope', 'scope_pv')) 
            self.trc_avg.SetValue(config.get('Scope', 'averages')) 
            self.scope_start_text_ctrl.SetValue(config.get('Scope', 'start')) 
            self.scope_length_text_control.SetValue(config.get('Scope', 'length')) 
            self.tgt_src_cb.SetSelection(config.getint('Parms', 'tgt_src')) 
            self.plength_text_ctrl.SetValue(config.get('Parms', 'pulse_length')) 
            self.gain_txt_ctrl.SetValue(config.get('Parms', 'gain')) 
            self.iterations_txt_ctrl.SetValue(config.get('Parms', 'iterations')) 
            self.tolerance_txt_ctrl.SetValue(config.get('Parms', 'tolerance')) 
            self.max_change_txt_ctrl.SetValue(config.get('Parms', 'max_change')) 
            self.diag_files_radio_box.SetSelection(config.getint('Parms', 'save_files'))
            self.library_combo_box.SetSelection(config.getint('Traces', 'lib_index'))
        except:
            pass
       
    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap,
            style=wx.ICON_ERROR)
        err.ShowModal()

    def popluate_library_combobox(self):
        try:
            files = os.listdir(LIBRARY_FILES_LOCATION)
            for f in files:
                pieces = f.split('.')
                if pieces[1] == 'curve':
                    self.library_combo_box.Append(pieces[0])
        except:
            pass
    
    def __set_properties(self):
        _title = "Beam profiling simulation" if SIMULATION == True else "Beam Profiling"
        self.SetTitle(_title)
        self.SetSize((1049, 447))
        self.SetBackgroundColour('#f1f1f1')
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
        self.diag_files_radio_box.SetSelection(0)
        self.go_button.SetBackgroundColour(wx.Colour(10, 255, 5))
        self.go_button.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.bkg_preview_button.SetName('bkg_prv')
        self.bkg_browse_button.SetName('bkg_browse')
        self.target_browse_button.SetName('tgt_browse')
        self.target_preview_button.SetName('tgt_prv')
        self.library_preview_button.SetName('lby_prv')
        self.trace_preview_button.SetName('trace_prv')
        self.gain_txt_ctrl.SetName('gain_ctrl')

    def __do_layout(self):
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
        self.plength_szr_staticbox.Lower()
        point_szr = wx.StaticBoxSizer(self.plength_szr_staticbox, wx.HORIZONTAL)
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
        point_szr.Add(self.plength_text_ctrl, 1, wx.EXPAND, 0)
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

        