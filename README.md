<div align="center">

<img src="assets/readme/translators-api-hero.svg" alt="translators-api — an HTTP gateway for the Python Translators library" width="100%">

# translators-api

**Turn the Python [Translators](https://github.com/UlionTse/translators) library into a small, self-hosted HTTP service.**

<p>
  <a href="https://github.com/UlionTse/translators"><img src="https://img.shields.io/badge/backend-Translators-6F6B63?style=flat-square" alt="Powered by Translators"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-8D8172?style=flat-square" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/FastAPI-HTTP%20API-9A8F83?style=flat-square" alt="FastAPI"></a>
  <img src="https://img.shields.io/badge/license-GPL--3.0-6F6B63?style=flat-square" alt="GPL-3.0 license">
</p>

<p>
  <a href="#readme-overview">Overview</a> ·
  <a href="#readme-features">Features</a> ·
  <a href="#readme-quick-start">Quick Start</a> ·
  <a href="#readme-api">API</a> ·
  <a href="#readme-configuration">Configuration</a> ·
  <a href="#readme-deployment">Deployment</a> ·
  <a href="#readme-development">Development</a>
</p>

</div>

---

<a name="readme-overview"></a>
## <img src="assets/readme/icons/overview.svg" width="24" height="24" alt=""> Overview

`translators-api` is a thin HTTP layer around the Python **[Translators](https://github.com/UlionTse/translators)** package.

The goal is simple: move translation-provider integration to one server-side boundary and give clients a normal JSON/HTTP interface.

That makes the service useful for applications that cannot, or should not, embed the Python `translators` package directly—such as browser extensions, desktop applications, web frontends, automation scripts, and other services.

### The problem

Without a gateway, every client that needs translation has to understand a provider-specific library, runtime, error model, and availability profile.

```text
Client A ──► provider-specific integration
Client B ──► provider-specific integration
Client C ──► provider-specific integration

                 ↓

           duplicated logic
```

### The approach

`translators-api` centralizes that boundary:

```text
┌──────────────────────────────────────┐
│             Your clients             │
│  browser · desktop · web · scripts   │
└──────────────────┬───────────────────┘
                   │ HTTP + JSON
                   ▼
┌──────────────────────────────────────┐
│            translators-api           │
│                                      │
│  validation · authentication         │
│  rate limiting · request IDs         │
│  fallback · structured errors        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│              Translators             │
│       provider-specific adapters     │
└──────────────────────────────────────┘
```

### What this project is not

This project is **not** a new translation engine and does not implement translation providers itself. Provider access remains the responsibility of the upstream `Translators` project.

It is also intentionally not a large platform: there is no database, account system, dashboard, distributed job queue, or shared cache in the current implementation.

---

<a name="readme-features"></a>
## <img src="assets/readme/icons/features.svg" width="24" height="24" alt=""> Features

### One HTTP contract

Expose text translation, batch translation, HTML translation, translator discovery, and language discovery through a single FastAPI application.

### Automatic fallback

Requests using `auto`, `detect`, or `all` can walk the configured fallback list until one translator succeeds.

The response records whether a fallback backend was required, so clients can distinguish the normal path from a degraded-but-successful path.

### Batch translation

Batch requests run concurrently with a configurable concurrency limit while preserving the original input order through an explicit `index` field on every returned item.

### Built-in request controls

The service applies:

- optional bearer-token authentication;
- per-process request rate limiting;
- text and HTML size limits;
- batch item and aggregate-size limits;
- upstream translation timeouts;
- request IDs for tracing failures across client responses and server logs.

### Operational endpoints

`/health` provides a liveness signal. `/ready` verifies that the upstream translator pool can be discovered and that at least one translator is available.

### Multiple delivery paths

The repository supports:

```text
Python source / wheel
Docker image
Windows x64 portable bundle
```

Release automation also creates GitHub Releases and publishes the Docker image to GitHub Container Registry.

---

<a name="readme-quick-start"></a>
## <img src="assets/readme/icons/quick-start.svg" width="24" height="24" alt=""> Quick Start

### 1. Clone and install

Python 3.10 or newer is required.

```bash
git clone https://github.com/CYoJkoY/translators-api.git
cd translators-api

python -m venv .venv
```

Activate the environment:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e "."
```

For development and tests:

```bash
python -m pip install -e ".[test]"
```

### 2. Start the server

Using Uvicorn directly:

```bash
uvicorn translators_api.main:app --host 127.0.0.1 --port 8000
```

Or use the packaged CLI:

```bash
translators-api --host 127.0.0.1 --port 8000
```

### 3. Check the service

```bash
curl http://127.0.0.1:8000/health
```

Expected shape:

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

Then open the interactive API documentation:

- [`/docs`](http://127.0.0.1:8000/docs) — Swagger UI
- [`/redoc`](http://127.0.0.1:8000/redoc) — ReDoc
- [`/openapi.json`](http://127.0.0.1:8000/openapi.json) — OpenAPI document
- [`/health`](http://127.0.0.1:8000/health) — liveness
- [`/ready`](http://127.0.0.1:8000/ready) — readiness

### 4. Translate text

```bash
curl -X POST http://127.0.0.1:8000/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，世界",
    "source": "zh",
    "target": "en",
    "translator": "bing"
  }'
```

A successful response has this shape:

```json
{
  "text": "你好，世界",
  "translation": "Hello, world",
  "source": "zh",
  "target": "en",
  "translator": "bing",
  "fallback": false,
  "request_id": "req_..."
}
```

### 5. Run with authentication

Create a local environment file from the provided example:

```bash
cp .env.example .env
```

Then set a token:

```text
TRANSLATORS_API_KEY=change-me
```

The current application reads environment variables directly, so exporting the value is sufficient:

```bash
# Linux / macOS
export TRANSLATORS_API_KEY=change-me

# Windows PowerShell
$env:TRANSLATORS_API_KEY = "change-me"
```

Authenticated requests use the standard bearer-token header:

```bash
curl http://127.0.0.1:8000/v1/translators \
  -H "Authorization: Bearer change-me"
```

When `TRANSLATORS_API_KEY` is unset, authentication is disabled. Keep an internet-facing deployment authenticated.

---

<a name="readme-api"></a>
## <img src="assets/readme/icons/api.svg" width="24" height="24" alt=""> API

The application API lives under `/v1`. Operational endpoints remain outside that namespace.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Upstream translator readiness check |
| `GET` | `/v1/translators` | List available translator backends |
| `GET` | `/v1/languages` | List languages exposed by a translator |
| `POST` | `/v1/translate` | Translate one text value |
| `POST` | `/v1/translate/batch` | Translate multiple text values concurrently |
| `POST` | `/v1/translate/html` | Translate an HTML fragment |

### Text translation

```http
POST /v1/translate
Content-Type: application/json
```

```json
{
  "text": "Hello, world!",
  "source": "en",
  "target": "zh-CN",
  "translator": "bing"
}
```

Request fields:

| Field | Type | Default | Notes |
| :--- | :--- | :--- | :--- |
| `text` | string | required | Must not be blank. Maximum size is controlled by `MAX_TEXT_LENGTH`. |
| `source` | string | `auto` | Source language code. |
| `target` | string | `en` | Target language code. |
| `translator` | string  `null` | configured default | Set a concrete backend or use `auto`/`detect`/`all` for fallback mode. |

The server returns the selected backend in `translator` and includes `fallback: true` when an automatic request succeeds only after moving past its first candidate.

### Batch translation

```http
POST /v1/translate/batch
Content-Type: application/json
```

```json
{
  "texts": [
    "Hello",
    "How are you?",
    "Good morning"
  ],
  "source": "en",
  "target": "zh-CN",
  "translator": "auto"
}
```

Limits are controlled by `MAX_BATCH_ITEMS` and `MAX_BATCH_TOTAL_LENGTH`. Work is bounded by `MAX_BATCH_CONCURRENCY`.

The response preserves the request order:

```json
{
  "items": [
    { "index": 0, "text": "Hello", "translation": "你好" },
    { "index": 1, "text": "How are you?", "translation": "你好吗？" },
    { "index": 2, "text": "Good morning", "translation": "早上好" }
  ],
  "source": "en",
  "target": "zh-CN",
  "translator": "bing",
  "fallback": false,
  "request_id": "req_..."
}
```

When different items are translated by different fallback backends, `translator` may be reported as `mixed`.

### HTML translation

```http
POST /v1/translate/html
Content-Type: application/json
```

```json
{
  "html": "<p>Hello, <strong>world!</strong></p>",
  "source": "en",
  "target": "zh-CN",
  "translator": "bing"
}
```

The HTML request follows the same translator selection and fallback behavior as text translation. Its size is bounded by `MAX_TEXT_LENGTH`.

### Translator discovery

```bash
curl http://127.0.0.1:8000/v1/translators
```

Example shape:

```json
{
  "translators": ["alibaba", "baidu", "bing"],
  "default": "bing",
  "fallback": ["bing", "google", "deepl", "baidu"]
}
```

The actual translator list is inherited from the installed upstream `translators` package and can change when that dependency changes.

### Language discovery

```bash
curl "http://127.0.0.1:8000/v1/languages?translator=bing"
```

The endpoint returns the language identifiers exposed by the selected upstream backend.

### Authentication

Authentication applies to `/v1/*` endpoints when `TRANSLATORS_API_KEY` is configured.

```http
Authorization: Bearer YOUR_API_KEY
```

`/health` and `/ready` remain available without authentication so they can be used by local tooling, process supervisors, and container health checks.

### Request IDs

Every application response receives an `X-Request-ID` response header. Successful translation responses also include `request_id` in the JSON payload.

For a failed request, the same identifier is included in the structured error body, making it possible to correlate the client-visible failure with server-side logs.

### Error model

Errors use a stable envelope:

```json
{
  "error": {
    "code": "translation_failed",
    "message": "all translators failed",
    "request_id": "req_..."
  }
}
```

Current error categories include:

| HTTP status | Code | Typical cause |
| :--- | :--- | :--- |
| `400` | `unknown_translator` / `request_error` | Invalid translator or HTTP-level request error |
| `401` | `unauthorized` | Missing or invalid bearer token |
| `413` | `payload_too_large` | Text, HTML, or batch limit exceeded |
| `422` | `validation_error` | Request body failed Pydantic validation |
| `429` | `rate_limited` | Local rate limit exceeded |
| `502` | `translation_failed` / `request_error` | Upstream translation failure |

The exact message is intentionally treated as diagnostic information rather than a second machine-readable error code.

---

<a name="readme-configuration"></a>
## <img src="assets/readme/icons/configuration.svg" width="24" height="24" alt=""> Configuration

Configuration is environment-variable based. The repository includes [`.env.example`](.env.example) as a complete reference.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `TRANSLATORS_API_KEY` | empty | Enables bearer-token authentication for `/v1/*`. |
| `HOST` | `0.0.0.0` | Default bind address for the CLI. |
| `PORT` | `8000` | Default HTTP port for the CLI. |
| `LOG_LEVEL` | `info` | Uvicorn log level. |
| `MAX_TEXT_LENGTH` | `20000` | Maximum text or HTML size in characters. |
| `MAX_BATCH_ITEMS` | `50` | Maximum number of items in one batch request. |
| `MAX_BATCH_TOTAL_LENGTH` | `100000` | Maximum combined character count in a batch. |
| `MAX_BATCH_CONCURRENCY` | `5` | Maximum concurrent upstream translations in a batch. |
| `UPSTREAM_TIMEOUT` | `30` | Per-provider upstream timeout in seconds. |
| `RATE_LIMIT_REQUESTS` | `120` | Requests allowed per local rate-limit window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Duration of the local rate-limit window. |
| `DEFAULT_TRANSLATOR` | `bing` | Backend used when `translator` is omitted. |
| `FALLBACK_TRANSLATORS` | `bing,google,deepl,baidu` | Ordered fallback candidates for automatic selection. |

### Configuration precedence

The application does not use a multi-file configuration hierarchy. Values are loaded from environment variables and fall back to the defaults listed above.

### Rate limiting scope

The built-in rate limiter is **process-local**. Counters are held in application memory, so separate workers or separate service instances maintain separate limits.

For a multi-worker or horizontally scaled deployment, place a shared rate limiter in front of the application rather than treating the built-in limiter as a cluster-wide quota.

---

<a name="readme-architecture"></a>
## <img src="assets/readme/icons/architecture.svg" width="24" height="24" alt=""> Architecture

The project deliberately keeps the HTTP layer small:

```text
src/translators_api/
├── __init__.py   package version
├── cli.py        command-line entry point
├── config.py     environment-backed settings
├── models.py     request / response schemas
├── service.py    upstream Translators adapter + fallback
└── main.py       FastAPI routes, auth, limits, errors
```

### Request flow

```text
HTTP request
    │
    ▼
FastAPI validation
    │
    ▼
authentication + rate limit
    │
    ▼
request-size checks
    │
    ▼
TranslationService
    │
    ├── explicit translator ───► one backend
    │
    └── auto / detect / all ───► ordered fallback list
                                  │
                                  ├── success ──► response
                                  └── failure ──► next backend
                                                   │
                                                   └── all fail ──► 502
```

### Why provider calls run in worker threads

The upstream `translators` calls used by this gateway are synchronous. The service therefore executes those calls through `asyncio.to_thread(...)` so ordinary provider work does not block the FastAPI event loop.

Batch requests add a semaphore on top of that mechanism, which provides a simple server-side concurrency boundary.

### Responsibility boundary

```text
translators-api
  ├─ HTTP contract
  ├─ request validation
  ├─ authentication
  ├─ rate limiting
  ├─ fallback orchestration
  ├─ response shaping
  └─ operational endpoints

Translators
  ├─ provider integrations
  ├─ provider-specific behavior
  ├─ provider language maps
  └─ upstream network interaction
```

Keeping this boundary narrow reduces duplication and makes provider updates primarily an upstream dependency concern.

---

<a name="readme-deployment"></a>
## <img src="assets/readme/icons/deployment.svg" width="24" height="24" alt=""> Deployment

Choose the delivery form that matches the environment.

### Docker

Build locally:

```bash
docker build -t translators-api .
```

Run:

```bash
docker run --rm \
  -p 8000:8000 \
  -e TRANSLATORS_API_KEY=change-me \
  translators-api
```

The image starts the same FastAPI application used by the Python deployment and listens on port `8000` inside the container.

Release automation publishes versioned images to GitHub Container Registry. Stable tags also receive `latest`; development tags do not overwrite `latest`.

```bash
docker pull ghcr.io/cyojkoy/translators-api:latest
docker run --rm \
  -p 8000:8000 \
  -e TRANSLATORS_API_KEY=change-me \
  ghcr.io/cyojkoy/translators-api:latest
```

### Python

Install a built distribution from the release artifacts or from a local checkout:

```bash
python -m pip install translators-api
translators-api --host 0.0.0.0 --port 8000
```

For a local checkout, use:

```bash
python -m pip install .
```

### Windows portable bundle

Each release is also built as a Windows x64 `onedir` bundle with PyInstaller.

Example release asset:

```text
translators-api-v0.1.0-windows-x64.zip
```

Extract it and run:

```powershell
.\translators-api.exe --host 127.0.0.1 --port 8000
```

Inspect the executable:

```powershell
.\translators-api.exe --help
.\translators-api.exe --version
```

The portable bundle contains its runtime files and does not require a separate Python installation on the target machine.

### Production topology

A typical public deployment should keep the API behind a TLS-capable reverse proxy:

```text
Internet
   │
   ▼
TLS / reverse proxy
   │
   ├── authentication policy
   ├── shared rate limiting
   └── access logging
          │
          ▼
   translators-api
          │
          ▼
      Translators
```

Use `TRANSLATORS_API_KEY` for application authentication, keep secrets outside images and source control, and monitor `/health` and `/ready` from the surrounding deployment platform.

Do not assume the local in-process rate limiter is sufficient for multiple workers or hosts.

---

<a name="readme-release-model"></a>
## <img src="assets/readme/icons/release.svg" width="24" height="24" alt=""> Release model

Releases are driven by Git tags.

```text
vX.Y.Z          → stable GitHub Release
vX.Y.Z.devN     → GitHub prerelease
```

The release workflow validates that the tag version exactly matches the package version before building artifacts.

A release can contain:

```text
Python distributions
Windows x64 portable ZIP
SHA-256 checksum for the Windows ZIP
Docker image
GitHub Release notes
```

Stable Docker releases update `latest`. Development releases receive version-specific image tags only.

---

<a name="readme-development"></a>
## <img src="assets/readme/icons/development.svg" width="24" height="24" alt=""> Development

### Project setup

```bash
python -m pip install -e ".[test]"
```

### Tests

```bash
python -m pytest
```

### Compile check

```bash
python -m compileall -q src
```

### Local Windows bundle

Install the build extra:

```powershell
python -m pip install -e ".[build]"
```

Then build with PyInstaller:

```powershell
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name translators-api `
  --distpath build/windows `
  --workpath build/pyinstaller `
  --specpath build/pyinstaller `
  --paths src `
  src/translators_api/cli.py
```

### Continuous integration

Pull requests and pushes to `main` run the test matrix on Python 3.10, 3.11, 3.12, and 3.13.

The CI pipeline performs:

```text
install
  ↓
compile
  ↓
pytest
  ↓
Docker build
```

Tag-triggered release workflows additionally validate the package/tag version pair, build Python distributions, build and smoke-test the Windows bundle, build the Docker image, generate the Windows checksum, and publish the release artifacts.

### Design rule

The project intentionally avoids reimplementing provider-specific behavior in the API layer. New HTTP features should only be introduced when they provide a stable cross-provider contract; provider-specific details should remain in the upstream `Translators` integration whenever possible.

---

<a name="readme-compatibility"></a>
## <img src="assets/readme/icons/compatibility.svg" width="24" height="24" alt=""> Compatibility

| Component | Current requirement / target |
| :--- | :--- |
| Python service | Python `>=3.10` |
| FastAPI | `>=0.115,<1` |
| Uvicorn | `>=0.34,<1` |
| Pydantic | `>=2.10,<3` |
| Translators | `>=6.0,<7` |
| Windows bundle | Windows x64 |
| Client runtime | Any environment capable of HTTP requests |

The upstream `Translators` project has its own provider matrix, runtime requirements, and availability constraints. This gateway inherits that variability rather than eliminating it.

For the authoritative upstream provider list and upstream language support, use the [Translators repository](https://github.com/UlionTse/translators).

---

<a name="readme-security"></a>
## <img src="assets/readme/icons/security.svg" width="24" height="24" alt=""> Security and privacy

### Authentication

Bearer-token authentication is optional and enabled by setting `TRANSLATORS_API_KEY`.

Because authentication is disabled by default, a fresh local instance is convenient for development but should **not** be treated as a safe public endpoint.

### Rate limiting

A process-local rate limiter is enabled by default. It is a protection boundary, not a replacement for a shared gateway or edge quota.

### Sensitive content

The service sends submitted text or HTML to whichever upstream translator handles the request. Translation content can therefore leave the machine running `translators-api`.

Do not deploy the service for sensitive content until the selected upstream providers, network path, retention behavior, and organizational data-handling requirements have been reviewed.

The current application does not provide a persistent translation database or server-side result cache.

---

<a name="readme-limitations"></a>
## <img src="assets/readme/icons/limitations.svg" width="24" height="24" alt=""> Limitations

`translators-api` improves the integration boundary, but it cannot make upstream providers reliable or uniform.

| Area | Reality |
| :--- | :--- |
| Provider availability | An upstream provider can change, throttle, block, or remove its public access path. |
| Translation quality | Results depend on the selected upstream backend. |
| Network environment | Geography, connectivity, anti-bot controls, cookies, headers, and provider behavior can affect results. |
| Provider quotas | Upstream restrictions still apply. |
| Fallback | Fallback improves resilience but cannot succeed when every candidate fails. |
| Scaling | The built-in rate limiter and in-memory state are process-local. |
| API stability | The HTTP contract belongs to this project; the available translator set comes from the upstream package. |

This project should therefore be understood as a **gateway and orchestration layer**, not as an independent translation service provider.

---

<a name="readme-project-structure"></a>
## <img src="assets/readme/icons/project.svg" width="24" height="24" alt=""> Project structure

```text
translators-api/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── assets/
│   └── readme/
│       ├── icons/
│       ├── support.svg
│       └── translators-api-hero.svg
├── src/
│   └── translators_api/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── main.py
│       ├── models.py
│       └── service.py
├── tests/
├── .env.example
├── Dockerfile
├── LICENSE
├── pyproject.toml
└── README.md
```

The repository keeps application code under `src/`, tests under `tests/`, container packaging in `Dockerfile`, and release/CI behavior under `.github/workflows/`.

---

<a name="readme-roadmap"></a>
## <img src="assets/readme/icons/roadmap.svg" width="24" height="24" alt=""> Roadmap

The current codebase focuses on a stable first gateway layer rather than a large platform.

Potential future work may include improvements such as:

```text
shared rate limiting
shared caching
richer observability
more explicit provider capability metadata
```

These are not part of the current production contract unless implemented and documented elsewhere in the repository.

---

<a name="readme-upstream"></a>
## <img src="assets/readme/icons/upstream.svg" width="24" height="24" alt=""> Upstream

This project is built around **[UlionTse/translators](https://github.com/UlionTse/translators)**.

The upstream project provides the actual translation-provider integrations and exposes APIs such as `translate_text`, `translate_html`, translator discovery, and language discovery. `translators-api` turns the relevant subset of that functionality into an HTTP service.

Refer to the upstream project for provider-specific behavior, provider support, and upstream changes:

- [Translators repository](https://github.com/UlionTse/translators)
- [Translators README](https://github.com/UlionTse/translators#readme)

---

<a name="readme-support"></a>
## <img src="assets/readme/icons/support.svg" width="24" height="24" alt=""> Support

Support helps sustain maintenance, compatibility work, testing, documentation, and future development of `translators-api`.

<a href="https://cyojkoy.github.io/Payment/">
  <img src="assets/readme/support.svg" alt="Support translators-api development" width="100%">
</a>

Canonical support page: **https://cyojkoy.github.io/Payment/**

---

<a name="readme-contributing"></a>
## <img src="assets/readme/icons/contributing.svg" width="24" height="24" alt=""> Contributing

Contributions should improve the HTTP contract, reliability, testing, documentation, deployment experience, or maintainability without unnecessarily duplicating upstream provider behavior.

Before adding a provider-specific API surface, check whether the capability already belongs in the upstream `Translators` package. Keep this gateway's contract small and predictable.

For bugs and feature requests, use the repository's [GitHub Issues](https://github.com/CYoJkoY/translators-api/issues).

---

<a name="readme-license"></a>
## <img src="assets/readme/icons/license.svg" width="24" height="24" alt=""> License

`translators-api` is licensed under the **GNU General Public License v3.0 only**.

See [`LICENSE`](LICENSE) for the complete license text.

This project depends on and wraps the separate **Translators** project. Review the upstream project's license and notices when redistributing a combined deployment.

---

<div align="center">

**translators-api** · one HTTP boundary for many translation backends

[Repository](https://github.com/CYoJkoY/translators-api) · [Issues](https://github.com/CYoJkoY/translators-api/issues) · [Releases](https://github.com/CYoJkoY/translators-api/releases)

</div>
