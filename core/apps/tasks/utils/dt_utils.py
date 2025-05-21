"""Module for all methods related to datetime."""
import time
from datetime import datetime
from typing import Union, Optional

from dateutil.parser import parse


class Timer:
    """A Timer utility to track elapsed time and manage time-based operations.

    The Timer class provides methods and properties to check whether a duration has elapsed,
    reset the timer, and increment the duration dynamically.

    Attributes:
        duration (float): The total duration the timer runs before expiring.
        start (float): The time the timer was started or last reset.

    Methods:
        reset(): Resets the timer to start counting from the current time.
        increment(increment: Union[int, float] = 0): Increases the timer's duration by a specified amount.
        expired: Checks if the timer has expired.
        not_expired: Checks if the timer is still active.
        at: Returns the elapsed time since the timer started or was reset.
    """

    def __init__(self, duration: Union[int, float] = 10):
        """Initializes the Timer with a specified duration in seconds.

        Args:
            duration (Union[int, float]): The duration for the timer in seconds. Defaults to 10 seconds.
        """
        self.duration = float(duration)
        self.start = time.perf_counter()

    def reset(self) -> None:
        """Resets the timer to start counting from the current time."""
        self.start = time.perf_counter()

    def increment(self, increment: Union[int, float] = 0) -> None:
        """Increases the timer's duration by a specified amount.

        Args:
            increment (Union[int, float]): The number of seconds to add to the timer's duration. Defaults to 0.
        """
        self.duration += float(increment)

    @property
    def expired(self) -> bool:
        """Checks if the timer's duration has elapsed.

        Returns:
            bool: True if the timer has expired, False otherwise.
        """
        return time.perf_counter() - self.start > self.duration

    @property
    def not_expired(self) -> bool:
        """Checks if the timer's duration has not yet elapsed.

        Returns:
            bool: True if the timer is still active, False otherwise.
        """
        return not self.expired

    @property
    def at(self) -> float:
        """Returns the elapsed time since the timer was started or last reset.

        Returns:
            float: The elapsed time in seconds.
        """
        return time.perf_counter() - self.start
