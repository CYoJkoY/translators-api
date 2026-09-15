import asyncio

from fastapi.testclient import TestClient

from translators_api import main
from translators_api.capabilities import CapabilitySupport, capabilities_for
from translators_api.config import Settings
from translators_api.service import TranslationResult, TranslationService, TranslationServiceError


def test_capabilities_for_is_conservative_and_deterministic():
    result = capabilities_for(["zeta", "alpha", "alpha"])

    assert list(result) == ["alpha", "zeta"]
    assert result["alpha"] == {
        "text": "supported",
        "html": "unknown",
        "auto_source": "unknown",
    }


def test_service_skips_providers_marked_unsupported():
    service = TranslationService(Settings(fallback_translators=["first", "second"]))
    service._available = {"first", "second"}
    service._capabilities = capabilities_for(service._available)
    service._capabilities["first"]["text"] = CapabilitySupport.UNSUPPORTED.value

    calls: list[str] = []

    def fake_translate(text, translator, source, target, timeout):
        calls.append(translator)
        return "translated"

    async def run():
        return await service.translate("hello", "en", "zh-CN", "auto")

    main_translate_sync = __import__("translators_api.service", fromlist=["_translate_sync"])
    original = main_translate_sync._translate_sync
    main_translate_sync._translate_sync = fake_translate
    try:
        result = asyncio.run(run())
    finally:
        main_translate_sync._translate_sync = original

    assert result == TranslationResult("translated", "second", False)
    assert calls == ["second"]


def test_service_rejects_explicit_unsupported_capability(monkeypatch):
    service = TranslationService(Settings())
    service._available = {"bing"}
    service._capabilities = capabilities_for(service._available)
    service._capabilities["bing"]["html"] = CapabilitySupport.UNSUPPORTED.value

    with monkeypatch.context() as context:
        context.setattr("translators_api.service._translate_html_sync", lambda *args: "unused")
        try:
            asyncio.run(service.translate_html("<p>hello</p>", "en", "zh-CN", "bing"))
        except TranslationServiceError as exc:
            assert str(exc) == "translator does not support required capability: html"
        else:
            raise AssertionError("unsupported HTML capability must fail")


def test_translator_endpoint_exposes_capabilities(monkeypatch):
    client = TestClient(main.app)
    main.settings.api_key = None
    main._rate_buckets.clear()
    monkeypatch.setattr(main.service, "provider_capabilities", lambda: {
        "bing": {
            "text": "supported",
            "html": "unknown",
            "auto_source": "unknown",
        }
    })
    monkeypatch.setattr(main, "available_translators", lambda: ["bing"])
    monkeypatch.setattr(main.service, "provider_states", lambda: {"bing": "closed"})

    response = client.get("/v1/translators")

    assert response.status_code == 200
    assert response.json()["capabilities"]["bing"]["html"] == "unknown"
