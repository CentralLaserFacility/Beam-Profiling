"""The small interfaces the loop needs from hardware. beam_shaper.hardware implements these."""

from typing import Callable, Optional, Protocol

import numpy as np


class FeedbackError(Exception):
    """The measured pulse shape couldn't be read."""


class AwgWriteError(Exception):
    """The AWG didn't end up holding the trace that was written. Its state is uncertain."""


class WriteCancelled(Exception):
    """A write was stopped part way. The AWG was returned to the trace it held before."""


class Progress(Protocol):
    """Reports progress of a slow hardware operation. The GUI decides how to show it."""

    def start(self, title: str, message: str, maximum: Optional[int] = None) -> None:
        """maximum=None means the length of the operation is unknown."""

    def update(self, value: Optional[int], message: str) -> None:
        """value=None means 'still busy' for operations of unknown length."""

    def finish(self) -> None: ...


class NullProgress:
    def start(self, title, message, maximum=None):
        pass

    def update(self, value, message):
        pass

    def finish(self):
        pass


def never_cancel():
    return False


class Awg(Protocol):
    def read_normalised_shape(self) -> np.ndarray:
        """The current AWG trace, scaled so the DAC maximum is 1."""

    def write(
        self,
        points: np.ndarray,
        zero_to_end: bool,
        progress: Progress,
        cancel: Callable[[], bool] = never_cancel,
    ) -> None:
        """Write a normalised trace and check the AWG now holds it.

        zero_to_end also zeroes samples beyond len(points). cancel() is polled during
        the write. Raises WriteCancelled (AWG restored) or AwgWriteError (readback wrong)."""


class Feedback(Protocol):
    def measure(self, progress: Progress) -> np.ndarray:
        """The current pulse shape, processed to match the target. Raises FeedbackError."""
