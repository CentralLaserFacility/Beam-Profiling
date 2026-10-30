"""Load the user-editable correction algorithm and AWG filter from Python files."""

import os
import types

from beam_shaper.core.correction import default_correction, no_filter


class PluginError(Exception):
    pass


def _load_function(filename, attribute):
    """Import filename as a fresh module and return its `attribute`.

    Raises PluginError with a user-readable message on any failure."""
    if not os.path.isfile(filename):
        raise PluginError("Can't find file {0}".format(os.path.abspath(filename)))
    module = types.ModuleType(os.path.splitext(os.path.basename(filename))[0])
    module.__file__ = filename
    try:
        # Compile from source every time: the bytecode cache can miss quick edits
        with open(filename) as f:
            source = f.read()
        exec(compile(source, filename, "exec"), module.__dict__)
        function = getattr(module, attribute)
    except Exception as e:
        raise PluginError("Error in {0}:\n\n{1}".format(filename, e)) from e
    if not callable(function):
        raise PluginError("{0} in {1} is not a function".format(attribute, filename))
    return function


def load_correction_algorithm(filename):
    """Returns (function, error message or None). Falls back to the default algorithm."""
    try:
        return _load_function(filename, "calc_correction"), None
    except PluginError as e:
        return default_correction, str(e) + "\n\nUsing the default algorithm"


def load_awg_filter(filename):
    """Returns (function, error message or None). Falls back to no filtering."""
    try:
        return _load_function(filename, "awg_filter"), None
    except PluginError as e:
        return no_filter, str(e) + "\n\nNo filter will be applied"
