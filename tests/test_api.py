import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from translators_api import main
from translators_api.config import Settings
from translators_api.service import TranslationResult, TranslationService, TranslationServiceError


@pytest.fixture()
def client():
    main.settings.api_key = None
    main.settings.rate_limit_requests = 1_000
    main.settings.rate_limit_window_seconds = 60
    main.settings.batch_timeout = 120.0
    main._rate_buckets.clear()
    return TestClient(main.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"].startswith("req_")


def test_translate(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        return TranslationResult("你好，世界", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post(
        "/v1/translate",
        json={"text": "Hello, world!", "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["translation"] == "你好，世界"
    assert body["translator"] == "bing"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_translate_records_metrics(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        return TranslationResult("你好", "bing", True)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post("/v1/translate", json={"text": "hello"})
    assert response.status_code == 200

    metrics = client.get("/metrics").text
    assert "translators_api_translations_total" in metrics
    assert "translators_api_translation_fallback_total" in metrics
    assert 'translator="bing"' in metrics


def test_batch_translation(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        return TranslationResult(f"translated:{text}", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post(
        "/v1/translate/batch",
        json={"texts": ["a", "b", "c"], "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["translation"] for item in body["items"]] == [
        "translated:a",
        "translated:b",
        "translated:c",
    ]
    assert all(item["status"] == "success" for item in body["items"])
    assert body["completed"] == 3
    assert body["failed"] == 0
    assert body["partial_success"] is False
    assert body["deadline_exceeded"] is False


def test_batch_preserves_success_when_one_item_fails(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        if text == "bad":
            raise TranslationServiceError("provider unavailable")
        return TranslationResult(f"translated:{text}", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post(
        "/v1/translate/batch",
        json={"texts": ["a", "bad", "c"], "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] == 2
    assert body["failed"] == 1
    assert body["partial_success"] is True
    assert body["deadline_exceeded"] is False
    assert body["items"] == [
        {
            "text": "a",
            "translation": "translated:a",
            "index": 0,
            "status": "success",
            "error_code": None,
            "error_message": None,
        },
        {
            "text": "bad",
            "translation": None,
            "index": 1,
            "status": "error",
            "error_code": "translation_failed",
            "error_message": "translation failed",
        },
        {
            "text": "c",
            "translation": "translated:c",
            "index": 2,
            "status": "success",
            "error_code": None,
            "error_message": None,
        },
    ]


def test_batch_deadline_marks_unfinished_items(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        if text == "slow":
            await asyncio.sleep(0.05)
        return TranslationResult(f"translated:{text}", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    monkeypatch.setattr(main.settings, "batch_timeout", 0.01)

    response = client.post(
        "/v1/translate/batch",
        json={"texts": ["fast", "slow"], "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] == 1
    assert body["failed"] == 1
    assert body["partial_success"] is True
    assert body["deadline_exceeded"] is True
    assert body["items"][0]["status"] == "success"
    assert body["items"][1]["error_code"] == "batch_timeout"


def test_batch_all_items_fail_without_http_5xx(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        raise TranslationServiceError("provider unavailable")

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post("/v1/translate/batch", json={"texts": ["a", "b"]})
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] == 0
    assert body["failed"] == 2
    assert body["partial_success"] is False
    assert body["translator"] == "none"
    assert all(item["status"] == "error" for item in body["items"])


def test_html_translation(client, monkeypatch):
    async def fake_translate_html(html, source, target, translator):
        return TranslationResult("<p>你好</p>", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate_html", fake_translate_html)
    response = client.post(
        "/v1/translate/html",
        json={"html": "<p>Hello</p>", "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    assert response.json()["translation"] == "<p>你好</p>"


def test_unknown_translator(client, monkeypatch):
    monkeypatch.setattr(main.service, "_available", {"bing"})
    response = client.post(
        "/v1/translate",
        json={"text": "Hello", "translator": "unknown"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_translator"


def test_validation_error(client):
    response = client.post("/v1/translate", json={"text": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_payload_limit(client, monkeypatch):
    monkeypatch.setattr(main.settings, "max_text_length", 4)
    response = client.post("/v1/translate", json={"text": "hello"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_batch_item_limit(client, monkeypatch):
    monkeypatch.setattr(main.settings, "max_batch_items", 2)
    response = client.post("/v1/translate/batch", json={"texts": ["a", "b", "c"]})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_batch_total_length_limit(client, monkeypatch):
    monkeypatch.setattr(main.settings, "max_batch_total_length", 3)
    response = client.post("/v1/translate/batch", json={"texts": ["ab", "cd"]})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_authentication(client):
    main.settings.api_key = "secret"
    response = client.get("/v1/translators")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

    response = client.get(
        "/v1/translators", headers={"Authorization": "Bearer secret"}
    )
    assert response.status_code == 200
    main.settings.api_key = None


def test_rate_limit(client, monkeypatch):
    main.settings.rate_limit_requests = 1
    main.settings.rate_limit_window_seconds = 60
    main._rate_buckets.clear()

    assert client.get("/v1/translators").status_code == 200
    response = client.get("/v1/translators")
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert response.json()["error"]["code"] == "rate_limited"

    metrics = client.get("/metrics").text
    assert "translators_api_rate_limit_rejections_total" in metrics


def test_readiness_failure(client, monkeypatch):
    monkeypatch.setattr(main, "available_translators", lambda: [])
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "request_error"


def test_service_error_contract(client, monkeypatch):
    async def failed_translate(text, source, target, translator):
        raise main.TranslationServiceError("provider timeout")

    monkeypatch.setattr(main.service, "translate", failed_translate)
    response = client.post("/v1/translate", json={"text": "hello"})
    assert response.status_code == 502
    assert response.json()["error"]["message"] == "all configured translators failed"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_service_fallback(monkeypatch):
    settings = main.settings.model_copy(
        update={"fallback_translators": ["first", "second"], "upstream_timeout": 1.5}
    )
    service = TranslationService(settings)
    service._available = {"first", "second"}
    calls: list[tuple[str, float]] = []

    def fake_translate(text, translator, source, target, timeout):
        calls.append((translator, timeout))
        if translator == "first":
            raise TimeoutError
        return "translated"

    monkeypatch.setattr("translators_api.service._translate_sync", fake_translate)
    result = asyncio.run(service.translate("hello", "en", "zh-CN", "auto"))
    assert result == TranslationResult("translated", "second", True)
    assert calls == [("first", 1.5), ("second", 1.5)]


def test_invalid_runtime_settings_are_rejected():
    with pytest.raises(ValidationError):
        Settings(rate_limit_requests=0)
    with pytest.raises(ValidationError):
        Settings(port=70_000)
