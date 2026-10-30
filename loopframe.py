import logging
import time

import matplotlib

matplotlib.use("WXAgg")
import matplotlib.pyplot as plt
import numpy as np
import wx
from matplotlib.backends.backend_wx import NavigationToolbar2Wx as NavigationToolbar
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas

from beam_shaper.core.diagnostics import DiagnosticWriter
from beam_shaper.core.interfaces import FeedbackError
from beam_shaper.core.loop import Decision, LoopEngine, LoopParameters
from beam_shaper.core.plugins import load_awg_filter, load_correction_algorithm
from beam_shaper.core.settings import num_points
from loopControlDialog import LoopControlDialog
from util import CODES
from wx_adapters import TextCtrlLogHandler, WxProgress

log = logging.getLogger(__name__)

DECISIONS = {
    CODES.Proceed: Decision.APPLY,
    CODES.Recalc: Decision.RECALC,
    CODES.Pause: Decision.PAUSE,
    CODES.Abort: Decision.ABORT,
}


class LoopFrame(wx.Frame):
    """Window that shows and controls the feedback loop run by a LoopEngine"""

    def __init__(self, parent, config, settings, target, background, scope_pv, time_resolution_pv):
        # A bit of work to position this window below the main setup window
        parent_x, parent_y = parent.GetPosition().Get()
        parent_height = parent.GetSize().GetHeight()
        position = wx.Point(parent_x, parent_y + parent_height)
        title = "Loop (simulation)" if config.sim else "Loop"

        wx.Frame.__init__(self, parent, size=(1000, 400), title=title, pos=position)
        self.parent = parent
        self.config = config
        self.auto_loop = config.auto_loop
        self.auto_loop_wait = config.auto_loop_wait
        self.num_points = num_points(settings.pulse_length, config.awg_ns_per_point)
        self.stop_loop = False

        self.engine = self.create_engine(
            config, settings, target, background, scope_pv, time_resolution_pv
        )
        try:
            self.engine.start()
        except FeedbackError as e:
            self.show_error("Couldn't read the pulse shape:\n\n{0}".format(e), "Feedback error")
            self.Destroy()
            return

        # Create a panel to hold a log output
        log_panel = wx.Panel(self, wx.ID_ANY)
        log_ctrl = wx.TextCtrl(
            log_panel,
            size=(1000, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(log_ctrl, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        log_panel.SetSizer(sizer)

        # Show log messages from the loop and hardware in the log window
        self.log_handler = TextCtrlLogHandler(log_ctrl)
        logging.getLogger().addHandler(self.log_handler)

        # Canvas to hold the plots
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.init_plot()
        self.canvas = FigCanvas(self, -1, self.fig)
        self.add_toolbar()

        # Add canvas and log window to sizer. Add stop button if auto-looping.
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.hbox.Add(log_panel, 5, flag=wx.LEFT | wx.TOP | wx.GROW)
        if self.auto_loop:
            # Add a stop button for breaking out of auto-loop
            self.add_stop_button()
        else:
            # Used to restart a paused loop
            self.add_continue_button()
        self.vbox.Add(self.hbox, 0, flag=wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.vbox)
        self.vbox.Fit(self)

        # Draw the window and display
        self.draw_plots()
        # Stop the user launching another loop window until this one is closed
        self.parent.Disable()
        self.parent.SetTransparent(120)
        self.Show()
        self.Bind(wx.EVT_CLOSE, self.close_window)
        self.run_loop()

    def create_engine(self, config, settings, target, background, scope_pv, time_resolution_pv):
        correction_fn, err = load_correction_algorithm(config.algorithm)
        if err:
            self.show_error(err, "Correction algorithm error")
        filter_fn, err = load_awg_filter(config.filter)
        if err:
            self.show_error(err, "Filter error")

        crop = (settings.slice_start, settings.slice_length)
        if config.sim:
            from beam_shaper.hardware.sim import SimAwg, SimFeedback, simulated_start_shape

            awg = SimAwg(simulated_start_shape(background, crop, self.num_points))
            feedback = SimFeedback(awg)
        else:
            from beam_shaper.hardware.epics_awg import EpicsAwg
            from beam_shaper.hardware.epics_scope import EpicsFeedback

            awg = EpicsAwg(
                config.awg_prefix,
                self.num_points,
                settings.max_percent_change,
                config.awg_write_method,
                config.awg_wait,
            )
            feedback = EpicsFeedback(
                scope_pv,
                time_resolution_pv,
                background,
                crop,
                self.num_points,
                settings.averages,
                config.scope_wait,
            )

        params = LoopParameters(
            gain=settings.gain,
            iterations=settings.iterations,
            tolerance=settings.tolerance,
            max_percent_change=settings.max_percent_change,
            auto_loop=config.auto_loop,
            pulse_peak_power=config.pulse_peak_power,
            noise_threshold_percentage=config.noise_threshold_percentage,
            awg_zero_shift=config.awg_zero_shift,
        )
        return LoopEngine(
            target.get_processed(),
            params,
            awg,
            feedback,
            correction_fn=correction_fn,
            filter_fn=filter_fn,
            diagnostics=DiagnosticWriter(config.diag) if settings.save_diag_files else None,
            background_raw=background.get_raw(),
            progress=WxProgress(self.parent),
            on_warning=self.show_error,
        )

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
        if not self.engine.limits_reached():
            self.run_loop()

    def on_stop(self, event):
        self.stop_loop = True

    def close_window(self, event):
        # Detach the log window, and enable the parent before closing
        self.stop_loop = True
        logging.getLogger().removeHandler(self.log_handler)
        self.parent.Enable()
        self.parent.SetTransparent(255)
        self.Destroy()

    def init_plot(self):
        engine = self.engine
        # create the plots and add some labels
        self.dpi = 100
        self.fig = plt.Figure((12.0, 4.0), dpi=self.dpi)
        self.curve_axis = self.fig.add_subplot(131)
        self.correction_axis = self.fig.add_subplot(132)
        self.awg_axis = self.fig.add_subplot(133)
        for axis in (self.curve_axis, self.correction_axis, self.awg_axis):
            axis.tick_params(labelsize=8)
            axis.set_xlabel("Time (ns)", fontsize=8)
        self.correction_axis.set_title("Applied Correction")
        self.curve_axis.set_title("Pulse Shape")
        self.awg_axis.set_title("AWG")

        # setup the values to use on the time axis
        ns_per_point = self.config.awg_ns_per_point
        time_axis = np.arange(0, self.num_points * ns_per_point, ns_per_point)

        # add data to the plots
        self.corr_plot_data = self.correction_axis.plot(
            time_axis, engine.correction_factor, label="Correction"
        )[0]
        self.curve_plot_data = self.curve_axis.plot(
            time_axis, engine.current_output, label="Current"
        )[0]
        self.target_plot_data = self.curve_axis.plot(time_axis, engine.target, label="Target")[0]
        self.curve_axis.legend(loc=8, prop={"size": 8})
        self.curve_axis.set_ybound(lower=-0.1, upper=1.2)
        self.awg_now_plot_data = self.awg_axis.plot(
            time_axis, engine.awg_now, label="AWG current"
        )[0]
        self.awg_next_plot_data = self.awg_axis.plot(
            time_axis, engine.awg_now, label="AWG next"
        )[0]
        self.awg_axis.legend(loc=8, prop={"size": 8})
        self.awg_axis.set_ybound(lower=-0.1, upper=1.2)
        self.statusBar = wx.StatusBar(self, -1)
        self.statusBar.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "Ubuntu"))
        self.SetStatusBar(self.statusBar)

    def draw_plots(self):
        engine = self.engine
        self.corr_plot_data.set_ydata(engine.correction_factor)
        self.curve_plot_data.set_ydata(engine.current_output)
        self.correction_axis.set_ybound(
            lower=0.9 * np.amin(engine.correction_factor),
            upper=1.1 * np.amax(engine.correction_factor) + 0.001,
        )
        self.statusBar.SetStatusText(
            "Iteration: {0:d}\tRMS: {1:.3f}\tPeak Power: {2:.2f}\tGain: {3:.2f}".format(
                engine.i, engine.rms_error(), engine.peak_power(), engine.gain
            )
        )
        self.canvas.draw()

    def draw_awg_plots(self):
        engine = self.engine
        self.awg_now_plot_data.set_ydata(engine.awg_now)
        if engine.awg_next_norm is not None:
            self.awg_next_plot_data.set_ydata(engine.awg_next_norm)
        self.canvas.draw()

    def on_update(self, engine):
        self.draw_plots()
        self.draw_awg_plots()
        wx.SafeYield(self)

    def should_stop(self):
        # Allow UI events to process in case user pressed the stop button
        wx.SafeYield(self)
        return self.stop_loop

    def approve(self, engine):
        if self.auto_loop:
            return self.auto_approve(engine)
        choice = LoopControlDialog(self.parent, title="Gain for next iteration")
        choice.SetValue(str(engine.gain))
        proceed = choice.ShowModal()
        gain = float(choice.GetValue())
        choice.Destroy()
        return DECISIONS[proceed], gain

    def auto_approve(self, engine):
        # Give the user a few seconds to cancel before each write
        prog = wx.ProgressDialog(
            "Ready to write to AWG",
            "Writing in %i seconds" % self.auto_loop_wait,
            self.auto_loop_wait,
            style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
            parent=self.parent,
        )
        decision = Decision.APPLY
        for i in range(self.auto_loop_wait + 1):
            if not prog.Update(i, "Writing in %i seconds" % (self.auto_loop_wait - i))[0]:
                decision = Decision.ABORT
                break
            time.sleep(1)
        prog.Destroy()
        return decision, engine.gain

    def run_loop(self):
        self.draw_plots()
        wx.SafeYield(self)  # Lets the plot update
        try:
            result = self.engine.run(self.approve, self.should_stop, self.on_update)
        except Exception as e:
            log.exception("Loop failed")
            self.show_error("Loop stopped by an error:\n\n{0}".format(e), "Loop error")
            return
        # After the loop has finished plot the final data
        self.draw_plots()
        wx.SafeYield(self)
        if result.is_error:
            self.show_error(result.message, "Quitting loop")

    def show_error(self, msg, cap):
        err = wx.MessageDialog(self, msg, cap, style=wx.ICON_ERROR)
        err.ShowModal()
