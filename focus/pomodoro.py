"""Pomodoro state machine: focus -> short break -> ... -> long break every N focus sessions.

Pure logic with an injectable clock, so it is testable without waiting 25 minutes.
"""
import time
from enum import Enum
from typing import Callable


class Phase(Enum):
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class Pomodoro:
    def __init__(
        self,
        focus_s: int = 25 * 60,
        short_break_s: int = 5 * 60,
        long_break_s: int = 15 * 60,
        focus_sessions_per_long_break: int = 4,
        clock: Callable[[], float] = time.monotonic,  # monotonic: immune to system clock changes
    ) -> None:
        self._durations = {Phase.FOCUS: focus_s, Phase.SHORT_BREAK: short_break_s, Phase.LONG_BREAK: long_break_s}
        self._sessions_per_long_break = focus_sessions_per_long_break
        self._clock = clock
        self.reset()

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def running(self) -> bool:
        return self._ends_at is not None

    @property
    def completed_focus_sessions(self) -> int:
        return self._completed_focus

    def remaining_s(self) -> float:
        if self._ends_at is None:
            return self._remaining_s
        return max(0.0, self._ends_at - self._clock())

    def toggle(self) -> None:
        if self.running:
            self._remaining_s = self.remaining_s()
            self._ends_at = None
        else:
            self._ends_at = self._clock() + self._remaining_s

    def reset(self) -> None:
        self._phase = Phase.FOCUS
        self._completed_focus = 0
        self._remaining_s = float(self._durations[Phase.FOCUS])
        self._ends_at: float | None = None

    def update(self) -> Phase | None:
        """Call periodically. Returns the new phase when the current one has just finished.

        The next phase starts paused: a break should not silently eat into work time and vice versa.
        """
        if not self.running or self.remaining_s() > 0:
            return None
        if self._phase is Phase.FOCUS:
            self._completed_focus += 1
            long_break_due = self._completed_focus % self._sessions_per_long_break == 0
            self._phase = Phase.LONG_BREAK if long_break_due else Phase.SHORT_BREAK
        else:
            self._phase = Phase.FOCUS
        self._remaining_s = float(self._durations[self._phase])
        self._ends_at = None
        return self._phase
