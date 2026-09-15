<div align="center">

<img src="assets/readme/translators-api-hero.svg" alt="translators-api — one HTTP boundary for many translation backends" width="100%">

# translators-api

**A self-hosted HTTP gateway for the Python [Translators](https://github.com/UlionTse/translators) library.**

<p>
  <a href="https://github.com/UlionTse/translators"><img src="https://img.shields.io/badge/engine-Translators-202020?style=flat-square" alt="Powered by Translators"></a>
  <img src="https://img.shields.io/badge/status-early%20development-8a7f6b?style=flat-square" alt="Early development">
  <img src="https://img.shields.io/badge/license-GPL--3.0-202020?style=flat-square" alt="GPL-3.0 license">
</p>

<p>
  <a href="#readme-overview">Overview</a> ·
  <a href="#readme-quick-start">Quick Start</a> ·
  <a href="#readme-api">API</a> ·
  <a href="#readme-configuration">Configuration</a> ·
  <a href="#readme-deployment">Deployment</a> ·
  <a href="#readme-limitations">Limitations</a> ·
  <a href="#readme-support">Support</a>
</p>

</div>

---

<a name="readme-overview"></a>
## <img src="assets/readme/icons/overview.svg" width="24" height="24" alt=""> Overview

`translators-api` exposes the upstream [Translators](https://github.com/UlionTse/translators) Python library through a small, versioned HTTP API.

The gateway gives browser extensions, desktop applications, web applications, scripts, and other runtimes a single integration point instead of requiring provider-specific translation code in every client.

```text
Client
  │
  │ HTTP + JSON
  ▼
┌───────────────────────────┐
│      translators-api      │
│ auth · validation         │
│ routing · limits          │
│ fallback · errors         │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│      Translators          │
│ common Python interface   │
└─────────────┬─────────────┘
              │
       ┌──────┼──────┬──────┐
       ▼      ▼      ▼      ▼
    Google   Bing   DeepL   ...
```

### Current status

The project now contains a runnable FastAPI service, test suite, configuration model, Docker image definition, and GitHub Actions CI. Advanced production features such as distributed rate limiting and shared caching remain future work.

### Design goals

- **One HTTP contract** across many upstream translators.
- **Thin integration layer** that does not duplicate provider implementations.
- **Explicit failure boundaries** so provider errors do not leak raw exceptions to clients.
- **Self-hosted operation** with configuration supplied through environment variables.
- **Incremental hardening** through tests, CI, and deployment checks.

---

<a name="readme-quick-start"></a>
## <img src="assets/readme/icons/quick-start.svg" width="24" height="24" alt=""> Quick Start

### Run locally

```bash
git clone https://github.com/CYoJkoY/translators-api.git
cd translators-api

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Start the server:

```bash
uvicorn translators_api.main:app --host 0.0.0.0 --port 8000
```

Then open:

- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/redoc` — ReDoc
- `http://localhost:8000/health` — health check
- `http://localhost:8000/ready` — readiness check

### Translate text

```bash
curl -X POST http://localhost:8000/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，世界",
    "source": "zh",
    "target": "en",
    "translator": "bing"
  }'
```

Example response:

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

---

<a name="readme-api"></a>
## <img src="assets/readme/icons/api.svg" width="24" height="24" alt=""> API

All application endpoints are versioned under `/v1`.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/v1/translate` | Translate one text value |
| `POST` | `/v1/translate/batch` | Translate multiple text values concurrently |
| `POST` | `/v1/translate/html` | Translate HTML through the upstream HTML API |
| `GET` | `/v1/translators` | List available translator backends |
| `GET` | `/v1/languages?translator=bing` | List languages exposed by one backend |
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness check |

### Text

```json
{
  "text": "Hello, world!",
  "source": "en",
  "target": "zh-CN",
  "translator": "auto"
}
```

`translator` is optional. `auto` uses the configured fallback list.

### Batch

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

Each item is returned with its original index so clients can safely reconstruct input order.

### HTML

```json
{
  "html": "<p>Hello, <strong>world!</strong></p>",
  "source": "en",
  "target": "zh-CN",
  "translator": "bing"
}
```

### Translator discovery

```bash
curl http://localhost:8000/v1/translators
```

```json
{
  "translators": ["alibaba", "baidu", "bing"],
  "default": "bing",
  "fallback": ["bing", "google", "deepl", "baidu"]
}
```

The exact list depends on the installed upstream `translators` version and its current implementation.

### Structured errors

API errors use a consistent envelope:

```json
{
  "error": {
    "code": "translation_failed",
    "message": "all translators failed",
    "request_id": "req_..."
  }
}
```

Every response generated by the application carries `X-Request-ID` so failed requests can be correlated with server logs.

### Authentication

Set `TRANSLATORS_API_KEY` to enable bearer-token authentication on `/v1/*` endpoints:

```bash
curl http://localhost:8000/v1/translators \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Authentication is disabled when the variable is unset, which is convenient for local development. Do not expose an unauthenticated public instance.

---

<a name="readme-configuration"></a>
## <img src="assets/readme/icons/configuration.svg" width="24" height="24" alt=""> Configuration

Copy `.env.example` as a reference. The application reads configuration from environment variables.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TRANSLATORS_API_KEY` | empty | Bearer token for API authentication |
| `HOST` | `0.0.0.0` | Bind address used by the deployment command |
| `PORT` | `8000` | HTTP port |
| `LOG_LEVEL` | `info` | Application log level |
| `MAX_TEXT_LENGTH` | `20000` | Maximum text/HTML size in characters |
| `MAX_BATCH_ITEMS` | `50` | Maximum batch item count |
| `MAX_BATCH_TOTAL_LENGTH` | `100000` | Maximum combined batch size |
| `RATE_LIMIT_REQUESTS` | `120` | Requests allowed per client window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window |
| `DEFAULT_TRANSLATOR` | `bing` | Translator used when omitted |
| `FALLBACK_TRANSLATORS` | `bing,google,deepl,baidu` | Ordered fallback candidates |

The built-in rate limiter is intentionally process-local. Multiple application workers therefore have independent counters. A shared limiter should be added before deploying a multi-worker or horizontally scaled public service.

---

<a name="readme-architecture"></a>
## <img src="assets/readme/icons/architecture.svg" width="24" height="24" alt=""> Architecture

The code is divided into small boundaries:

```text
src/translators_api/
├── config.py      environment-backed settings
├── models.py      request / response schemas
├── service.py     upstream Translators adapter + fallback
└── main.py        FastAPI routes, auth, limits, errors
```

The API layer does not reimplement provider logic. It delegates translation to the upstream package and runs its synchronous provider calls through worker threads so the ASGI event loop is not blocked by ordinary provider requests.

### Fallback

```text
translator = explicit
       │
       └────────────► one configured backend

translator = auto
       │
       ▼
configured fallback list
       │
       ├─ success ───────► response
       │
       └─ failure
             │
             ▼
        next backend
             │
             └───────────► final 502 if all fail
```

A successful fallback response reports `fallback: true` when a backend after the first candidate was required.

---

<a name="readme-deployment"></a>
## <img src="assets/readme/icons/deployment.svg" width="24" height="24" alt=""> Deployment

### Docker

Build:

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

### Production topology

```text
Internet
   │
   ▼
Reverse proxy / TLS
   │
   ├── access policy
   └── request limits
          │
          ▼
   translators-api
          │
          ▼
      Translators
```

For production use, terminate TLS at a reverse proxy, keep secrets outside the image, use health/readiness checks, and use an external rate limiter when running multiple workers or instances.

---

<a name="readme-development"></a>
## <img src="assets/readme/icons/development.svg" width="24" height="24" alt=""> Development

Run the test suite:

```bash
python -m pytest
```

Compile-check the source:

```bash
python -m compileall -q src
```

GitHub Actions runs the test suite on Python 3.10–3.13 and builds the Docker image after the test matrix succeeds.

The repository intentionally keeps the provider adapter small. Provider-specific parameters should only be added to the HTTP contract when they provide stable cross-provider value; otherwise they belong in the upstream `Translators` layer.

---

<a name="readme-compatibility"></a>
## <img src="assets/readme/icons/compatibility.svg" width="24" height="24" alt=""> Compatibility

The service requires Python 3.10 or newer. The upstream [Translators](https://github.com/UlionTse/translators) package currently declares Python 3.8+ support and exposes synchronous and asynchronous translation entry points.

The gateway can be consumed by any client capable of HTTP requests. No Python runtime is required on the client side.

The available translator set is inherited from the installed upstream package and can change independently of this project.

---

<a name="readme-limitations"></a>
## <img src="assets/readme/icons/limitations.svg" width="24" height="24" alt=""> Limitations

`translators-api` does not operate the underlying translation services. It wraps the access mechanisms implemented by the upstream `Translators` project.

Consequently:

| Area | Limitation |
| :--- | :--- |
| Provider availability | A provider may change, restrict, or disable access. |
| Network conditions | Geography, anti-bot controls, cookies, headers, and provider limits can affect availability. |
| Quality | Translation quality depends on the selected backend. |
| Provider limits | Upstream rate limits still apply. |
| Public hosting | Open instances can be abused and create unexpected upstream traffic. |
| Privacy | Do not log or cache sensitive translation content without an appropriate data-handling policy. |

Automatic fallback improves resilience but cannot guarantee successful translation when every configured provider is unavailable.

---

<a name="readme-support"></a>
## <img src="assets/readme/icons/support.svg" width="24" height="24" alt=""> Support

Support helps sustain compatibility work, implementation, testing, documentation, and maintenance.

<a href="https://cyojkoy.github.io/Payment/">
  <img src="assets/readme/support.svg" alt="Support translators-api" width="100%">
</a>

Canonical support page: **https://cyojkoy.github.io/Payment/**

---

<a name="readme-upstream"></a>
## <img src="assets/readme/icons/upstream.svg" width="24" height="24" alt=""> Upstream

This project builds on **[Translators](https://github.com/UlionTse/translators)** by [UlionTse](https://github.com/UlionTse).

- [GitHub repository](https://github.com/UlionTse/translators)
- [PyPI package](https://pypi.org/project/translators/)
- [Upstream documentation](https://github.com/UlionTse/translators#readme)

The upstream library provides the actual provider-specific translation implementations; `translators-api` supplies the HTTP service boundary around them.

---

<a name="readme-license"></a>
## <img src="assets/readme/icons/license.svg" width="24" height="24" alt=""> License

This project is licensed under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for the full license text.

The upstream `Translators` project is also GPL-3.0 licensed. Review the applicable license obligations when redistributing or modifying this project.

<div align="center">

**translators-api** · one HTTP boundary for many translation backends

</div>
