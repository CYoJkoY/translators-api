from __future__ import annotations

import asyncio
import hashlib
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
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
_metrics_lock = threading.Lock()
_metrics = {
    "http_requests_total": 0,
    "http_request_failures_total": 0,
    "http_request_duration_seconds_sum": 0.0,
    "http_request_duration_seconds_count": 0,
    "translations_total": 0,
    "translation_failures_total": 0,
    "translation_fallback_total": 0,
    "rate_limit_rejections_total": 0,
    "readiness_failures_total": 0,
}
_translations_by_translator: dict[str, int] = defaultdict(int)


def _metric_inc(name: str, value: int = 1) -> None:
    with _metrics_lock:
        _metrics[name] += value


def _metric_observe_duration(value: float) -> None:
    with _metrics_lock:
        _metrics["http_request_duration_seconds_sum"] += value
        _metrics["http_request_duration_seconds_count"] += 1


def _metric_translation(translator: str, fallback: bool = False) -> None:
    with _metrics_lock:
        _metrics["translations_total"] += 1
        _translations_by_translator[translator] += 1
        if fallback:
            _metrics["translation_fallback_total"] += 1


def _escape_metric_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_metrics() -> str:
    with _metrics_lock:
        snapshot = dict(_metrics)
        by_translator = dict(_translations_by_translator)

    lines = [
        "# HELP translators_api_http_requests_total Total HTTP requests handled.",
        "# TYPE translators_api_http_requests_total counter",
        f"translators_api_http_requests_total {snapshot['http_requests_total']}",
        "# HELP translators_api_http_request_failures_total Total HTTP requests ending in a 4xx or 5xx response.",
        "# TYPE translators_api_http_request_failures_total counter",
        f"translators_api_http_request_failures_total {snapshot['http_request_failures_total']}",
        "# HELP translators_api_http_request_duration_seconds_sum Sum of HTTP request durations in seconds.",
        "# TYPE translators_api_http_request_duration_seconds_sum counter",
        f"translators_api_http_request_duration_seconds_sum {snapshot['http_request_duration_seconds_sum']}",
        "# HELP translators_api_http_request_duration_seconds_count Number of observed HTTP request durations.",
        "# TYPE translators_api_http_request_duration_seconds_count counter",
        f"translators_api_http_request_duration_seconds_count {snapshot['http_request_duration_seconds_count']}",
        "# HELP translators_api_translations_total Successful translation operations.",
        "# TYPE translators_api_translations_total counter",
        f"translators_api_translations_total {snapshot['translations_total']}",
        "# HELP translators_api_translation_failures_total Translation operations that failed after routing to the service layer.",
        "# TYPE translators_api_translation_failures_total counter",
        f"translators_api_translation_failures_total {snapshot['translation_failures_total']}",
        "# HELP translators_api_translation_fallback_total Successful translations that required a fallback translator.",
        "# TYPE translators_api_translation_fallback_total counter",
        f"translators_api_translation_fallback_total {snapshot['translation_fallback_total']}",
        "# HELP translators_api_rate_limit_rejections_total Total rate-limit rejections.",
        "# TYPE translators_api_rate_limit_rejections_total counter",
        f"translators_api_rate_limit_rejections_total {snapshot['rate_limit_rejections_total']}",
        "# HELP translators_api_readiness_failures_total Total readiness check failures.",
        "# TYPE translators_api_readiness_failures_total counter",
        f"translators_api_readiness_failures_total {snapshot['readiness_failures_total']}",
        "# HELP translators_api_translations_by_translator_total Successful translations by upstream translator.",
        "# TYPE translators_api_translations_by_translator_total counter",
    ]
    lines.extend(
        f'translators_api_translations_by_translator_total{{translator="{_escape_metric_label(name)}"}} {count}'
        for name, count in sorted(by_translator.items())
    )
    return "\n".join(lines) + "\n"


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if value is None:
        value = f"req_{uuid.uuid4().hex}"
        request.state.request_id = value
    return value


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex}"
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        _metric_inc("http_requests_total")
        _metric_observe_duration(time.perf_counter() - started)

    if response.status_code >= 400:
        _metric_inc("http_request_failures_total")
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
    authorization = request.headers.get("authorization", "").encode("utf-8")
    token_fingerprint = hashlib.sha256(authorization).hexdigest()[:16]
    key = f"{client}:{token_fingerprint}"
    async with _rate_lock:
        bucket = _rate_buckets[key]
        cutoff = now - settings.rate_limit_window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            retry_after = max(1, int(bucket[0] + settings.rate_limit_window_seconds - now))
            _metric_inc("rate_limit_rejections_total")
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
    _metric_inc("translation_failures_total")
    rid = request_id(request)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error={"code": "translation_failed", "message": "all configured translators failed", "request_id": rid}
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
        _metric_inc("readiness_failures_total")
        raise HTTPException(status_code=503, detail=f"translator engine unavailable: {type(exc).__name__}") from exc
    if not names:
        _metric_inc("readiness_failures_total")
        raise HTTPException(status_code=503, detail="no translators available")
    return {"status": "ready", "translators": str(len(names))}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=_render_metrics(), media_type="text/plain; version=0.0.4")


