from __future__ import annotations

import asyncio
from dataclasses import dataclass

import translators as ts

from .config import Settings


class TranslationServiceError(RuntimeError):
    """Raised when a configured translator cannot complete a request."""


class UnknownTranslatorError(ValueError):
    """Raised when a client requests a translator that is not available."""


@dataclass(slots=True)
class TranslationResult:
    translation: str
    translator: str
    fallback: bool


def available_translators() -> list[str]:
    pool = ts.translators_pool
    names = pool.keys() if isinstance(pool, dict) else pool
    return sorted({str(name) for name in names if str(name) not in {"auto", "detect", "all"}})


def available_languages(translator: str) -> list[str]:
    if translator not in available_translators():
        raise UnknownTranslatorError(f"unknown translator: {translator}")
    languages = ts.get_languages(translator)
    if isinstance(languages, dict):
        values: list[str] = []
        for key, value in languages.items():
            values.append(str(key))
            if isinstance(value, (list, tuple, set)):
                values.extend(str(item) for item in value)
            else:
                values.append(str(value))
        return sorted(set(values))
    if isinstance(languages, (list, tuple, set)):
        return sorted({str(value) for value in languages})
    return [str(languages)]


def _translate_sync(text: str, translator: str, source: str, target: str, timeout: float) -> str:
    result = ts.translate_text(
        query_text=text,
        translator=translator,
        from_language=source,
        to_language=target,
        timeout=timeout,
        if_print_warning=False,
    )
    return str(result)


def _translate_html_sync(
    html: str, translator: str, source: str, target: str, timeout: float
) -> str:
    result = ts.translate_html(
        query_text=html,
        translator=translator,
        from_language=source,
        to_language=target,
        timeout=timeout,
        if_print_warning=False,
    )
    return str(result)


class TranslationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._available = set(available_translators())

    def _candidates(self, translator: str | None) -> tuple[list[str], bool]:
        requested = translator or self.settings.default_translator
        if requested.lower() not in {"auto", "detect", "all"}:
            if requested not in self._available:
                raise UnknownTranslatorError(f"unknown translator: {requested}")
            return [requested], False

        candidates = list(dict.fromkeys(self.settings.fallback_translators))
        candidates = [name for name in candidates if name in self._available]
        if not candidates:
            raise TranslationServiceError("no configured fallback translators are available")
        return candidates, True

    async def translate(
        self, text: str, source: str, target: str, translator: str | None
    ) -> TranslationResult:
        candidates, auto = self._candidates(translator)
        errors: list[str] = []
        for index, name in enumerate(candidates):
            try:
                result = await asyncio.to_thread(
                    _translate_sync,
                    text,
                    name,
                    source,
                    target,
                    self.settings.upstream_timeout,
                )
                if not result:
                    raise TranslationServiceError("translator returned an empty result")
                return TranslationResult(result, name, auto and index > 0)
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")

        raise TranslationServiceError(
            "all translators failed" + (f" ({'; '.join(errors)})" if errors else "")
        )

    async def translate_html(
        self, html: str, source: str, target: str, translator: str | None
    ) -> TranslationResult:
        candidates, auto = self._candidates(translator)
        errors: list[str] = []
        for index, name in enumerate(candidates):
            try:
                result = await asyncio.to_thread(
                    _translate_html_sync,
                    html,
                    name,
                    source,
                    target,
                    self.settings.upstream_timeout,
                )
                if not result:
                    raise TranslationServiceError("translator returned an empty result")
                return TranslationResult(result, name, auto and index > 0)
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")

        raise TranslationServiceError(
            "all translators failed" + (f" ({'; '.join(errors)})" if errors else "")
        )
