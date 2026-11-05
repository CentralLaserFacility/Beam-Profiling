"""The setup window's fields, remembered between sessions in state.txt."""

import configparser
from dataclasses import dataclass

from beam_shaper.core import settings

# (section, key) in state.txt for each field. Same format as the wx version.
_KEYS = {
    "bkg_path": ("Traces", "bkg_path"),
    "target_path": ("Traces", "tkg_path"),
    "library_index": ("Traces", "lib_index"),
    "scope_pv": ("Scope", "scope_pv"),
    "averages": ("Scope", "averages"),
    "slice_start": ("Scope", "start"),
    "slice_length": ("Scope", "length"),
    "target_from_file": ("Parms", "tgt_src"),
    "pulse_length": ("Parms", "pulse_length"),
    "gain": ("Parms", "gain"),
    "iterations": ("Parms", "iterations"),
    "tolerance": ("Parms", "tolerance"),
    "max_change": ("Parms", "max_change"),
    "save_files": ("Parms", "save_files"),
}


@dataclass
class SetupState:
    bkg_path: str = ""
    target_path: str = ""
    library_index: int = 0
    scope_pv: str = ""
    averages: int = 1
    slice_start: int = 273
    slice_length: int = 410
    target_from_file: bool = False
    pulse_length: float = 10.0
    gain: float = 0.1
    iterations: int = 30
    tolerance: float = 0.05
    max_change: int = 25
    save_files: bool = True

    @classmethod
    def load(cls, filename="./state.txt"):
        """Read state.txt. Missing or invalid values (e.g. "N/A") keep their defaults."""
        parser = configparser.RawConfigParser()
        parser.read(filename)
        state = cls()

        def get(name):
            section, key = _KEYS[name]
            return parser.get(section, key, fallback=None)

        def setter(name, convert):
            text = get(name)
            if text is None:
                return
            try:
                setattr(state, name, convert(text))
            except ValueError:
                pass

        setter("bkg_path", str)
        setter("target_path", str)
        setter("library_index", int)
        setter("scope_pv", str)
        setter("averages", lambda t: max(1, int(t)))
        setter("slice_start", int)
        setter("slice_length", int)
        setter("target_from_file", lambda t: int(t) == 1)  # combo index: 0 library, 1 file
        setter("pulse_length", float)
        setter("gain", settings.coerce_gain)
        setter("iterations", settings.coerce_iterations)
        setter("tolerance", settings.coerce_tolerance)
        setter("max_change", settings.coerce_max_percentage_change)
        setter("save_files", lambda t: int(t) == 0)  # radio index: 0 yes, 1 no
        return state

    def save(self, filename="./state.txt"):
        values = {
            "bkg_path": self.bkg_path,
            "target_path": self.target_path,
            "library_index": self.library_index,
            "scope_pv": self.scope_pv,
            "averages": self.averages,
            "slice_start": self.slice_start,
            "slice_length": self.slice_length,
            "target_from_file": 1 if self.target_from_file else 0,
            "pulse_length": self.pulse_length,
            "gain": self.gain,
            "iterations": self.iterations,
            "tolerance": self.tolerance,
            "max_change": self.max_change,
            "save_files": 0 if self.save_files else 1,
        }
        parser = configparser.RawConfigParser()
        for name, (section, key) in _KEYS.items():
            if not parser.has_section(section):
                parser.add_section(section)
            parser.set(section, key, str(values[name]))
        with open(filename, "w") as f:
            parser.write(f)