@app.get("/v1/translators", dependencies=[Depends(protected)])
async def translators() -> dict[str, object]:
    names = available_translators()
    return {
        "translators": names,
        "default": settings.default_translator,
        "fallback": settings.fallback_translators,
        "state": service.provider_states(),
        "capabilities": service.provider_capabilities(),
    }


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
    _metric_translation(result.translator, result.fallback)
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

    semaphore = asyncio.Semaphore(settings.max_batch_concurrency)

    async def translate_one(text: str):
        async with semaphore:
            return await service.translate(text, payload.source, payload.target, payload.translator)

    tasks = [asyncio.create_task(translate_one(text)) for text in payload.texts]
    done, pending = await asyncio.wait(tasks, timeout=settings.batch_timeout)

    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    items: list[BatchItem] = []
    successful_results = []
    for index, (text, task) in enumerate(zip(payload.texts, tasks, strict=True)):
        if task in pending:
            items.append(
                BatchItem(
                    index=index,
                    text=text,
                    translation=None,
                    status="error",
                    error_code="batch_timeout",
                    error_message="translation did not complete before the batch deadline",
                )
            )
            continue

        try:
            result = task.result()
        except UnknownTranslatorError as exc:
            _metric_inc("translation_failures_total")
            items.append(
                BatchItem(
                    index=index,
                    text=text,
                    translation=None,
                    status="error",
                    error_code="unknown_translator",
                    error_message=str(exc),
                )
            )
        except TranslationServiceError:
            _metric_inc("translation_failures_total")
            items.append(
                BatchItem(
                    index=index,
                    text=text,
                    translation=None,
                    status="error",
                    error_code="translation_failed",
                    error_message="translation failed",
                )
            )
        except Exception:
            _metric_inc("translation_failures_total")
            items.append(
                BatchItem(
                    index=index,
                    text=text,
                    translation=None,
                    status="error",
                    error_code="internal_error",
                    error_message="unexpected translation failure",
                )
            )
        else:
            _metric_translation(result.translator, result.fallback)
            successful_results.append(result)
            items.append(
                BatchItem(
                    index=index,
                    text=text,
                    translation=result.translation,
                    status="success",
                )
            )

    translators_used = {result.translator for result in successful_results}
    translator_name = (
        next(iter(translators_used)) if len(translators_used) == 1 else "mixed" if translators_used else "none"
    )
    completed = len(successful_results)
    failed = len(items) - completed
    return BatchTranslateResponse(
        items=items,
        source=payload.source,
        target=payload.target,
        translator=translator_name,
        fallback=any(result.fallback for result in successful_results),
        completed=completed,
        failed=failed,
        partial_success=completed > 0 and failed > 0,
        deadline_exceeded=bool(pending),
        request_id=request_id(request),
    )


@app.post("/v1/translate/html", response_model=HtmlTranslateResponse, dependencies=[Depends(protected)])
async def translate_html(request: Request, payload: HtmlTranslateRequest) -> HtmlTranslateResponse:
    ensure_length(payload.html, settings.max_text_length, "html")
    result = await service.translate_html(payload.html, payload.source, payload.target, payload.translator)
    _metric_translation(result.translator, result.fallback)
    return HtmlTranslateResponse(
        html=payload.html,
        translation=result.translation,
        source=payload.source,
        target=payload.target,
        translator=result.translator,
        fallback=result.fallback,
        request_id=request_id(request),
    )
