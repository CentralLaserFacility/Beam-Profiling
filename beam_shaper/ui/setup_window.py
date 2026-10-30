import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from beam_shaper.core import settings
from beam_shaper.core.curve import Curve, library_curves, library_path, load_background, load_target
from beam_shaper.core.settings import LoopSettings
from beam_shaper.hardware.epics_scope import close_pvs, open_scope_pvs, read_average
from beam_shaper.session import build_engine
from beam_shaper.ui.config_dialog import ConfigDialog
from beam_shaper.ui.file_editor import FileEditDialog
from beam_shaper.ui.loop_window import LoopWindow
from beam_shaper.ui.plots import PreviewWindow
from beam_shaper.ui.state import SetupState
from beam_shaper.ui.workers import UNKNOWN, TaskWorker

CONNECTED_STYLE = "QLineEdit { background: #0aff05; }"
DISCONNECTED_STYLE = "QLineEdit { background: #cc99ff; }"
GO_STYLE = (
    "QPushButton { background: #0aff05; color: black; font: bold 14pt; }"
    "QPushButton:disabled { background: #a8d8a6; color: #606060; }"
)
ICONS = "gui_files"


def _icon_button(icon_file, tooltip):
    button = QToolButton()
    path = os.path.join(ICONS, icon_file)
    if os.path.exists(path):
        button.setIcon(QIcon(path))
    else:
        button.setText(tooltip)
    button.setToolTip(tooltip)
    return button


def _boxed(title, *widgets):
    box = QGroupBox(title)
    layout = QHBoxLayout(box)
    for widget in widgets:
        layout.addWidget(widget)
    return box


