# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build. Run from the repo folder:  uv run pyinstaller main.spec
# Output: dist/beam_shaper/, with beam_shaper.exe and everything it needs alongside it.

from PyInstaller.utils.hooks import collect_data_files

# Files the app reads from its own folder (see beam_shaper/paths.py). The user
# algorithm and filter stay as editable .py files next to the exe.
app_files = [
    ("gui_files", "gui_files"),
    ("curve_library", "curve_library"),
    ("config.ini", "."),
    ("user_algorithm.py", "."),
    ("user_filter.py", "."),
]

a = Analysis(
    ["main.py"],
    # Includes epics/clibs/<platform>/ca.dll and Com.dll, where pyepics looks for them
    datas=app_files + collect_data_files("epics"),
    # Imported by user_filter.py, which is loaded at run time so PyInstaller can't see it
    hiddenimports=["scipy.ndimage", "scipy.signal"],
    excludes=["tkinter", "matplotlib", "wx"],
)
# Dependency analysis can pick up another EPICS install's ca.dll/Com.dll from PATH
# (e.g. CA Lab). Only pyepics' own copies, under epics/clibs, belong in the build.
a.binaries = [b for b in a.binaries if b[0].lower() not in ("ca.dll", "com.dll")]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="beam_shaper",
    console=True,  # keeps a console showing the log, as before
    # Put everything next to the exe rather than in _internal/, so the app's own
    # folder (where it looks for config, curves and user files) is the exe's folder
    contents_directory=".",
)
coll = COLLECT(exe, a.binaries, a.datas, name="beam_shaper")
