"""Where the app's files live, independent of the folder it was started from."""

import sys
from pathlib import Path


def app_dir():
    """The folder holding main.py (or the exe, when packaged with PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve(path, base=None):
    """path as given if absolute, otherwise relative to base (default: the app folder)."""
    p = Path(path)
    return p if p.is_absolute() else Path(base or app_dir()) / p


DEFAULT_CONFIG = "config.ini"
LOCAL_CONFIG = "config.local.ini"  # This machine's settings; not in git
STATE_FILE = "state.txt"
LOG_FOLDER = "logs"
ICON_FOLDER = "gui_files"
