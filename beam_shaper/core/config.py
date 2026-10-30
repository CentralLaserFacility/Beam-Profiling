"""Application configuration held in config.ini, independent of any GUI."""

import configparser
import os
from dataclasses import dataclass, field, fields


def _opt(section, label, default, choices=None):
    return field(
        default=default,
        metadata={"section": section, "label": label, "choices": choices},
    )


@dataclass
class AppConfig:
    diag: str = _opt("file_locations", "Diagnostic files location", "./diag_files/")
    curve: str = _opt("file_locations", "Library files location", "./curve_library/")
    filter: str = _opt("file_locations", "Filter file", "./user_filter.py")
    algorithm: str = _opt("file_locations", "Algorithm file", "./user_algorithm.py")
    pulse_peak_power: float = _opt("safety", "Peak Power", 20.0)
    auto_loop: bool = _opt("safety", "Auto loop", True)
    auto_loop_wait: int = _opt("timing", "Auto loop wait (s)", 3)
    scope_wait: float = _opt("timing", "Scope read wait (s)", 2.1)
    awg_wait: float = _opt("timing", "AWG write wait (s)", 0.5)
    scope: str = _opt("pvs", "Default scope PV", "")
    awg_prefix: str = _opt("pvs", "AWG_PV prefix", "AWG")
    sim: bool = _opt("sim", "Simulation", True)
    awg_zero_shift: float = _opt("awg", "AWG zero shift", 0.1)
    noise_threshold_percentage: float = _opt("awg", "Noise threshold (%)", 3.0)
    awg_ns_per_point: float = _opt("awg", "AWG calib (ns/point)", 0.125)
    awg_write_method: str = _opt("awg", "AWG write method", "pts", ("pts", "wfm"))
    epics_ca_addr_list: str = _opt("epics", "Channel Access addr list", "")
    epics_ca_auto_addr_list: str = _opt(
        "epics", "Channel Access auto addr list", "No", ("No", "Yes")
    )

    @staticmethod
    def options():
        """The fields of the config, with their metadata, in display order."""
        return fields(AppConfig)

    def set_from_string(self, name, text):
        """Set a field from user-entered text, converting to the field's type.

        Raises ValueError if the text can't be converted."""
        f = next(f for f in fields(self) if f.name == name)
        if f.type is bool:
            value = text if isinstance(text, bool) else _parse_bool(text)
        elif f.type is int:
            value = int(text)
        elif f.type is float:
            value = float(text)
        else:
            value = str(text)
            choices = f.metadata["choices"]
            if choices and value not in choices:
                raise ValueError(
                    "{0} must be one of: {1}".format(f.metadata["label"], ", ".join(choices))
                )
        setattr(self, name, value)

    @classmethod
    def load(cls, filename="./config.ini"):
        parser = configparser.RawConfigParser()
        parser.read(filename)
        config = cls()
        for f in fields(cls):
            section = f.metadata["section"]
            if parser.has_option(section, f.name):
                config.set_from_string(f.name, parser.get(section, f.name))
        return config

    def save(self, filename="./config.ini"):
        # Read the existing file first so unknown sections and keys survive
        parser = configparser.RawConfigParser()
        parser.read(filename)
        for f in fields(self):
            section = f.metadata["section"]
            if not parser.has_section(section):
                parser.add_section(section)
            parser.set(section, f.name, str(getattr(self, f.name)))
        with open(filename, "w") as configfile:
            parser.write(configfile)

    def ensure_diag_folder(self):
        if not os.path.exists(self.diag):
            os.makedirs(self.diag)


def _parse_bool(text):
    lowered = str(text).strip().lower()
    if lowered in ("1", "yes", "true", "on"):
        return True
    if lowered in ("0", "no", "false", "off"):
        return False
    raise ValueError("Not a boolean: %r" % text)
