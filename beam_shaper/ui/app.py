import logging
import logging.handlers
import sys

from PySide6.QtWidgets import QApplication

from beam_shaper import paths
from beam_shaper.core.config import AppConfig
from beam_shaper.hardware.epics_scope import configure_epics

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(log_dir):
    """Log to the console and to a daily file in log_dir, kept for 90 days."""
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s: %(message)s", "%b_%d_%H:%M.%S"))
    handlers = [console]
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = logging.handlers.TimedRotatingFileHandler(
            log_dir / "beam_shaper.log", when="midnight", backupCount=90, encoding="utf-8"
        )
        log_file.setFormatter(logging.Formatter(LOG_FORMAT))
        handlers.append(log_file)
    except OSError as e:
        print("Can't write log files to {0}: {1}".format(log_dir, e), file=sys.stderr)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def main(app_dir=None, argv=None):
    """Start the GUI. With --check, check the installation instead and exit (0 if all is well)."""
    argv = sys.argv[1:] if argv is None else argv
    app_dir = paths.resolve(app_dir) if app_dir else paths.app_dir()
    local_config = app_dir / paths.LOCAL_CONFIG
    config = AppConfig.load(app_dir / paths.DEFAULT_CONFIG, local_config, base_dir=app_dir)

    if "--check" in argv:
        from beam_shaper.session import check_installation

        print("Checking installation in", app_dir)
        return 0 if check_installation(config) else 1

    setup_logging(app_dir / paths.LOG_FOLDER)
    log = logging.getLogger("beam_shaper")
    log.info("Starting from %s", app_dir)

    app = QApplication(sys.argv)
    # EPICS must be configured before the first PV is created
    configure_epics(config.epics_ca_addr_list, config.epics_ca_auto_addr_list)
    config.ensure_diag_folder()

    from beam_shaper.ui.setup_window import SetupWindow

    window = SetupWindow(config, str(local_config), str(app_dir / paths.STATE_FILE))
    window.show()
    code = app.exec()
    log.info("Exiting")
    return code
