from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .models import (
    BatchItem,
    BatchTranslateRequest,
    BatchTranslateResponse,
    ErrorResponse,
    HtmlTranslateRequest,
    HtmlTranslateResponse,
    TranslateRequest,
    TranslateResponse,
)
from .service import (
    TranslationService,
    TranslationServiceError,
    UnknownTranslatorError,
    available_languages,
    available_translators,
)

settings = get_settings()
service = TranslationService(settings)

app = FastAPI(
    title="translators-api",
    version="0.1.0",
    description="Self-hosted HTTP gateway for the Translators Python library.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = asyncio.Lock()


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if value is None:
        value = f"req_{uuid.uuid4().hex}"
        request.state.request_id = value
    return value


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


async def authenticate(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    configured = settings.api_key
    if not configured:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    supplied = authorization[7:].strip()
    if not supplied or not secrets.compare_digest(supplied, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


async def enforce_rate_limit(request: Request) -> None:
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.headers.get('authorization', '')[:24]}"
    async with _rate_lock:
        bucket = _rate_buckets[key]
        cutoff = now - settings.rate_limit_window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            retry_after = max(1, int(bucket[0] + settings.rate_limit_window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


async def protected(request: Request, authorization: str | None = Header(default=None)) -> None:
    await authenticate(request, authorization)
    await enforce_rate_limit(request)


def ensure_length(value: str, maximum: int, field: str) -> None:
    if len(value) > maximum:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{field} exceeds the configured limit of {maximum} characters",
        )


def ensure_batch(request: BatchTranslateRequest) -> None:
    if len(request.texts) > settings.max_batch_items:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"batch exceeds the maximum of {settings.max_batch_items} items",
        )
    total = sum(len(item) for item in request.texts)
    if total > settings.max_batch_total_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"batch exceeds the configured total limit of {settings.max_batch_total_length} characters",
        )


@app.exception_handler(TranslationServiceError)
async def translation_error_handler(request: Request, exc: TranslationServiceError):
    rid = request_id(request)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error={"code": "translation_failed", "message": str(exc), "request_id": rid}
        ).model_dump(),
        headers={"X-Request-ID": rid},
    )


@app.exception_handler(UnknownTranslatorError)
async def unknown_translator_handler(request: Request, exc: UnknownTranslatorError):
    rid = request_id(request)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error={"code": "unknown_translator", "message": str(exc), "request_id": rid}
        ).model_dump(),
        headers={"X-Request-ID": rid},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    rid = request_id(request)
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = rid
    code = {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        413: "payload_too_large",
        429: "rate_limited",
    }.get(exc.status_code, "request_error")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error={"code": code, "message": str(exc.detail), "request_id": rid}
        ).model_dump(),
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    rid = request_id(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error={
                "code": "validation_error",
                "message": "request validation failed",
                "request_id": rid,
            }
        ).model_dump(),
        headers={"X-Request-ID": rid},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/ready")
async def ready() -> dict[str, str]:
    try:
        names = available_translators()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"translator engine unavailable: {type(exc).__name__}") from exc
    if not names:
        raise HTTPException(status_code=503, detail="no translators available")
    return {"status": "ready", "translators": str(len(names))}


@app.get("/v1/translators", dependencies=[Depends(protected)])
async def translators() -> dict[str, object]:
    names = available_translators()
    return {"translators": names, "default": settings.default_translator, "fallback": settings.fallback_translators}


@app.get("/v1/languages", dependencies=[Depends(protected)])
async def languages(translator: str = settings.default_translator) -> dict[str, object]:
    try:
        values = await asyncio.to_thread(available_languages, translator)
    except UnknownTranslatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"failed to load languages: {type(exc).__name__}") from exc
    return {"translator": translator, "languages": values}


@app.post("/v1/translate", response_model=TranslateResponse, dependencies=[Depends(protected)])
async def translate(request: Request, payload: TranslateRequest) -> TranslateResponse:
    ensure_length(payload.text, settings.max_text_length, "text")
    result = await service.translate(payload.text, payload.source, payload.target, payload.translator)
    return TranslateResponse(
        text=payload.text,
        translation=result.translation,
        source=payload.source,
        target=payload.target,
        translator=result.translator,
        fallback=result.fallback,
        request_id=request_id(request),
    )


@app.post("/v1/translate/batch", response_model=BatchTranslateResponse, dependencies=[Depends(protected)])
async def translate_batch(request: Request, payload: BatchTranslateRequest) -> BatchTranslateResponse:
    ensure_batch(payload)
    results = await asyncio.gather(
        *(
            service.translate(text, payload.source, payload.target, payload.translator)
            for text in payload.texts
        )
    )
    translators_used = {result.translator for result in results}
    translator_name = next(iter(translators_used)) if len(translators_used) == 1 else "mixed"
    return BatchTranslateResponse(
        items=[
            BatchItem(index=index, text=text, translation=result.translation)
            for index, (text, result) in enumerate(zip(payload.texts, results, strict=True))
        ],
        source=payload.source,
        target=payload.target,
        translator=translator_name,
        fallback=any(result.fallback for result in results),
        request_id=request_id(request),
    )


@app.post("/v1/translate/html", response_model=HtmlTranslateResponse, dependencies=[Depends(protected)])
async def translate_html(request: Request, payload: HtmlTranslateRequest) -> HtmlTranslateResponse:
    ensure_length(payload.html, settings.max_text_length, "html")
    result = await service.translate_html(payload.html, payload.source, payload.target, payload.translator)
    return HtmlTranslateResponse(
        html=payload.html,
        translation=result.translation,
        source=payload.source,
        target=payload.target,
        translator=result.translator,
        fallback=result.fallback,
        request_id=request_id(request),
    )
