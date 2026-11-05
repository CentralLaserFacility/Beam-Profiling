import logging
import sys

from PySide6.QtWidgets import QApplication

from beam_shaper.core.config import AppConfig
from beam_shaper.hardware.epics_scope import configure_epics


def main(config_file="./config.ini", state_file="./state.txt"):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s: %(message)s", datefmt="%b_%d_%H:%M.%S"
    )
    app = QApplication(sys.argv)
    config = AppConfig.load(config_file)
    # EPICS must be configured before the first PV is created
    configure_epics(config.epics_ca_addr_list, config.epics_ca_auto_addr_list)
    config.ensure_diag_folder()

    from beam_shaper.ui.setup_window import SetupWindow

    window = SetupWindow(config, config_file, state_file)
    window.show()
    return app.exec()
