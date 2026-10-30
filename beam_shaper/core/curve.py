import logging
import os

import numpy as np

log = logging.getLogger(__name__)


class Curve:
    # Background and target curves never have a background subtracted
    supports_background = True

    def __init__(self, curve_array=np.array([]), name="unnamed"):
        """
        Creates a Curve object. The intialiser optionally takes the argument
        curve_array, which is an array specifying the curve. Alternatively
        it initalises an array of zeros, and curves can be loaded from files
        using the load() method.
        """

        self._num_points = 82
        self._trim_method = "off"
        self._curve = np.zeros(self._num_points)
        self._name = name

        if len(curve_array) > 0:
            self._curve = curve_array
            self._num_points = len(curve_array)

        self._processed = self._curve

    def name(self, name=None):
        if name:
            self._name = name
        else:
            return self._name

    def load(self, data, num_points=None, trim_method=None, name=None):
        """
        load(data, num_points=None, trim_method=None, name=None)

        Load a curve from an array or a file

        Parameters
        ----------
        data: ndarray or string
            If an array is supplied, it will be read directly and num_points and trim_method are
            ignored. If a string is passed, the file at that path will be loaded.
        num_points: int, optional
            The number of points required for the curve. If not set then the
            default number is used (usually 82)
        trim_method: string, optional
            The method used to manipulate the input into an array of num_points
            in length. Options are 'resample', 'truncate' and 'off' (default). If 'truncate'
            is chosen, arrays shorter that num_points are zero-padded. If 'off' the
            full input array is output.
        name: string, optional
            The name given to the curve. Defaults to either "manual" if data is supplied,
            or the filename of the loaded curve otherwise.

        Raises OSError or ValueError if the file can't be read.
        """

        if isinstance(data, np.ndarray):
            self._curve = data
            self._num_points = len(data)
            self._processed = data
            self._name = name if name else "manual"
            return

        if not num_points:
            num_points = self._num_points
        if not trim_method:
            trim_method = self._trim_method

        pathname = data
        self._curve = np.loadtxt(pathname)

        if trim_method == "resample":
            self._processed = self._resample(self._curve, num_points)
        elif trim_method == "truncate":
            self._processed = self._curve[:num_points]
            if np.size(self._processed) < num_points:
                self._processed = np.pad(
                    self._processed,
                    (0, num_points - np.size(self._processed)),
                    "constant",
                )
        elif trim_method == "off":
            self._processed = self._curve

        self._num_points = len(self._processed)
        self._name = name if name else pathname.split("/")[-1]

    def save(self, pathname, raw=False):
        """Save the raw or processed curve as a 1D text array."""
        np.savetxt(pathname, self._curve if raw else self._processed)

    def process(self, clip=False, norm=False, bkg=None, crop=None, resample=None):
        """
        Process the curve to prepare for the feedback loop. Each time this is run it starts
        from the raw curve data, so all desired processing parms must be specified each time.
        The steps are always applied in the order: bkg, crop, resample, clip, norm.

        Parameters
        ----------
        clip: bool
            Clip the negative values of the curve, replacing with zeros
        norm: bool
            Normalise the values to 1
        bkg: Curve, optional
            The Curve containing the background trace to be subtracted
        crop: tuple of ints, optional
            (start_point, length) - slice the trace, starting at start_point for length pixels
        resample: int, optional
            Resample the curve to this many points

        Results in a processed curve to be accessed by the get_processed() method
        """

        self._processed = self._curve

        if bkg is not None:
            if self.supports_background:
                self._processed = self._processed - bkg.get_raw()
            else:
                log.warning(
                    "Ignoring background: %s curves don't support background subtraction",
                    type(self).__name__,
                )
        if crop is not None:
            start, length = crop
            self._processed = self._processed[start : start + length]
        if resample is not None:
            self._processed = self._resample(self._processed, resample)
        if clip:
            self._processed = self._clip_neg(self._processed)
        if norm:
            self._processed = self._normalise(self._processed)

    def _resample(self, data, npoints):
        im = np.arange(0, len(data))
        ip = np.linspace(0, len(data) - 1, npoints)
        return np.interp(ip, im, data)

    def _clip_neg(self, data):
        return np.clip(data, 0, np.amax(data))

    def _normalise(self, data):
        if np.amax(np.abs(data)) != 0:
            return data / np.amax(np.abs(data))
        return data

    def get_raw(self):
        return self._curve

    def get_processed(self):
        return self._processed


class BkgCurve(Curve):
    supports_background = False


class TargetCurve(Curve):
    supports_background = False


LIBRARY_EXTENSION = ".curve"


def library_curves(folder):
    """Names of the target shapes in the library folder, sorted. Empty if the folder is missing."""
    try:
        files = os.listdir(folder)
    except OSError:
        return []
    return sorted(f[: -len(LIBRARY_EXTENSION)] for f in files if f.endswith(LIBRARY_EXTENSION))


def library_path(folder, name):
    return os.path.join(folder, name + LIBRARY_EXTENSION)


def load_background(path):
    """Raises OSError or ValueError if the file can't be read."""
    curve = BkgCurve(name="Background")
    curve.load(str(path))
    return curve


def load_target(path, num_points):
    """Load a target shape, resampled to num_points and normalised. Raises OSError or ValueError."""
    curve = TargetCurve(name="Target")
    curve.load(str(path), num_points=num_points, trim_method="resample")
    curve.process(clip=True, norm=True, resample=num_points)
    return curve
