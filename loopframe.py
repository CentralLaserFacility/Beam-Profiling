from util import get_message_time, CODES, RedirectText
from awg import Awg
import matplotlib

matplotlib.use("WXAgg")
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx as NavigationToolbar
import time, math, pylab, wx, sys, importlib, os
import numpy as np
import epics
from datetime import datetime
import matplotlib.pyplot as plt
from curve import Curve
from loopControlDialog import LoopControlDialog


class LoopFrame(wx.Frame):
    """Class to run the loop. It launches a new window"""

    def __init__(self, parent, config):
        # A bit of work to position this window below the main setup window
        parent_x, parent_y = parent.GetPosition().Get()
        parent_height = parent.GetSize().GetHeight()
        position = wx.Point(parent_x, parent_y + parent_height)
        title = "Loop (simulation)" if config.getVal("sim") == True else "Loop"

        wx.Frame.__init__(self, parent, size=(1000, 400), title=title, pos=position)
        self.parent = parent

        # Set up the parameters for the AWG and the loop
        self.config = config
        self.import_awg_filter()
        self.import_correction_algorithm()
        self.sim = config.getVal("sim")
        self.auto_loop = config.getVal("auto_loop")
        self.auto_loop_wait = config.getVal("auto_loop_wait")
        self.awg_zero_shift = config.getVal("awg_zero_shift")
        self.pulse_peak_power = config.getVal("pulse_peak_power")
        self.noise_threshold_percentage = config.getVal("noise_threshold_percentage")
        self.target = config.getVal("target").get_processed()
        self.target = self.target / np.max(self.target)  # Normalise
        self.background = config.getVal("background")
        self.pulse_length = config.getVal("pulse_length")
        self.slice_start = config.getVal("start")
        self.slice_length = config.getVal("length")
        self.scope_pv = config.getVal("scope_pv")
        self.time_resolution_pv = config.getVal("time_res_pv")
        self.time_res = self.time_resolution_pv.get()
        self.scope_averages = config.getVal("averages")
        self.gain = config.getVal("gain")
        self.iterations = config.getVal("iterations")
        self.tolerance = config.getVal("tolerance")
        self.max_percent_change = config.getVal("max_percentage_change")
        self.save_diag_files = config.getVal("save_diag_files")
        self.num_points = int(
            float(self.pulse_length / config.getVal("awg_ns_per_point"))
        )
        self.i = 0  # Store the loop count for stopping/restarting loop
        self.update_feedback_curve()

        if self.sim == True:
            self.current_output = self.simulate_start_data()
        self.correction_factor = np.zeros(len(self.current_output))
        self.awg = Awg(self.config, self.num_points, self.max_percent_change)

        # Create a panel to hold a log output
        log_panel = wx.Panel(self, wx.ID_ANY)
        log = wx.TextCtrl(
            log_panel,
            size=(1000, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(log, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        log_panel.SetSizer(sizer)

        # Point stdout to the log window
        log_stream = RedirectText(log)
        self.standard_stdout = sys.stdout
        sys.stdout = log_stream

        # Canvas to hold the plots
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.init_plot()
        self.canvas = FigCanvas(self, -1, self.fig)
        self.add_toolbar()

        # Add canvas and log window to sizer. Add stop button if auto-looping.
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.hbox.Add(log_panel, 5, flag=wx.LEFT | wx.TOP | wx.GROW)
        if self.auto_loop == True:
            # Add a stop button for breaking out of auto-loop
            self.add_stop_button()
        else:
            # Used to restart a paused loop
            self.add_continue_button()
        self.stop_loop = False
        self.vbox.Add(self.hbox, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.vbox)
        self.vbox.Fit(self)

        # Draw the window and display
        self.draw_plots()
        # Stop the user launching another loop window until this one is closed
        self.parent.Disable()
        self.parent.SetTransparent(120)
        self.Show()
        self.run_loop()
        self.Bind(wx.EVT_CLOSE, self.close_window)

    def add_stop_button(self):
        self.stop_button = wx.Button(self, wx.ID_ANY, "Stop")
        self.stop_button.SetBackgroundColour(wx.Colour(255, 40, 40))
        self.stop_button.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.stop_button)
        self.hbox.Add(self.stop_button, 1, flag=wx.LEFT | wx.TOP | wx.GROW)

    def add_continue_button(self):
        self.continue_button = wx.Button(self, wx.ID_ANY, "Continue")
        self.continue_button.SetBackgroundColour(wx.Colour(220, 220, 220))
        self.continue_button.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.Bind(wx.EVT_BUTTON, self.on_continue, self.continue_button)
        self.hbox.Add(self.continue_button, 1, flag=wx.LEFT | wx.TOP | wx.GROW)

    def add_toolbar(self):
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()
        self.vbox.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        self.toolbar.update()

    def on_continue(self, event):
        if self.i < self.iterations and self.rms_error() >= self.tolerance:
            self.run_loop()

    def on_stop(self, event):
        self.stop_loop = True

    def close_window(self, event):
        # Restore stdout to normal, and enable the parent before closing
        self.stop_loop = True
        sys.stdout = self.standard_stdout
        self.parent.Enable()
        self.parent.SetTransparent(255)
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
        self.correction_axis.set_xlabel("Time (ns)", fontsize=8)
        self.correction_axis.set_title("Applied Correction")
        self.curve_axis.set_xlabel("Time (ns)", fontsize=8)
        self.curve_axis.set_title("Pulse Shape")
        self.awg_axis.set_xlabel("Time (ns)", fontsize=8)
        self.awg_axis.set_title("AWG")

        # setup the values to use on the time axis
        time_axis = np.arange(
            0,
            self.num_points * self.config.getVal("awg_ns_per_point"),
            self.config.getVal("awg_ns_per_point"),
        )

        # add data to the plots
        self.corr_plot_data = self.correction_axis.plot(
            time_axis, self.correction_factor, label="Correction"
        )[0]
        self.curve_plot_data = self.curve_axis.plot(
            time_axis, self.current_output, label="Current"
        )[0]
        self.target_plot_data = self.curve_axis.plot(
            time_axis, self.target, label="Target"
        )[0]
        self.curve_axis.legend(loc=8, prop={"size": 8})
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        if not self.config.parms["sim"].value:
            awg_start = self.awg.get_normalised_shape()[: self.num_points]
        else:
            awg_start = self.correction_factor
        self.awg_now_plot_data = self.awg_axis.plot(
            time_axis, awg_start, label="AWG current"
        )[0]
        self.awg_next_plot_data = self.awg_axis.plot(
            time_axis, awg_start, label="AWG next"
        )[0]
        self.awg_axis.legend(loc=8, prop={"size": 8})
        self.awg_axis.set_ybound(lower=-0.1, upper=1.2)
        self.statusBar = wx.StatusBar(self, -1)
        self.statusBar.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "Ubuntu"))
        self.SetStatusBar(self.statusBar)

    def rms_error(self):
        try:
            rms = np.sqrt(np.mean(np.square(self.target - self.current_output)))
        except:
            rms = -1
        return rms

    def peak_power(self):
        try:
            power = 1.0 / np.mean(self.awg_next_norm)
        except:
            power = -1
        return power

    def draw_plots(self):
        self.corr_plot_data.set_ydata(self.correction_factor)
        self.curve_plot_data.set_ydata(self.current_output)
        self.correction_axis.set_ybound(
            lower=0.9 * np.amin(self.correction_factor),
            upper=1.1 * np.amax(self.correction_factor) + 0.001,
        )
        self.statusBar.SetStatusText(
            "Iteration: {0:d}\tRMS: {1:.3f}\tPeak Power: {2:.2f}\tGain: {3:.2f}".format(
                self.i, self.rms_error(), self.peak_power(), self.gain
            )
        )
        self.canvas.draw()

    def draw_awg_plots(self):
        try:
            self.awg_now_plot_data.set_ydata(self.awg_now[: self.num_points])
            self.awg_next_plot_data.set_ydata(self.awg_next_norm[: self.num_points])
            self.canvas.draw()
        except:
            pass

    def check_proceed(self):
        if self.auto_loop == True:
            i = 0
            proceed = CODES.Proceed
            prog = wx.ProgressDialog(
                "Ready to write to AWG",
                "Writing in %i seconds" % self.auto_loop_wait,
                self.auto_loop_wait,
                style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
                parent=self.parent,
            )
            while self.auto_loop_wait - i >= 0:
                if (
                    prog.Update(i, "Writing in %i seconds" % (self.auto_loop_wait - i))[
                        0
                    ]
                ) == False:
                    # User pressed cancel
                    proceed = CODES.Abort
                    prog.Destroy()
                    break
                i += 1
                time.sleep(1)
            wx.SafeYield(
                self
            )  # Allow other UI events to process in case user pressed stop button rather than cancel
            return proceed

        choice = LoopControlDialog(self.parent, title="Gain for next iteration")
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
        self.draw_plots()
        wx.SafeYield(self)  # Lets the plot update
        proceed = -1

        # If auto loop is off, loop continuously until user quits, else loop until
        # max iterations or RMS value reached
        while (not self.auto_loop) or (
            self.i < self.iterations and self.rms_error() >= self.tolerance
        ):
            self.calculate_parms_for_loop()

            # Draw plots and check if the user wants to continue
            self.draw_plots()
            self.draw_awg_plots()
            wx.SafeYield(self)
            proceed = self.check_proceed()

            if proceed == CODES.Abort:
                print(
                    get_message_time() + "Quitting loop. AWG curve will not be applied"
                )
                break
            elif proceed == CODES.Pause:
                print(get_message_time() + "Loop paused")
                break
            elif proceed == CODES.Recalc:
                break

            if self.save_diag_files:
                self.save_files()

            # If the next AWG trace would be unsafe, don't apply it and quit
            if self.peak_power() > self.pulse_peak_power:
                print(
                    get_message_time()
                    + "Quitting loop: proposed curve would exceed peak power"
                )
                self.show_error(
                    "Quitting loop: proposed curve would exceed peak power",
                    "Quitting loop",
                )
                break

            # Check if user stopped the loop
            if self.stop_loop:
                print(get_message_time() + "Quitting loop: user stop")
                break

            self.apply_correction()
            err = self.update_feedback_curve()
            if err == CODES.Error:
                print(
                    get_message_time() + "Quitting loop: couldn't update feedback curve"
                )
                self.show_error(
                    "Quitting loop: couldn't update feedback curve", "Quitting loop"
                )
                break

            # Increase the iteration number and loop again
            self.i += 1

        # After the loop has finished plot the final data. Use the applied AWG trace from the last iteration
        # rather than re-read the AWG values from hardware. The two shouldn't differ unless there was a problem.
        self.draw_plots()
        wx.SafeYield(
            self
        )  # Needed to allow processing events to stop loop and let plot update
        self.loop_end_message(proceed)

    def loop_end_message(self, proceed):
        if proceed == CODES.Abort:
            msg = "Quitting loop: user stop"
        elif proceed == CODES.Recalc:
            return
        elif proceed == CODES.Pause:
            msg = "Loop paused"
        else:
            msg = "Loop ended"
        print(get_message_time() + msg)

    def calculate_parms_for_loop(self):
        self.awg_now = self.get_awg_now()
        self.correction_factor = self.calc_correction_factor(
            self.target, self.current_output, self.gain
        )

        # Apply max % change to the correction factor
        self.correction_factor = np.clip(
            self.correction_factor,
            1.0 - self.max_percent_change / 100.0,
            1.0 + self.max_percent_change / 100.0,
        )

        # Apply correction factor
        awg_next = self.awg_now * self.correction_factor

        # If target is non-zero and output is just noise apply offset. First pass only.
        if self.i == 0:
            threshold = self.noise_threshold_percentage / 100.0
            awg_next[
                np.logical_and(self.target != 0, self.current_output <= threshold)
            ] += self.awg_zero_shift

        # If target is zero set AWG to zero directly
        awg_next[self.target == 0] = 0

        # Normalise output
        try:
            awg_next = self.awg_filter(awg_next)
        except:
            self.show_error(
                "Error when applying user-defined filter\n Ignoring filter",
                "Filter error",
            )

            # Remove filter to avoid error message every loop
            def no_filter(data):
                return data

            self.awg_filter = no_filter
        self.awg_next_norm = awg_next / np.amax(awg_next)

    def apply_correction(self):
        if self.sim == True:
            self.current_output = self.awg_next_norm
            self.awg.sim_write(self.parent)
            print(
                get_message_time()
                + "Applied correction for iteration %i" % (self.i + 1)
            )
        else:
            # Write the new AWG trace to the hardware
            self.awg.pause_scanning_PVS()  # Stop IDIL/AWG comms while writing curve
            time.sleep(1)  # Let the message buffer clear
            if self.i == 0:
                # On the first pass only, set any AWG samples outside the pulse to zero
                self.awg.write(self.awg_next_norm, parent=self.parent, zero_to_end=True)
            else:
                self.awg.write(
                    self.awg_next_norm, parent=self.parent, zero_to_end=False
                )
            self.awg.start_scanning_PVS()  # Restart the comms now finished writing
        wx.SafeYield(self)

    def update_feedback_curve(self):
        if self.sim == True:
            # Don't bother with background correction for simulation mode, so
            # just return
            return CODES.NoError

        # Check if scope settings have changed. We could deal with this if they have, but for now
        # just warn user and exit
        if self.time_resolution_pv.get() != self.time_res:
            print(
                get_message_time()
                + "Scope time resolution has changed since loop started"
            )
            self.show_error(
                "Scope time resolution has changed since loop started", "Scope settings"
            )
            return CODES.Error

        cropping = (self.slice_start, self.slice_length)
        datas = []
        i = 0
        if self.scope_pv.connected:
            prog = wx.ProgressDialog(
                "Getting scope data",
                "Reading trace 1",
                self.scope_averages,
                style=wx.PD_AUTO_HIDE,
                parent=self.parent,
            )
            while i < self.scope_averages:
                data = self.scope_pv.get()
                datas.append(data)
                time.sleep(self.config.getVal("scope_wait"))
                i += 1
                prog.Update(i, "Reading trace %d" % (i))
        else:
            self.show_error("Can't connect to scope PV", "Scope read error")
            return CODES.Error

        avg = np.average(np.array(datas), axis=0)
        feedback_curve = Curve(curve_array=avg, name="Current")
        feedback_curve.process(
            "clip", "norm", bkg=self.background, crop=cropping, resample=self.num_points
        )
        self.current_output = feedback_curve.get_processed()
        wx.SafeYield(self)
        return CODES.NoError

    def save_files(self):
        location = self.config.getVal("diag")
        fileroot = datetime.now().strftime("%Y_%m_%d_%Hh%M")
        if self.i == 0:
            np.savetxt(location + fileroot + "_target.txt", self.target)
            np.savetxt(
                location + fileroot + "_background.txt", self.background.get_raw()
            )
        np.savetxt(
            (location + fileroot + "_i_%0.5d_AWG_shape.txt" % self.i), self.awg_now
        )
        np.savetxt(
            (
                location
                + fileroot
                + "_i_%0.5d_g_%.2f_correction.txt" % (self.i + 1, self.gain)
            ),
            self.correction_factor,
        )
        np.savetxt(
            (location + fileroot + "_i_%0.5d_scope_trace.txt" % self.i),
            self.current_output,
        )

    def get_awg_now(self):
        if self.sim == True:
            # Assume 1 to 1 mapping of AWG to output for simulation
            return self.current_output
        else:
            # Read from the AWG and extract the number of points used for this pulse
            return self.awg.get_normalised_shape()[: self.num_points]

    def simulate_start_data(self):
        temp = 0.5 * np.ones(np.size(self.background.get_raw()))
        temp[250:350] = 0.01
        temp[400:500] = 0.03
        cropping = (self.slice_start, self.slice_length)

        sim_curve = Curve(curve_array=temp)
        sim_curve.process(
            "clip", "norm", bkg=self.background, crop=cropping, resample=self.num_points
        )
        return sim_curve.get_processed()

    def import_correction_algorithm(self):
        try:
            filename = self.config.getVal("algorithm")
            modname = os.path.split(filename)[-1].rsplit(".", 1)[0]
            if not modname in sys.modules.keys():
                mod = importlib.import_module(modname)
            else:
                mod = importlib.reload(sys.modules[modname])
            if mod.calc_correction:
                algorithm = mod.calc_correction
        except ModuleNotFoundError:
            self.show_error(
                "Can't import module {0}. Ensure {1} is in one of the following locations:\n\n{2}".format(
                    modname, filename, sys.path
                ),
                "File not found",
            )

            # Use a default if the imported version causes and error
            def algorithm(target, current, gain):
                with np.errstate(divide="ignore", invalid="ignore"):
                    temp = target / current
                temp[np.isfinite(temp) == False] = 1
                correction_factor = (temp - 1) * gain + 1
                return correction_factor

        except (NameError, AttributeError) as e:
            self.show_error("Error in {0}:\n\n{1}".format(filename, e), "Not found")
        self.calc_correction_factor = algorithm

    def import_awg_filter(self):
        # null filter to apply if import fails
        def filt(data):
            return data

        try:
            filename = self.config.getVal("filter")
            modname = os.path.split(filename)[-1].rsplit(".", 1)[0]
            if not modname in sys.modules.keys():
                mod = importlib.import_module(modname)
            else:
                mod = importlib.reload(sys.modules[modname])
            if mod.awg_filter:
                filt = mod.awg_filter
        except ModuleNotFoundError:
            self.show_error(
                "Can't import module {0}. Ensure {1} is in one of the following locations:\n\n{2}".format(
                    modname, filename, sys.path
                ),
                "File not found",
            )
        except (NameError, AttributeError) as e:
            self.show_error("Error in {0}:\n\n{1}".format(filename, e), "Not found")
        self.awg_filter = filt

    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap, style=wx.ICON_ERROR)
        err.ShowModal()
