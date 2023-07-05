import matplotlib

matplotlib.use("WXAgg")
from fileEditor import FileEditDialog
from curve import Curve, BkgCurve, TargetCurve
import numpy as np
import wx, time, os, sys
from util import CODES
from loopframe import LoopFrame

if sys.version_info[0] < 3:
    import ConfigParser as cp
else:
    import configparser as cp

import epics
from epics.wx import EpicsFunction, DelayedEpicsCallback


class SetupFrame(wx.Frame):
    def __init__(self, config, **kwargs):
        wx.Frame.__init__(self, **kwargs)  # , pos=wx.Point(50,50)) # *args, **kwds)
        self.config = config
        self.bkg_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.bkg_path_text_ctrl = wx.TextCtrl(
            self.bkg_choice_panel, wx.ID_ANY, "Path to background file"
        )
        self.bkg_browse_button = wx.BitmapButton(
            self.bkg_choice_panel,
            wx.ID_ANY,
            wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY),
        )
        self.bkgfile_sizer_staticbox = wx.StaticBox(
            self.bkg_choice_panel, wx.ID_ANY, "Background file"
        )
        self.bkg_preview_button = wx.BitmapButton(
            self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY)
        )
        self.target_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.target_path_text_ctrl = wx.TextCtrl(
            self.target_choice_panel, wx.ID_ANY, "Path to target file"
        )
        self.target_browse_button = wx.BitmapButton(
            self.target_choice_panel,
            wx.ID_ANY,
            wx.Bitmap("./gui_files/Open folder.png", wx.BITMAP_TYPE_ANY),
        )
        self.target_file_sizer_staticbox = wx.StaticBox(
            self.target_choice_panel, wx.ID_ANY, "Target file"
        )
        self.trace_preview_button = wx.BitmapButton(
            self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY)
        )
        self.library_choice_panel = wx.Panel(self, wx.ID_ANY)
        self.library_combo_box = wx.ComboBox(
            self.library_choice_panel,
            wx.ID_ANY,
            choices=[],
            style=wx.CB_READONLY | wx.CB_SORT,
        )
        self.library_file_sizer_staticbox = wx.StaticBox(
            self.library_choice_panel, wx.ID_ANY, "Pulse shape library"
        )
        self.scope_pv_text_ctrl = wx.TextCtrl(
            self, wx.ID_ANY, self.config.getVal("scope"), style=wx.TE_PROCESS_ENTER
        )
        self.library_preview_button = wx.BitmapButton(
            self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY)
        )
        self.grab_trace_button = wx.Button(self, wx.ID_ANY, "Grab")
        self.trc_avg = wx.TextCtrl(self, wx.ID_ANY, "1", style=wx.TE_CENTRE)
        self.trc_avg_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Average")
        self.target_preview_button = wx.BitmapButton(
            self, wx.ID_ANY, wx.Bitmap("./gui_files/preview.png", wx.BITMAP_TYPE_ANY)
        )
        self.save_trace_button = wx.BitmapButton(
            self, wx.ID_ANY, wx.Bitmap("./gui_files/Save.png", wx.BITMAP_TYPE_ANY)
        )
        self.scope_pv_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Scope PV")
        self.scope_start_text_ctrl = wx.TextCtrl(
            self, wx.ID_ANY, "273", style=wx.TE_CENTRE
        )
        self.scope_length_text_control = wx.TextCtrl(
            self, wx.ID_ANY, "410", style=wx.TE_CENTRE | wx.TE_READONLY
        )
        self.scope_slice_sizer_staticbox = wx.StaticBox(
            self, wx.ID_ANY, "Start point / length"
        )
        self.tgt_src_cb = wx.ComboBox(
            self, wx.ID_ANY, choices=["Library", "File"], style=wx.CB_READONLY
        )
        self.src_cb_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Target source")
        self.plength_text_ctrl = wx.TextCtrl(self, wx.ID_ANY, "10", style=wx.TE_CENTRE)
        self.plength_szr_staticbox = wx.StaticBox(self, wx.ID_ANY, "Pulse length (ns)")
        self.gain_txt_ctrl = wx.TextCtrl(self, wx.ID_ANY, "0.1", style=wx.TE_CENTRE)
        self.gain_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Gain")
        self.iterations_txt_ctrl = wx.TextCtrl(
            self, wx.ID_ANY, "10", style=wx.TE_CENTRE
        )
        self.iterations_sizer_staticbox = wx.StaticBox(
            self, wx.ID_ANY, "Max iterations"
        )
        self.tolerance_txt_ctrl = wx.TextCtrl(
            self, wx.ID_ANY, ".01", style=wx.TE_CENTRE
        )
        self.tolerance_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Tolerance")
        self.max_change_txt_ctrl = wx.TextCtrl(
            self, wx.ID_ANY, "25", style=wx.TE_CENTRE
        )
        self.max_change_sizer_staticbox = wx.StaticBox(self, wx.ID_ANY, "Max % change")
        self.diag_files_radio_box = wx.RadioBox(
            self,
            wx.ID_ANY,
            "Save files?",
            choices=["Yes", "No"],
            majorDimension=2,
            style=wx.RA_SPECIFY_COLS,
        )
        self.go_button = wx.Button(self, wx.ID_ANY, "Go")

        # Set windows layout and properties
        self.__set_properties()
        self.__do_layout()

        # Event bindings
        self.Bind(wx.EVT_MENU, self.onConfig, self.configMenuItem)
        self.Bind(wx.EVT_MENU, self.onFilter, self.filterMenuItem)
        self.Bind(wx.EVT_MENU, self.onAlgorithm, self.algorithmMenuItem)
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
        self.gain_txt_ctrl.Bind(wx.EVT_KILL_FOCUS, self.coerce_gain)
        self.tolerance_txt_ctrl.Bind(wx.EVT_KILL_FOCUS, self.coerce_tolerance)
        self.max_change_txt_ctrl.Bind(
            wx.EVT_KILL_FOCUS, self.coerce_max_percentage_change
        )
        self.iterations_txt_ctrl.Bind(wx.EVT_KILL_FOCUS, self.coerce_iterations)

        # Instantiate Curve objects to hold data
        self.background_curve = BkgCurve(name="Background")
        self.target_curve = TargetCurve(name="Target")
        self.scope_curve = Curve(name="Scope")  # Used to hold data from a 'grab'

        # Load old parameters
        self.load_state()

        # Create scope pvs and connect
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()
        self.scope_pv = epics.PV(
            self.scope_pv_name, connection_callback=self.on_pv_connect
        )
        if self.scope_pv.connected:
            self.scope_pv_text_ctrl.SetBackgroundColour("#0aff05")
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour("#cc99ff")
        self.time_resolution_pv_name = (
            self.scope_pv_name.split(":")[0] + ":SetResolution"
        )
        self.time_resolution_pv = epics.PV(self.time_resolution_pv_name)

        # Trigger event handler with dummy event so initial presented values are correct
        self.coerce_pulse_length(wx.CommandEvent())

        # Final touches to UI depending on configuration settings
        self.populate_library_combobox()
        self.setUIforAutoLoop()

    #####################################################################################
    # Event handlers
    #####################################################################################

    def onConfig(self, event):
        apply = self.config.ShowModal()
        if apply:
            # Config folder may have changed
            self.populate_library_combobox()
            # May have switched simulation mode
            self.setTitle()
            # In case autolooping has changed
            self.setUIforAutoLoop()

    def onFilter(self, event):
        dlg = FileEditDialog(None, self.config.getVal("filter"))
        dlg.ShowModal()

    def onAlgorithm(self, event):
        dlg = FileEditDialog(None, self.config.getVal("algorithm"))
        dlg.ShowModal()

    def coerce_pulse_length(self, event):
        desired_length = float(self.plength_text_ctrl.GetValue())
        remainder = desired_length % self.config.getVal("awg_ns_per_point")
        coerced_length = desired_length - remainder
        self.plength_text_ctrl.SetValue(str(coerced_length))
        # Set the correct slice length
        if self.time_resolution_pv.connected:
            self.scope_length_text_control.SetValue(
                str(int(coerced_length * 1e-9 / self.time_resolution_pv.get()))
            )
        else:
            print(f"PV {self.time_resolution_pv_name} is not connected")
        event.Skip()

    def coerce_gain(self, event):
        minimum = 0.05
        maximum = 1
        obj = event.GetEventObject()
        try:
            gain = np.clip(float(obj.GetValue()), minimum, maximum)
        except:
            self.show_error(
                "Gain must be number between {0:.2f} and {1:.2f}".format(
                    minimum, maximum
                ),
                "Value error",
            )
            gain = 0.5
        obj.SetValue(str(gain))
        event.Skip()

    def coerce_iterations(self, event):
        minimum = 1
        obj = event.GetEventObject()
        try:
            # Read as float and convert to int to allow scientific notation
            iterations = int(max(minimum, float(obj.GetValue())))
        except:
            self.show_error(
                "Iterations must be number >= {0:d}".format(minimum), "Value error"
            )
            iterations = minimum
        obj.SetValue(str(iterations))
        event.Skip()

    def coerce_tolerance(self, event):
        minimum = 0.01
        obj = event.GetEventObject()
        try:
            tolerance = float(max(minimum, float(obj.GetValue())))
        except:
            self.show_error(
                "Tolerance must be number >= {0:.2f}".format(minimum), "Value error"
            )
            tolerance = minimum
        obj.SetValue(str(tolerance))
        event.Skip()

    def coerce_max_percentage_change(self, event):
        minimum = 1
        maximum = 100
        obj = event.GetEventObject()
        try:
            change = np.clip(int(obj.GetValue()), minimum, maximum)
        except:
            self.show_error(
                "Max percentage change must be number between {0:d} and {1:d}".format(
                    minimum, maximum
                ),
                "Value error",
            )
            change = 25
        obj.SetValue(str(change))
        event.Skip()

    @EpicsFunction
    def on_scope_pv(self, event):
        """Connects to pv when user hits enter. Uses PyEpics."""
        self.scope_pv_name = self.scope_pv_text_ctrl.GetValue().strip()
        self.scope_pv = epics.PV(
            self.scope_pv_name, connection_callback=self.on_pv_connect
        )
        # Change the colour after connection attempt, and set the on/off pv
        if self.scope_pv.connected:
            self.scope_pv_text_ctrl.SetBackgroundColour("#0aff05")
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour("#cc99ff")
        self.time_resolution_pv_name = (
            self.scope_pv_name.split(":")[0] + ":SetResolution"
        )
        self.scope_pv_text_ctrl.Refresh()
        event.Skip()

    @DelayedEpicsCallback
    def on_pv_connect(self, pvname=None, conn=None, **kwargs):
        """Change the colour of the field to reflect connetion status. Uses PyEpics"""
        if conn:
            self.scope_pv_text_ctrl.SetBackgroundColour("#0aff05")
        else:
            self.scope_pv_text_ctrl.SetBackgroundColour("#cc99ff")
        self.scope_pv_text_ctrl.Refresh()

    def closeWindow(self, event):
        self.save_state()
        self.config.Destroy()
        self.Destroy()

    def on_browse(self, event):
        frame = wx.Frame(None, -1, "Load a curve")

        with wx.FileDialog(
            frame, "Load Curve", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:
            fileDialog.ShowModal()
            if fileDialog == wx.ID_CANCEL:
                return
            pathname = fileDialog.GetPath()

        if event.GetEventObject().GetName() == "bkg_browse":
            self.bkg_path_text_ctrl.SetValue(pathname)
        elif event.GetEventObject().GetName() == "tgt_browse":
            self.target_path_text_ctrl.SetValue(pathname)
        frame.Destroy()

    def on_preview(self, event):
        if event.GetEventObject().GetName() == "bkg_prv":
            reason = "bkg"
            curve = self.background_curve
        elif event.GetEventObject().GetName() == "tgt_prv":
            reason = "tgt_file"
            curve = self.target_curve
        elif event.GetEventObject().GetName() == "lby_prv":
            reason = "library"
            curve = self.target_curve
        elif event.GetEventObject().GetName() == "trace_prv":
            reason = "trace"
            curve = self.scope_curve
        err = self.load(reason)
        if err == CODES.NoError:
            curve.plot_processed()
        else:
            self.show_error("Couldn't read the curve", "Preview error")

    def on_grab_trace(self, event):
        """Grabs a user defined number of traces from the scope"""
        num_to_average = int(self.trc_avg.GetValue())
        datas = []
        i = 0
        self.on_scope_pv(event)
        if self.scope_pv.connected:
            prog = wx.ProgressDialog(
                "Getting scope data", "Reading trace 1", num_to_average
            )
            while i < num_to_average:
                data = self.scope_pv.get()
                datas.append(data)
                time.sleep(self.config.getVal("scope_wait"))
                i += 1
                prog.Update(i, "Reading trace %d" % (i))
        else:
            self.show_error("Can't connect to scope PV", "Scope read error")
            return

        try:
            result = np.average(np.array(datas), axis=0)
            self.scope_curve = Curve(curve_array=result, name="Scope")
        except:
            caption = """Scope may not be sending data.
            Check correct PV is connected and that the scope IOC is running"""
            self.show_error(caption, "Error when averaging scope data")

    def on_trace_save(self, event):
        self.scope_curve.save(raw=True)

    def on_go(self, event):
        num_points = int(
            float(self.plength_text_ctrl.GetValue())
            / self.config.getVal("awg_ns_per_point")
        )
        start = int(self.scope_start_text_ctrl.GetValue())
        length = int(self.scope_length_text_control.GetValue())
        cropping = (start, start + length)

        # Reload curves
        bkg_loaded = self.load("bkg")
        if bkg_loaded != CODES.NoError:
            self.show_error("Can't load background curve", "File error")
            return
        if self.tgt_src_cb.GetSelection() == 1:
            target_loaded = self.load("tgt_file")
        else:
            target_loaded = self.load("library")

        # Get the latest data for the feedback curve
        if self.config.getVal("sim") == True:
            temp = 0.5 * np.ones(np.size(self.background_curve.get_raw()))
            temp[250:350] = 0
            temp[400:500] = 0
            start_curve = Curve(curve_array=temp)
            start_curve.process(
                "clip",
                "norm",
                bkg=self.background_curve,
                crop=cropping,
                resample=num_points,
            )
        else:
            if not self.scope_pv.connected:
                self.show_error("Can't connect to scope PV", "Scope read error")
                return

        # Run the loop if files whre succefully loaded
        if bkg_loaded == CODES.NoError and target_loaded == CODES.NoError:
            self.run_loop()
        else:
            self.show_error(
                "Couldn't open the background and/or target files", "File open error"
            )

    #####################################################################################
    #
    #####################################################################################

    def load(self, reason):
        num_pts = int(
            float(self.plength_text_ctrl.GetValue())
            / self.config.getVal("awg_ns_per_point")
        )

        if reason == "bkg":
            pathname = self.bkg_path_text_ctrl.GetValue()
            err = self.background_curve.load(
                num_points=num_pts, trim_method="off", data=str(pathname)
            )
        elif reason == "tgt_file":
            pathname = self.target_path_text_ctrl.GetValue()
            err = self.target_curve.load(
                num_points=num_pts, trim_method="resample", data=str(pathname)
            )
            self.target_curve.process("clip", "norm", resample=num_pts)
        elif reason == "library":
            pathname = (
                self.config.getVal("curve")
                + self.library_combo_box.GetStringSelection()
                + ".curve"
            )
            err = self.target_curve.load(
                num_points=num_pts, trim_method="resample", data=str(pathname)
            )
            self.target_curve.process("clip", "norm", resample=num_pts)
        elif reason == "trace":
            pass
            err = CODES.NoError
        return err

    def run_loop(self):
        try:
            if self.config.getVal("auto_loop") == True:
                iterations = int(self.iterations_txt_ctrl.GetValue())
                tolerance = float(self.tolerance_txt_ctrl.GetValue())
            else:
                # Dummy values - these are ignored when not autolooping
                iterations = 200
                tolerance = 0
            max_percent_change = int(self.max_change_txt_ctrl.GetValue())
            gain = float(self.gain_txt_ctrl.GetValue())
            pulse_length = float(self.plength_text_ctrl.GetValue())
            start = int(self.scope_start_text_ctrl.GetValue())
            averages = int(self.trc_avg.GetValue())
            if not self.config.getVal("sim"):
                length = int(pulse_length * 1e-9 / self.time_resolution_pv.get())
            else:
                length = int(self.scope_length_text_control.GetValue())
        except:
            self.show_error("Check parameters are all valid numbers", "Value error")
            return

        self.config.setVal("scope_pv", self.scope_pv)
        self.config.setVal("time_res_pv", self.time_resolution_pv)
        self.config.setVal("target", self.target_curve)
        self.config.setVal("background", self.background_curve)
        self.config.setVal(
            "save_diag_files", self.diag_files_radio_box.GetSelection() == 0
        )
        self.config.setVal("iterations", iterations)
        self.config.setVal("tolerance", tolerance)
        self.config.setVal("max_percentage_change", max_percent_change)
        self.config.setVal("gain", gain)
        self.config.setVal("pulse_length", pulse_length)
        self.config.setVal("start", start)
        self.config.setVal("averages", averages)
        self.config.setVal("length", length)

        self.loop = LoopFrame(self, self.config)

    #####################################################################################
    # Utility functions
    #####################################################################################

    def save_state(self, filename="./state.txt"):
        config_parser = cp.RawConfigParser()
        config_parser.add_section("Traces")
        config_parser.add_section("Scope")
        config_parser.add_section("Parms")
        config_parser.set("Traces", "bkg_path", self.bkg_path_text_ctrl.GetValue())
        config_parser.set("Traces", "tkg_path", self.target_path_text_ctrl.GetValue())
        config_parser.set(
            "Traces", "lib_index", self.library_combo_box.GetCurrentSelection()
        )
        config_parser.set("Scope", "scope_pv", self.scope_pv_text_ctrl.GetValue())
        config_parser.set("Scope", "averages", self.trc_avg.GetValue())
        config_parser.set("Scope", "start", self.scope_start_text_ctrl.GetValue())
        config_parser.set("Scope", "length", self.scope_length_text_control.GetValue())
        config_parser.set("Parms", "tgt_src", self.tgt_src_cb.GetSelection())
        config_parser.set("Parms", "pulse_length", self.plength_text_ctrl.GetValue())
        config_parser.set("Parms", "gain", self.gain_txt_ctrl.GetValue())
        config_parser.set("Parms", "iterations", self.iterations_txt_ctrl.GetValue())
        config_parser.set("Parms", "tolerance", self.tolerance_txt_ctrl.GetValue())
        config_parser.set("Parms", "max_change", self.max_change_txt_ctrl.GetValue())
        config_parser.set(
            "Parms", "save_files", self.diag_files_radio_box.GetSelection()
        )

        with open(filename, "w") as configfile:
            config_parser.write(configfile)

    def load_state(self, filename="./state.txt"):
        config_parser = cp.RawConfigParser()
        config_parser.read(filename)
        try:
            self.bkg_path_text_ctrl.SetValue(config_parser.get("Traces", "bkg_path"))
            self.target_path_text_ctrl.SetValue(config_parser.get("Traces", "tkg_path"))
            self.scope_pv_text_ctrl.SetValue(config_parser.get("Scope", "scope_pv"))
            self.trc_avg.SetValue(config_parser.get("Scope", "averages"))
            self.scope_start_text_ctrl.SetValue(config_parser.get("Scope", "start"))
            self.scope_length_text_control.SetValue(
                config_parser.get("Scope", "length")
            )
            self.tgt_src_cb.SetSelection(config_parser.getint("Parms", "tgt_src"))
            self.plength_text_ctrl.SetValue(config_parser.get("Parms", "pulse_length"))
            self.gain_txt_ctrl.SetValue(config_parser.get("Parms", "gain"))
            self.iterations_txt_ctrl.SetValue(config_parser.get("Parms", "iterations"))
            self.tolerance_txt_ctrl.SetValue(config_parser.get("Parms", "tolerance"))
            self.max_change_txt_ctrl.SetValue(config_parser.get("Parms", "max_change"))
            self.diag_files_radio_box.SetSelection(
                config_parser.getint("Parms", "save_files")
            )
            self.library_combo_box.SetSelection(
                config_parser.getint("Traces", "lib_index")
            )
        except:
            pass

    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap, style=wx.ICON_ERROR)
        err.ShowModal()

    def populate_library_combobox(self):
        self.library_combo_box.Clear()
        try:
            files = os.listdir(self.config.getVal("curve"))
            for f in files:
                pieces = f.split(".")
                if pieces[-1] == "curve":
                    self.library_combo_box.Append(pieces[0])
            self.library_combo_box.SetSelection(0)
        except:
            pass

    def setTitle(self):
        title = (
            "Beam Profiling (simulation)"
            if self.config.getVal("sim") == True
            else "Beam Profiling"
        )
        self.SetTitle(title)

    def setUIforAutoLoop(self):
        # When not autolooping, max iterations and tolerance aren't used
        if self.config.getVal("auto_loop") == False:
            self.iterations_txt_ctrl.Disable()
            self.iterations_txt_ctrl.SetValue("N/A")
            self.tolerance_txt_ctrl.Disable()
            self.tolerance_txt_ctrl.SetValue("N/A")
        else:
            self.iterations_txt_ctrl.Enable()
            self.tolerance_txt_ctrl.Enable()
            if self.iterations_txt_ctrl.GetValue() == "N/A":
                self.iterations_txt_ctrl.SetValue("30")
                self.tolerance_txt_ctrl.SetValue("0.05")

    def __set_properties(self):
        self.setTitle()
        self.SetSize((1049, 447))
        self.SetBackgroundColour("#f1f1f1")
        self.bkg_browse_button.SetSize(self.bkg_browse_button.GetBestSize())
        self.bkg_browse_button.SetDefault()
        self.bkg_preview_button.SetSize(self.bkg_preview_button.GetBestSize())
        self.bkg_preview_button.SetDefault()
        self.target_browse_button.SetSize(self.target_browse_button.GetBestSize())
        self.target_browse_button.SetDefault()
        self.trace_preview_button.SetSize(self.trace_preview_button.GetBestSize())
        self.trace_preview_button.SetDefault()
        self.library_combo_box.SetFont(
            wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "Ubuntu")
        )
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
        self.bkg_preview_button.SetName("bkg_prv")
        self.bkg_browse_button.SetName("bkg_browse")
        self.target_browse_button.SetName("tgt_browse")
        self.target_preview_button.SetName("tgt_prv")
        self.library_preview_button.SetName("lby_prv")
        self.trace_preview_button.SetName("trace_prv")
        self.gain_txt_ctrl.SetName("gain_ctrl")

    def __do_layout(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        loop_szr = wx.BoxSizer(wx.HORIZONTAL)
        loop_settings_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.max_change_sizer_staticbox.Lower()
        max_change_sizer = wx.StaticBoxSizer(
            self.max_change_sizer_staticbox, wx.HORIZONTAL
        )
        self.tolerance_sizer_staticbox.Lower()
        tolerance_sizer = wx.StaticBoxSizer(
            self.tolerance_sizer_staticbox, wx.HORIZONTAL
        )
        self.iterations_sizer_staticbox.Lower()
        iterations_sizer = wx.StaticBoxSizer(
            self.iterations_sizer_staticbox, wx.HORIZONTAL
        )
        self.gain_sizer_staticbox.Lower()
        gain_sizer = wx.StaticBoxSizer(self.gain_sizer_staticbox, wx.HORIZONTAL)
        scope_szr = wx.BoxSizer(wx.HORIZONTAL)
        tgt_src_szr = wx.BoxSizer(wx.HORIZONTAL)
        self.plength_szr_staticbox.Lower()
        point_szr = wx.StaticBoxSizer(self.plength_szr_staticbox, wx.HORIZONTAL)
        self.src_cb_szr_staticbox.Lower()
        src_cb_szr = wx.StaticBoxSizer(self.src_cb_szr_staticbox, wx.HORIZONTAL)
        self.scope_slice_sizer_staticbox.Lower()
        scope_slice_sizer = wx.StaticBoxSizer(
            self.scope_slice_sizer_staticbox, wx.HORIZONTAL
        )
        self.scope_pv_szr_staticbox.Lower()
        scope_pv_szr = wx.StaticBoxSizer(self.scope_pv_szr_staticbox, wx.HORIZONTAL)
        self.trc_avg_szr_staticbox.Lower()
        trc_avg_szr = wx.StaticBoxSizer(self.trc_avg_szr_staticbox, wx.HORIZONTAL)
        library_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.library_file_sizer_staticbox.Lower()
        library_file_sizer = wx.StaticBoxSizer(
            self.library_file_sizer_staticbox, wx.HORIZONTAL
        )
        target_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.target_file_sizer_staticbox.Lower()
        target_file_sizer = wx.StaticBoxSizer(
            self.target_file_sizer_staticbox, wx.HORIZONTAL
        )
        bkg_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bkgfile_sizer_staticbox.Lower()
        bkgfile_sizer = wx.StaticBoxSizer(self.bkgfile_sizer_staticbox, wx.HORIZONTAL)
        bkgfile_sizer.Add(self.bkg_path_text_ctrl, 2, wx.EXPAND, 0)
        bkgfile_sizer.Add(self.bkg_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.bkg_choice_panel.SetSizer(bkgfile_sizer)
        bkg_sizer.Add(self.bkg_choice_panel, 2, wx.EXPAND, 0)
        bkg_sizer.Add((20, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        bkg_sizer.Add(self.bkg_preview_button, 0, wx.EXPAND, 0)
        main_sizer.Add((20, 10), 0, 0, 0)
        main_sizer.Add(bkg_sizer, 1, wx.EXPAND, 0)
        main_sizer.Add((20, 10), 0, 0, 0)
        target_file_sizer.Add(self.target_path_text_ctrl, 2, wx.EXPAND, 0)
        target_file_sizer.Add(self.target_browse_button, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.target_choice_panel.SetSizer(target_file_sizer)
        target_sizer.Add(self.target_choice_panel, 2, wx.EXPAND, 0)
        target_sizer.Add((20, 20), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        target_sizer.Add(self.target_preview_button, 0, wx.EXPAND, 0)
        main_sizer.Add(target_sizer, 1, wx.EXPAND, 0)
        main_sizer.Add((20, 10), 0, 0, 0)
        library_file_sizer.Add(self.library_combo_box, 4, wx.EXPAND, 0)
        self.library_choice_panel.SetSizer(library_file_sizer)
        library_sizer.Add(self.library_choice_panel, 2, wx.EXPAND, 0)
        library_sizer.Add((20, 10), 0, wx.ALIGN_CENTER_VERTICAL, 0)
        library_sizer.Add(self.library_preview_button, 0, wx.EXPAND, 0)
        main_sizer.Add(library_sizer, 1, wx.EXPAND, 0)
        main_sizer.Add((500, 10), 0, 0, 0)
        scope_pv_szr.Add(self.scope_pv_text_ctrl, 2, wx.EXPAND, 0)
        scope_pv_szr.Add(self.grab_trace_button, 0, wx.EXPAND, 0)
        trc_avg_szr.Add(self.trc_avg, 0, wx.EXPAND, 0)
        scope_pv_szr.Add(trc_avg_szr, 0, wx.EXPAND, 0)
        scope_pv_szr.Add(self.trace_preview_button, 0, wx.EXPAND, 0)
        scope_pv_szr.Add(self.save_trace_button, 0, wx.EXPAND, 0)
        scope_szr.Add(scope_pv_szr, 3, wx.EXPAND, 0)
        scope_slice_sizer.Add(self.scope_start_text_ctrl, 1, wx.EXPAND, 0)
        scope_slice_sizer.Add(self.scope_length_text_control, 1, wx.EXPAND, 0)
        scope_szr.Add(scope_slice_sizer, 1, wx.EXPAND, 0)
        tgt_src_szr.Add((10, 20), 0, 0, 0)
        src_cb_szr.Add(self.tgt_src_cb, 1, wx.EXPAND, 0)
        tgt_src_szr.Add(src_cb_szr, 1, wx.EXPAND, 0)
        tgt_src_szr.Add((10, 20), 0, 0, 0)
        point_szr.Add(self.plength_text_ctrl, 1, wx.EXPAND, 0)
        tgt_src_szr.Add(point_szr, 1, wx.EXPAND, 0)
        scope_szr.Add(tgt_src_szr, 1, 0, 0)
        main_sizer.Add(scope_szr, 1, wx.EXPAND, 0)
        main_sizer.Add((500, 30), 0, 0, 0)
        gain_sizer.Add(self.gain_txt_ctrl, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(gain_sizer, 1, wx.BOTTOM | wx.EXPAND | wx.RIGHT, 0)
        iterations_sizer.Add(self.iterations_txt_ctrl, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(iterations_sizer, 1, wx.EXPAND, 0)
        tolerance_sizer.Add(self.tolerance_txt_ctrl, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(tolerance_sizer, 1, wx.EXPAND, 0)
        max_change_sizer.Add(self.max_change_txt_ctrl, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(max_change_sizer, 1, wx.EXPAND, 0)
        loop_settings_sizer.Add(self.diag_files_radio_box, 0, wx.EXPAND, 0)
        loop_szr.Add(loop_settings_sizer, 4, wx.ALL | wx.EXPAND, 0)
        loop_szr.Add(self.go_button, 1, wx.EXPAND, 0)
        main_sizer.Add(loop_szr, 1, wx.EXPAND, 0)

        menuBar = wx.MenuBar()
        settingsMenu = wx.Menu()
        self.configMenuItem = settingsMenu.Append(
            wx.NewId(), "Configure", "Edit configuration"
        )
        self.filterMenuItem = settingsMenu.Append(
            wx.NewId(), "Edit filter", "Open filter file for editing"
        )
        self.algorithmMenuItem = settingsMenu.Append(
            wx.NewId(), "Edit algorithm", "Open algorithm file for editing"
        )
        menuBar.Append(settingsMenu, "&Settings")

        self.SetMenuBar(menuBar)

        self.SetSizer(main_sizer)
        self.Layout()
