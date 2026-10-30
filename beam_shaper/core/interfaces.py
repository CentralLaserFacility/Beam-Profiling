"""The small interfaces the loop needs from hardware. beam_shaper.hardware implements these."""

from typing import Optional, Protocol

import numpy as np


class FeedbackError(Exception):
    """The measured pulse shape couldn't be read."""


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


class Awg(Protocol):
    def read_normalised_shape(self) -> np.ndarray:
        """The current AWG trace, scaled so the DAC maximum is 1."""

    def write(self, points: np.ndarray, zero_to_end: bool, progress: Progress) -> None:
        """Write a normalised trace. zero_to_end also zeroes samples beyond len(points)."""


class Feedback(Protocol):
    def measure(self, progress: Progress) -> np.ndarray:
        """The current pulse shape, processed to match the target. Raises FeedbackError."""
