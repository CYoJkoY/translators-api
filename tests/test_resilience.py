from __future__ import annotations

import asyncio

import pytest

from translators_api.config import Settings
from translators_api.resilience import CircuitBreaker, FailureKind, classify_failure
from translators_api.service import TranslationService, TranslationServiceError


def test_classify_timeout_as_retryable():
    failure = classify_failure(TimeoutError())
    assert failure.kind is FailureKind.TIMEOUT
    assert failure.retryable is True


def test_classify_value_error_as_non_retryable_request_error():
    failure = classify_failure(ValueError("unsupported language"))
    assert failure.kind is FailureKind.REQUEST
    assert failure.retryable is False


def test_classify_connection_failure_as_retryable():
    failure = classify_failure(ConnectionError("offline"))
    assert failure.kind is FailureKind.PROVIDER
    assert failure.retryable is True


def test_circuit_opens_after_threshold_and_recovers():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=10)

    assert breaker.allow("bing", now=0) is True
    breaker.record_failure("bing", now=0)
    assert breaker.state("bing", now=0) == "closed"

    assert breaker.allow("bing", now=1) is True
    breaker.record_failure("bing", now=1)
    assert breaker.state("bing", now=1) == "open"
    assert breaker.allow("bing", now=5) is False

    assert breaker.state("bing", now=12) == "half_open"
    assert breaker.allow("bing", now=12) is True
    assert breaker.state("bing", now=12) == "half_open"
    assert breaker.allow("bing", now=12) is False
    breaker.record_success("bing")
    assert breaker.state("bing", now=12) == "closed"
    assert breaker.allow("bing", now=13) is True


def test_half_open_probe_failure_reopens_circuit():
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=10)
    breaker.record_failure("bing", now=0)

    assert breaker.allow("bing", now=11) is True
    assert breaker.allow("bing", now=11) is False
    breaker.record_failure("bing", now=11)
    assert breaker.state("bing", now=11) == "open"
    assert breaker.allow("bing", now=12) is False


def test_explicit_translator_respects_open_circuit():
    settings = Settings(circuit_failure_threshold=1, circuit_recovery_seconds=60)
    service = TranslationService(settings)
    service._available = {"bing"}
    service._circuits.record_failure("bing")

    with pytest.raises(TranslationServiceError, match="circuit"):
        asyncio.run(service.translate("hello", "en", "zh-CN", "bing"))


def test_auto_mode_does_not_reserve_multiple_half_open_probes():
    settings = Settings(
        fallback_translators=["first", "second"],
        circuit_failure_threshold=1,
        circuit_recovery_seconds=10,
    )
    service = TranslationService(settings)
    service._available = {"first", "second"}
    service._circuits.record_failure("first", now=0)
    service._circuits.record_failure("second", now=0)

    # Probe ownership is acquired only when a provider is actually attempted.
    assert service._circuits.allow("first", now=11) is True
    assert service._circuits.allow("first", now=11) is False
    assert service._circuits.allow("second", now=11) is True


def test_invalid_circuit_configuration_is_rejected():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(recovery_seconds=0)
