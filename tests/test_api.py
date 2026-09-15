import asyncio

import pytest
from fastapi.testclient import TestClient

from translators_api import main
from translators_api.service import TranslationResult


@pytest.fixture()
def client(monkeypatch):
    main.settings.api_key = None
    main.settings.rate_limit_requests = 1_000
    main.settings.rate_limit_window_seconds = 60
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


def test_batch_translation(client, monkeypatch):
    async def fake_translate(text, source, target, translator):
        return TranslationResult(f"translated:{text}", translator or "bing", False)

    monkeypatch.setattr(main.service, "translate", fake_translate)
    response = client.post(
        "/v1/translate/batch",
        json={"texts": ["a", "b", "c"], "source": "en", "target": "zh-CN"},
    )
    assert response.status_code == 200
    assert [item["translation"] for item in response.json()["items"]] == [
        "translated:a",
        "translated:b",
        "translated:c",
    ]


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
    monkeypatch.setattr(main, "available_translators", lambda: ["bing"])
    response = client.post(
        "/v1/translate",
        json={"text": "Hello", "translator": "unknown"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "translation_failed"


def test_authentication(client, monkeypatch):
    main.settings.api_key = "secret"
    response = client.get("/v1/translators")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

    response = client.get(
        "/v1/translators", headers={"Authorization": "Bearer secret"}
    )
    assert response.status_code == 200
    main.settings.api_key = None
