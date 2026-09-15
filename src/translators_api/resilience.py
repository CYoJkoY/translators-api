from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
import time


class FailureKind(str, Enum):
    TIMEOUT = "timeout"
    REQUEST = "request"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    kind: FailureKind
    retryable: bool
    detail: str


def classify_failure(exc: BaseException) -> ProviderFailure:
    if isinstance(exc, TimeoutError):
        return ProviderFailure(FailureKind.TIMEOUT, True, "provider request timed out")
    if isinstance(exc, ValueError):
        return ProviderFailure(FailureKind.REQUEST, False, "provider rejected the request")
    if isinstance(exc, (OSError, ConnectionError)):
        return ProviderFailure(FailureKind.PROVIDER, True, "provider connection failed")
    return ProviderFailure(FailureKind.UNKNOWN, True, "provider request failed")


@dataclass(slots=True)
class _Circuit:
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 30.0) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._circuits: dict[str, _Circuit] = {}
        self._lock = threading.Lock()

    def allow(self, provider: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            state = self._circuits.setdefault(provider, _Circuit())
            if state.opened_at is None:
                return True
            if current - state.opened_at < self.recovery_seconds:
                return False
            if state.probe_in_flight:
                return False
            state.probe_in_flight = True
            return True

    def record_success(self, provider: str) -> None:
        with self._lock:
            self._circuits[provider] = _Circuit()

    def record_failure(self, provider: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            state = self._circuits.setdefault(provider, _Circuit())
            state.failures += 1
            state.probe_in_flight = False
            state.opened_at = current if state.failures >= self.failure_threshold else state.opened_at

    def state(self, provider: str, now: float | None = None) -> str:
        current = time.monotonic() if now is None else now
        with self._lock:
            state = self._circuits.setdefault(provider, _Circuit())
            if state.opened_at is None:
                return "closed"
            if current - state.opened_at >= self.recovery_seconds:
                return "half_open"
            return "open"

    def snapshot(self, providers: list[str], now: float | None = None) -> dict[str, str]:
        return {provider: self.state(provider, now) for provider in providers}
