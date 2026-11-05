import logging

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from beam_shaper.core.loop import Decision, Outcome
from beam_shaper.ui.plots import BLUE, ORANGE, make_plot
from beam_shaper.ui.workers import UNKNOWN, LoopWorker, QtLogHandler

STOP_STYLE = (
    "QPushButton { background: #ff2828; color: white; font: bold 14pt; }"
    "QPushButton:disabled { background: #d8a0a0; color: #f0f0f0; }"
)
BIG_BUTTON_STYLE = "QPushButton { font: bold 14pt; }"


class LoopWindow(QMainWindow):
    """Shows and controls a LoopEngine running in a background thread."""

    closed = Signal()

    def __init__(self, engine, auto_loop, auto_loop_wait, ns_per_point, sim, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loop (simulation)" if sim else "Loop")
        self.resize(1200, 650)
        self.auto_loop = auto_loop
        self.auto_loop_wait = auto_loop_wait
        self.time_axis = np.arange(engine.num_points) * ns_per_point
        self.close_pending = False
        self.last_result = None

        self.worker = LoopWorker(engine, sim)
        self.build_ui()

        # Show log messages from the loop and hardware in the log panel
        self.log_handler = QtLogHandler()
        self.log_handler.emitter.message.connect(self.log.appendPlainText)
        app_log = logging.getLogger("beam_shaper")
        if app_log.level == logging.NOTSET:
            app_log.setLevel(logging.INFO)
        app_log.addHandler(self.log_handler)

        self.countdown = QTimer(self)
        self.countdown.setInterval(1000)
        self.countdown.timeout.connect(self.on_countdown_tick)

        # Worker signals come from its thread. Connect only to methods of this window, never
        # lambdas: a lambda has no thread of its own, so it would run on the worker thread.
        w = self.worker
        w.updated.connect(self.show_snapshot)
        w.approval_needed.connect(self.on_approval_needed)
        w.warning.connect(self.on_warning)
        w.failed.connect(self.on_failed)
        w.finished.connect(self.on_finished)
        w.progress.started.connect(self.on_progress_started)
        w.progress.updated.connect(self.on_progress_updated)
        w.progress.finished.connect(self.on_progress_finished)

        self.set_awaiting(False)
        w.start_run()

    # ---------------------------------------------------------------- layout

    def build_ui(self):
        self.shape_plot = make_plot("Pulse Shape", "Time (ns)")
        self.shape_plot.addLegend()
        self.current_line = self.shape_plot.plot(pen=BLUE, name="Current")
        self.target_line = self.shape_plot.plot(pen=ORANGE, name="Target")
        self.shape_plot.setYRange(-0.1, 1.2)

        self.correction_plot = make_plot("Applied Correction", "Time (ns)")
        self.correction_line = self.correction_plot.plot(pen=BLUE)

        self.awg_plot = make_plot("AWG", "Time (ns)")
        self.awg_plot.addLegend()
        self.awg_now_line = self.awg_plot.plot(pen=BLUE, name="AWG current")
        self.awg_next_line = self.awg_plot.plot(pen=ORANGE, name="AWG next")
        self.awg_plot.setYRange(-0.1, 1.2)

        plots = QHBoxLayout()
        for plot in (self.shape_plot, self.correction_plot, self.awg_plot):
            plots.addWidget(plot)

        # Progress of slow hardware operations
        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        progress = QHBoxLayout()
        progress.addWidget(self.progress_label, 1)
        progress.addWidget(self.progress_bar, 2)

        # Approval controls
        controls = QHBoxLayout()
        if self.auto_loop:
            self.countdown_label = QLabel()
            self.cancel_button = QPushButton("Cancel write")
            self.cancel_button.clicked.connect(lambda: self.respond(Decision.ABORT))
            self.stop_button = QPushButton("Stop")
            self.stop_button.setStyleSheet(STOP_STYLE)
            self.stop_button.clicked.connect(self.on_stop)
            controls.addWidget(self.countdown_label, 1)
            controls.addWidget(self.cancel_button)
            controls.addWidget(self.stop_button, 1)
        else:
            self.gain_spin = QDoubleSpinBox()
            self.gain_spin.setRange(0.0, 1.0)
            self.gain_spin.setSingleStep(0.05)
            self.gain_spin.setDecimals(2)
            self.gain_spin.setPrefix("Gain: ")
            # Changing the gain replots straight away, as the wx version did
            self.gain_spin.editingFinished.connect(self.on_gain_edited)
            self.apply_button = QPushButton("Apply")
            self.apply_button.clicked.connect(lambda: self.respond(Decision.APPLY))
            self.replot_button = QPushButton("Replot")
            self.replot_button.clicked.connect(lambda: self.respond(Decision.RECALC))
            self.pause_button = QPushButton("Pause")
            self.pause_button.clicked.connect(lambda: self.respond(Decision.PAUSE))
            self.continue_button = QPushButton("Continue")
            self.continue_button.setStyleSheet(BIG_BUTTON_STYLE)
            self.continue_button.setEnabled(False)
            self.continue_button.clicked.connect(self.on_continue)
            for widget in (self.gain_spin, self.apply_button, self.replot_button, self.pause_button):
                controls.addWidget(widget)
            controls.addStretch(1)
            controls.addWidget(self.continue_button, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setMaximumHeight(140)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("font: bold 12pt;")
        self.statusBar().addWidget(self.status_label)

        layout = QVBoxLayout()
        layout.addLayout(plots, 1)
        layout.addLayout(progress)
        layout.addLayout(controls)
        layout.addWidget(self.log)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.on_progress_finished()

    # ---------------------------------------------------------------- display

    def show_snapshot(self, s):
        if s.current is not None:
            self.current_line.setData(self.time_axis, s.current)
        self.target_line.setData(self.time_axis, s.target)
        self.correction_line.setData(self.time_axis, s.correction)
        if s.awg_now is not None:
            self.awg_now_line.setData(self.time_axis, s.awg_now)
            next_trace = s.awg_next if s.awg_next is not None else s.awg_now
            self.awg_next_line.setData(self.time_axis, next_trace)
        self.status_label.setText(
            "Iteration: {0:d}    RMS: {1:.3f}    Peak Power: {2:.2f}    Gain: {3:.2f}".format(
                s.i, s.rms, s.peak_power, s.gain
            )
        )

    def on_warning(self, message, caption):
        QMessageBox.warning(self, caption, message)

    def on_failed(self, message):
        QMessageBox.critical(self, "Loop error", "Loop stopped by an error:\n\n" + message)

    def on_progress_started(self, title, message, maximum):
        self.progress_label.setText("{0}: {1}".format(title, message) if message else title)
        self.progress_bar.setRange(0, 0 if maximum == UNKNOWN else maximum)
        self.progress_bar.setValue(0)
        self.progress_label.show()
        self.progress_bar.show()

    def on_progress_updated(self, value, message):
        if value != UNKNOWN:
            self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    def on_progress_finished(self):
        self.progress_label.hide()
        self.progress_bar.hide()

    # ---------------------------------------------------------------- approval

    def set_awaiting(self, awaiting):
        if self.auto_loop:
            self.cancel_button.setEnabled(awaiting)
            if not awaiting:
                self.countdown_label.setText("")
        else:
            for widget in (self.apply_button, self.replot_button, self.pause_button, self.gain_spin):
                widget.setEnabled(awaiting)

    def on_approval_needed(self, snapshot):
        self.set_awaiting(True)
        if self.auto_loop:
            # Give the user a few seconds to cancel before each write
            self.remaining = self.auto_loop_wait
            self.update_countdown_label()
            if self.remaining <= 0:
                self.respond(Decision.APPLY)
            else:
                self.countdown.start()
        else:
            self.gain_spin.blockSignals(True)
            self.gain_spin.setValue(snapshot.gain)
            self.gain_spin.blockSignals(False)
            self.shown_gain = snapshot.gain

    def update_countdown_label(self):
        self.countdown_label.setText("Writing to AWG in %i s" % self.remaining)

    def on_countdown_tick(self):
        self.remaining -= 1
        self.update_countdown_label()
        if self.remaining <= 0:
            self.respond(Decision.APPLY)

    def on_gain_edited(self):
        if self.worker.awaiting_approval and self.gain_spin.value() != self.shown_gain:
            self.respond(Decision.RECALC)

    def respond(self, decision):
        self.countdown.stop()
        gain = self.worker.engine.gain if self.auto_loop else self.gain_spin.value()
        self.set_awaiting(False)
        self.worker.respond(decision, gain)

    def on_stop(self):
        self.worker.request_stop()
        self.stop_button.setEnabled(False)
        # If counting down, finish now: the loop checks for the stop before writing
        if self.worker.awaiting_approval:
            self.respond(Decision.APPLY)

    def on_continue(self):
        self.continue_button.setEnabled(False)
        self.worker.start_run()

    def on_finished(self, result):
        self.last_result = result
        self.set_awaiting(False)
        if self.auto_loop:
            self.stop_button.setEnabled(False)
        elif result is not None and result.outcome is Outcome.PAUSED:
            self.continue_button.setEnabled(not self.worker.engine.limits_reached())
        if self.close_pending:
            self.close()
            return
        if result is not None and result.is_error:
            QMessageBox.critical(self, "Quitting loop", result.message)

    # ---------------------------------------------------------------- closing

    def closeEvent(self, event):
        if self.worker.running:
            # Never abandon the thread mid-write: stop the loop, then close when it finishes
            self.close_pending = True
            self.worker.request_stop()
            if self.worker.awaiting_approval:
                self.respond(Decision.ABORT)
            self.status_label.setText("Stopping...")
            event.ignore()
            return
        logging.getLogger("beam_shaper").removeHandler(self.log_handler)
        self.worker.shutdown()
        self.closed.emit()
        event.accept()
