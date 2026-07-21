"""Simple in-process circuit breaker for provider calls."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


class CircuitOpenError(RuntimeError):
    """Raised when a circuit is open and calls are short-circuited."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_timeout_sec: float = 60.0
    _failures: int = 0
    _opened_at: float | None = None
    _lock: Lock = field(default_factory=Lock)

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            # Half-open once recovery timeout elapses.
            return time.monotonic() - self._opened_at >= self.recovery_timeout_sec

    def before_call(self) -> None:
        if not self.allow():
            raise CircuitOpenError(f"circuit open: {self.name}")

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    def status(self) -> dict[str, object]:
        with self._lock:
            state = "closed"
            if self._opened_at is not None:
                elapsed = time.monotonic() - self._opened_at
                state = (
                    "half_open"
                    if elapsed >= self.recovery_timeout_sec
                    else "open"
                )
            return {
                "name": self.name,
                "state": state,
                "failures": self._failures,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_sec": self.recovery_timeout_sec,
            }
