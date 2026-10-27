import threading
import time
from datetime import date


class UsageGuard:
    """Protects the shared API key: one analysis at a time, a cooldown, a daily cap."""

    def __init__(self, daily_cap: int, cooldown_s: int, clock=time.time):
        self.daily_cap = daily_cap
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._lock = threading.Lock()
        self._day = date.today()
        self._count = 0
        self._last_finished = 0.0
        self._busy = False

    def try_start(self):
        """Returns (ok, message). If ok is True, the caller must call finish()."""
        with self._lock:
            today = date.today()
            if today != self._day:
                self._day, self._count = today, 0
            if self._count >= self.daily_cap:
                return False, "The daily limit for this free demo has been reached. Please try again tomorrow."
            if self._busy:
                return False, "Another analysis is running right now. Please try again in a minute."
            wait = self.cooldown_s - (self._clock() - self._last_finished)
            if wait > 0:
                return False, f"The demo is cooling down. Try again in about {int(wait) + 1} seconds."
            self._busy = True
            self._count += 1
            return True, ""

    def finish(self):
        with self._lock:
            self._busy = False
            self._last_finished = self._clock()