class SetupWindow(QMainWindow):
    """Choose the target, background and loop settings, then start a loop."""

    # Connection changes arrive on a Channel Access thread; signals move them to the GUI thread
    scope_connection_changed = Signal(bool)
    time_res_connection_changed = Signal(bool)

    def __init__(self, config, config_file="./config.ini", state_file="./state.txt"):
        super().__init__()
        self.config = config
        self.config_file = config_file
        self.state_file = state_file
        self.scope_pv = self.time_resolution_pv = None
        self.scope_curve = Curve(name="Scope")  # Holds data from a 'grab'
        self.loop_window = None
        self.close_pending = False
        self.previews = []
        self.task = None

        self.build_ui()
        # Connect cross-thread signals to methods, never lambdas: a lambda has no thread of
        # its own, so it would run on the thread that emitted the signal
        self.scope_connection_changed.connect(self.show_scope_connection)
        self.time_res_connection_changed.connect(self.on_time_res_connection)

        state = SetupState.load(state_file)
        self.apply_state(state)
        self.populate_library(state.library_index)
        self.connect_scope()
        self.apply_config_to_ui()

    # ---------------------------------------------------------------- layout

    def build_ui(self):
        self.resize(1050, 0)  # height fits the contents

        # Background, target file and library
        self.bkg_path = QLineEdit()
        self.bkg_browse = _icon_button("Open folder.png", "Browse")
        self.bkg_browse.clicked.connect(lambda: self.browse(self.bkg_path))
        self.bkg_preview = _icon_button("preview.png", "Preview")
        self.bkg_preview.clicked.connect(self.preview_background)

        self.target_path = QLineEdit()
        self.target_browse = _icon_button("Open folder.png", "Browse")
        self.target_browse.clicked.connect(lambda: self.browse(self.target_path))
        self.target_preview = _icon_button("preview.png", "Preview")
        self.target_preview.clicked.connect(lambda: self.preview_target(from_file=True))

        self.library = QComboBox()
        self.library_preview = _icon_button("preview.png", "Preview")
        self.library_preview.clicked.connect(lambda: self.preview_target(from_file=False))

        files = QGridLayout()
        files.addWidget(_boxed("Background file", self.bkg_path, self.bkg_browse), 0, 0)
        files.addWidget(self.bkg_preview, 0, 1)
        files.addWidget(_boxed("Target file", self.target_path, self.target_browse), 1, 0)
        files.addWidget(self.target_preview, 1, 1)
        files.addWidget(_boxed("Pulse shape library", self.library), 2, 0)
        files.addWidget(self.library_preview, 2, 1)

        # Scope
        self.scope_pv_edit = QLineEdit()
        self.scope_pv_edit.setMinimumWidth(260)
        self.scope_pv_edit.returnPressed.connect(self.connect_scope)
        self.grab_button = QPushButton("Grab")
        self.grab_button.clicked.connect(self.grab_trace)
        self.averages = QSpinBox()
        self.averages.setRange(1, 1000)
        self.averages.setPrefix("Average: ")
        self.trace_preview = _icon_button("preview.png", "Preview")
        self.trace_preview.clicked.connect(
            lambda: self.show_preview("Scope", self.scope_curve.get_processed())
        )
        self.save_trace_button = _icon_button("Save.png", "Save trace")
        self.save_trace_button.clicked.connect(self.save_trace)

        self.slice_start = QSpinBox()
        self.slice_start.setRange(0, 10**7)
        self.slice_length = QSpinBox()
        self.slice_length.setRange(0, 10**7)
        self.slice_length.setReadOnly(True)
        self.slice_length.setButtonSymbols(QSpinBox.NoButtons)

        self.target_source = QComboBox()
        self.target_source.addItems(["Library", "File"])

        self.pulse_length = QDoubleSpinBox()
        self.pulse_length.setDecimals(3)
        self.pulse_length.setRange(0, 10**4)
        self.pulse_length.editingFinished.connect(self.coerce_pulse_length)

        scope = QHBoxLayout()
        scope.addWidget(
            _boxed(
                "Scope PV",
                self.scope_pv_edit,
                self.grab_button,
                self.averages,
                self.trace_preview,
                self.save_trace_button,
            ),
            3,
        )
        scope.addWidget(_boxed("Start point / length", self.slice_start, self.slice_length), 1)
        scope.addWidget(_boxed("Target source", self.target_source), 1)
        scope.addWidget(_boxed("Pulse length (ns)", self.pulse_length), 1)

        # Loop settings
        self.gain = QDoubleSpinBox()
        self.gain.setRange(*settings.GAIN_RANGE)
        self.gain.setSingleStep(0.05)
        self.gain.setDecimals(2)
        self.iterations = QSpinBox()
        self.iterations.setRange(settings.MIN_ITERATIONS, 10**6)
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setDecimals(3)
        self.tolerance.setRange(settings.MIN_TOLERANCE, 1000)
        self.tolerance.setSingleStep(0.01)
        self.max_change = QSpinBox()
        self.max_change.setRange(*settings.MAX_CHANGE_RANGE)
        self.save_files = QCheckBox("Save files")
        self.go_button = QPushButton("Go")
        self.go_button.setStyleSheet(GO_STYLE)
        self.go_button.setMinimumHeight(50)
        self.go_button.clicked.connect(self.on_go)

        loop = QHBoxLayout()
        loop.addWidget(_boxed("Gain", self.gain), 1)
        loop.addWidget(_boxed("Max iterations", self.iterations), 1)
        loop.addWidget(_boxed("Tolerance", self.tolerance), 1)
        loop.addWidget(_boxed("Max % change", self.max_change), 1)
        loop.addWidget(self.save_files)
        loop.addWidget(self.go_button, 1)

        layout = QVBoxLayout()
        layout.addLayout(files)
        layout.addLayout(scope)
        layout.addLayout(loop)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        menu = self.menuBar().addMenu("&Settings")
        for text, slot in (
            ("Configure...", self.edit_config),
            ("Edit filter...", lambda: self.edit_file(self.config.filter)),
            ("Edit algorithm...", lambda: self.edit_file(self.config.algorithm)),
        ):
            action = QAction(text, self)
            action.triggered.connect(slot)
            menu.addAction(action)

    # ---------------------------------------------------------------- state

    def apply_state(self, s):
        self.bkg_path.setText(s.bkg_path)
        self.target_path.setText(s.target_path)
        self.scope_pv_edit.setText(s.scope_pv or self.config.scope)
        self.averages.setValue(s.averages)
        self.slice_start.setValue(s.slice_start)
        self.slice_length.setValue(s.slice_length)
        self.target_source.setCurrentIndex(1 if s.target_from_file else 0)
        self.pulse_length.setValue(s.pulse_length)
        self.gain.setValue(s.gain)
        self.iterations.setValue(s.iterations)
        self.tolerance.setValue(s.tolerance)
        self.max_change.setValue(s.max_change)
        self.save_files.setChecked(s.save_files)
        self.coerce_pulse_length()

    def current_state(self):
        return SetupState(
            bkg_path=self.bkg_path.text(),
            target_path=self.target_path.text(),
            library_index=max(0, self.library.currentIndex()),
            scope_pv=self.scope_pv_edit.text().strip(),
            averages=self.averages.value(),
            slice_start=self.slice_start.value(),
            slice_length=self.slice_length.value(),
            target_from_file=self.target_source.currentIndex() == 1,
            pulse_length=self.pulse_length.value(),
            gain=self.gain.value(),
            iterations=self.iterations.value(),
            tolerance=self.tolerance.value(),
            max_change=self.max_change.value(),
            save_files=self.save_files.isChecked(),
        )

    def populate_library(self, index=0):
        self.library.clear()
        self.library.addItems(library_curves(self.config.curve))
        if 0 <= index < self.library.count():
            self.library.setCurrentIndex(index)

    def apply_config_to_ui(self):
        self.setWindowTitle("Beam Profiling (simulation)" if self.config.sim else "Beam Profiling")
        self.pulse_length.setSingleStep(self.config.awg_ns_per_point)
        # When not autolooping, max iterations and tolerance aren't used
        self.iterations.setEnabled(self.config.auto_loop)
        self.tolerance.setEnabled(self.config.auto_loop)

    # ---------------------------------------------------------------- scope

    def connect_scope(self):
        close_pvs(self.scope_pv, self.time_resolution_pv)
        self.show_scope_connection(False)
        self.scope_pv, self.time_resolution_pv = open_scope_pvs(
            self.scope_pv_edit.text().strip(),
            self.scope_connection_changed.emit,
            self.time_res_connection_changed.emit,
        )

    def show_scope_connection(self, connected):
        self.scope_pv_edit.setStyleSheet(CONNECTED_STYLE if connected else DISCONNECTED_STYLE)

    def on_time_res_connection(self, connected):
        if connected:
            self.update_slice_length()

    def time_resolution(self):
        """Scope time resolution in seconds, or None if unknown."""
        if self.time_resolution_pv is None or not self.time_resolution_pv.connected:
            return None
        return self.time_resolution_pv.get()

    def coerce_pulse_length(self):
        self.pulse_length.setValue(
            settings.coerce_pulse_length(self.pulse_length.value(), self.config.awg_ns_per_point)
        )
        self.update_slice_length()

    def update_slice_length(self):
        resolution = self.time_resolution()
        if resolution:
            self.slice_length.setValue(
                settings.scope_slice_length(self.pulse_length.value(), resolution)
            )

    def grab_trace(self):
        """Average a number of traces from the scope, without blocking the window."""
        if self.task is not None:
            return
        pv, n, wait = self.scope_pv, self.averages.value(), self.config.scope_wait
        self.task = TaskWorker(lambda progress: read_average(pv, n, wait, progress), self.config.sim)

        self.grab_dialog = QProgressDialog("Reading trace 1", None, 0, n, self)
        self.grab_dialog.setWindowTitle("Getting scope data")
        self.grab_dialog.setMinimumDuration(0)
        self.task.progress.updated.connect(self.on_grab_progress)
        self.task.succeeded.connect(self.on_grab_succeeded)
        self.task.failed.connect(self.on_grab_failed)
        self.task.finished.connect(self.on_grab_finished)
        self.task.start()

    def on_grab_progress(self, value, message):
        if value != UNKNOWN:
            self.grab_dialog.setValue(value)
        self.grab_dialog.setLabelText(message)

    def on_grab_succeeded(self, result):
        self.scope_curve = Curve(curve_array=result, name="Scope")

    def on_grab_failed(self, message):
        self.show_error(message, "Scope read error")

    def on_grab_finished(self):
        self.grab_dialog.close()
        self.task.shutdown()
        self.task = None

    def save_trace(self):
        pathname, _ = QFileDialog.getSaveFileName(self, "Save Curve")
        if not pathname:
            return
        try:
            self.scope_curve.save(pathname, raw=True)
        except OSError as e:
            self.show_error("Couldn't save the file:\n\n{0}".format(e), "Save error")

    # ---------------------------------------------------------------- curves

    def num_points(self):
        return settings.num_points(self.pulse_length.value(), self.config.awg_ns_per_point)

    def browse(self, line_edit):
        pathname, _ = QFileDialog.getOpenFileName(self, "Load Curve", line_edit.text())
        if pathname:
            line_edit.setText(pathname)

    def target_file(self, from_file):
        if from_file:
            return self.target_path.text()
        return library_path(self.config.curve, self.library.currentText())

    def preview_background(self):
        try:
            curve = load_background(self.bkg_path.text())
        except (OSError, ValueError):
            self.show_error("Couldn't read the curve", "Preview error")
            return
        self.show_preview("Background", curve.get_processed())

    def preview_target(self, from_file):
        try:
            curve = load_target(self.target_file(from_file), self.num_points())
        except (OSError, ValueError):
            self.show_error("Couldn't read the curve", "Preview error")
            return
        self.show_preview("Target", curve.get_processed())

    def show_preview(self, title, data):
        window = PreviewWindow(title, data)
        self.previews = [p for p in self.previews if p.isVisible()] + [window]
        window.show()

    # ---------------------------------------------------------------- loop

    def on_go(self):
        try:
            background = load_background(self.bkg_path.text())
        except (OSError, ValueError):
            self.show_error("Can't load background curve", "File error")
            return
        try:
            target = load_target(
                self.target_file(self.target_source.currentIndex() == 1), self.num_points()
            )
        except (OSError, ValueError):
            self.show_error("Couldn't open the target file", "File open error")
            return

        if self.config.sim:
            length = self.slice_length.value()
        else:
            if not self.scope_pv.connected:
                self.show_error("Can't connect to scope PV", "Scope read error")
                return
            resolution = self.time_resolution()
            if not resolution:
                self.show_error("Can't read the scope time resolution", "Scope read error")
                return
            length = settings.scope_slice_length(self.pulse_length.value(), resolution)

        auto = self.config.auto_loop
        loop_settings = LoopSettings(
            gain=self.gain.value(),
            # When not autolooping these are ignored
            iterations=self.iterations.value() if auto else 200,
            tolerance=self.tolerance.value() if auto else 0,
            max_percent_change=self.max_change.value(),
            pulse_length=self.pulse_length.value(),
            slice_start=self.slice_start.value(),
            slice_length=length,
            averages=self.averages.value(),
            save_diag_files=self.save_files.isChecked(),
        )
        engine, warnings = build_engine(
            self.config,
            loop_settings,
            target,
            background,
            self.scope_pv,
            self.time_resolution_pv,
        )
        for message, caption in warnings:
            self.show_error(message, caption)
        self.open_loop_window(engine)

    def open_loop_window(self, engine):
        self.loop_window = LoopWindow(
            engine,
            self.config.auto_loop,
            self.config.auto_loop_wait,
            self.config.awg_ns_per_point,
            self.config.sim,
        )
        self.loop_window.closed.connect(self.on_loop_closed)
        # Place the loop window below this one, and stop another loop starting
        geometry = self.frameGeometry()
        self.loop_window.move(geometry.left(), geometry.bottom())
        self.centralWidget().setEnabled(False)
        self.menuBar().setEnabled(False)
        self.loop_window.show()

    def on_loop_closed(self):
        self.loop_window = None
        self.centralWidget().setEnabled(True)
        self.menuBar().setEnabled(True)
        if self.close_pending:
            self.close()

    # ---------------------------------------------------------------- menus

    def edit_config(self):
        if ConfigDialog(self.config, self.config_file, self).exec():
            self.populate_library(self.library.currentIndex())
            self.apply_config_to_ui()

    def edit_file(self, filename):
        try:
            FileEditDialog(filename, self).exec()
        except OSError as e:
            self.show_error("Couldn't open {0}:\n\n{1}".format(filename, e), "File error")

    # ---------------------------------------------------------------- misc

    def show_error(self, msg, caption):
        QMessageBox.critical(self, caption, msg)

    def closeEvent(self, event):
        if self.loop_window is not None:
            # The loop window stops its loop safely first, then closes
            self.close_pending = True
            self.loop_window.close()
            if self.loop_window is not None:
                event.ignore()
                return
        if self.task is not None:
            self.task.shutdown()
        self.current_state().save(self.state_file)
        close_pvs(self.scope_pv, self.time_resolution_pv)
        for preview in self.previews:
            preview.close()
        event.accept()
