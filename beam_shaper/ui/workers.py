"""Run slow hardware work off the GUI thread, reporting back through Qt signals.

Signals emitted from a worker thread are queued, so connected slots run on the GUI thread.
"""

import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal, Slot

from beam_shaper.core.loop import Decision
from beam_shaper.session import prepare_worker_thread

log = logging.getLogger(__name__)

# Progress values sent through signals: -1 means unknown maximum / still busy
UNKNOWN = -1


class ProgressSignals(QObject):
    started = Signal(str, str, int)  # title, message, maximum
    updated = Signal(int, str)  # value, message
    finished = Signal()


class QtProgress:
    """beam_shaper.core.interfaces.Progress that forwards to Qt signals."""

    def __init__(self, signals):
        self.signals = signals

    def start(self, title, message, maximum=None):
        self.signals.started.emit(title, message, UNKNOWN if maximum is None else maximum)

    def update(self, value, message):
        self.signals.updated.emit(UNKNOWN if value is None else value, message)

    def finish(self):
        self.signals.finished.emit()


class LoopWorker(QObject):
    """Runs a LoopEngine in its own thread. Create it, then call start_run()."""

    updated = Signal(object)  # LoopSnapshot
    approval_needed = Signal(object)  # LoopSnapshot; answer with respond()
    warning = Signal(str, str)  # message, caption
    finished = Signal(object)  # LoopResult, or None if the run failed
    failed = Signal(str)

    _run_requested = Signal()

    def __init__(self, engine, sim):
        super().__init__()
        self.engine = engine
        self.sim = sim
        self.progress = ProgressSignals()
        engine.progress = QtProgress(self.progress)
        engine.on_warning = self.warning.emit

        self._started = False
        self._stop = threading.Event()
        self._reply_ready = threading.Event()
        self._reply = None
        self.running = False
        self.awaiting_approval = False

        self.thread = QThread()
        self.moveToThread(self.thread)
        self.progress.moveToThread(self.thread)
        self._run_requested.connect(self._run)
        # A lambda runs on the emitting thread - here the new worker thread, as intended
        self.thread.started.connect(lambda: prepare_worker_thread(self.sim))
        self.thread.start()

    # ------------------------------------------------------- GUI thread API

    def start_run(self):
        """Start (or resume after a pause) the loop."""
        self.running = True
        self._stop.clear()
        self._run_requested.emit()

    def respond(self, decision, gain):
        """Answer an approval_needed request."""
        if not self.awaiting_approval:
            return
        self.awaiting_approval = False
        self._reply = (decision, gain)
        self._reply_ready.set()

    def request_stop(self):
        self._stop.set()

    def shutdown(self):
        """Stop the thread. Only call once the run has finished."""
        self.thread.quit()
        self.thread.wait()

    # ------------------------------------------------------- worker thread

    @Slot()
    def _run(self):
        result = None
        try:
            if not self._started:
                self.engine.start()
                self._started = True
                self.updated.emit(self.engine.snapshot())
            result = self.engine.run(
                self._approve,
                should_stop=self._stop.is_set,
                on_update=lambda engine: self.updated.emit(engine.snapshot()),
            )
            self.updated.emit(self.engine.snapshot())
        except Exception as e:
            log.exception("Loop failed")
            self.failed.emit(str(e))
        finally:
            self.running = False
            self.finished.emit(result)

    def _approve(self, engine):
        self._reply_ready.clear()
        self.awaiting_approval = True
        self.approval_needed.emit(engine.snapshot())
        self._reply_ready.wait()
        return self._reply


class TaskWorker(QObject):
    """Runs fn(progress) once in a new thread. Delete with shutdown() after finished."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, fn, sim):
        super().__init__()
        self.fn = fn
        self.sim = sim
        self.progress = ProgressSignals()
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.progress.moveToThread(self.thread)
        self.thread.started.connect(self._run)

    def start(self):
        self.thread.start()

    def shutdown(self):
        self.thread.quit()
        self.thread.wait()

    @Slot()
    def _run(self):
        prepare_worker_thread(self.sim)
        try:
            self.succeeded.emit(self.fn(QtProgress(self.progress)))
        except Exception as e:
            log.exception("Task failed")
            self.failed.emit(str(e))
        finally:
            self.finished.emit()


class LogEmitter(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Sends formatted log records to a Qt signal, from any thread."""

    def __init__(self, fmt="%(asctime)s: %(message)s", datefmt="%b_%d_%H:%M.%S"):
        super().__init__()
        self.emitter = LogEmitter()
        self.setFormatter(logging.Formatter(fmt, datefmt))

    def emit(self, record):
        self.emitter.message.emit(self.format(record))
