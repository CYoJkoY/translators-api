<div align="center">

<img src="assets/readme/translators-api-hero.svg" alt="translators-api — one HTTP boundary for multiple translation backends" width="100%">

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
  <a href="#readme-architecture">Architecture</a> ·
  <a href="#readme-limitations">Limitations</a> ·
  <a href="#readme-support">Support</a>
</p>

</div>

---

<a name="readme-overview"></a>
## <img src="assets/readme/icons/overview.svg" width="24" height="24" alt=""> Overview

`translators-api` is intended to turn the Python [Translators](https://github.com/UlionTse/translators) library into a language-agnostic HTTP service.

The upstream project already provides a common Python interface for many translation services, including text and HTML translation. `translators-api` adds a stable service boundary so browser extensions, desktop applications, web applications, scripts, and other runtimes can consume the same translation backend over HTTP. fileciteturn2file0

### Current status

This repository is currently in **early development**. The README defines the intended service contract and architecture; the production API implementation is being developed incrementally.

That distinction is intentional: documented endpoints and features below describe the target service design, not functionality that is already guaranteed to be available in the current repository.

### What it solves

```text
Without a gateway

Application ──► provider-specific integration
              ├─ Google
              ├─ Bing
              ├─ DeepL
              └─ other services

With translators-api

Application ──► HTTP API ──► Translators ──► providers
                         one stable boundary
```

---

<a name="readme-quick-start"></a>
## <img src="assets/readme/icons/quick-start.svg" width="24" height="24" alt=""> Quick Start

The service implementation is not yet published, so there is currently no production startup command to copy and run.

The planned local setup uses Python and the upstream `translators` package:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install the upstream engine during development:

```bash
python -m pip install --upgrade pip
python -m pip install translators
```

The final server entry point, dependency manifest, container image, and deployment command will be added together with the first API implementation.

### Upstream Python API

For direct Python usage today, the upstream package exposes a common interface such as:

```python
import translators as ts

result = ts.translate_text(
    "Hello, world!",
    translator="bing",
    from_language="en",
    to_language="zh-CN",
)

print(result)
```

The upstream package also supports HTML translation and asynchronous invocation. Consult the upstream documentation for provider-specific parameters and the current supported-service list. fileciteturn2file0

---

<a name="readme-api"></a>
## <img src="assets/readme/icons/api.svg" width="24" height="24" alt=""> API

The public API is designed around versioned endpoints under `/v1`.

### Translate text

`POST /v1/translate`

```json
{
  "text": "你好，世界",
  "source": "zh",
  "target": "en",
  "translator": "google"
}
```

```json
{
  "text": "你好，世界",
  "translation": "Hello, world",
  "source": "zh",
  "target": "en",
  "translator": "google"
}
```

### Translate multiple texts

`POST /v1/translate/batch`

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

### Translate HTML

`POST /v1/translate/html`

```json
{
  "html": "<p>Hello, world!</p>",
  "source": "en",
  "target": "zh-CN",
  "translator": "bing"
}
```

### Inspect translators

`GET /v1/translators`

Returns the translator backends exposed by the running service.

### Inspect languages

`GET /v1/languages`

Returns language identifiers available through the configured backends.

### Health check

`GET /health`

A minimal endpoint for reverse proxies, container orchestration, and service monitoring.

```json
{
  "status": "ok"
}
```

### Authentication

Network-accessible deployments should require an API key or equivalent authentication mechanism.

```http
Authorization: Bearer YOUR_API_KEY
```

Authentication, quotas, and rate limits belong at the API boundary so the service can protect both its own resources and upstream providers.

### Error model

The final implementation should expose predictable HTTP status codes and a machine-readable error object rather than leaking raw provider exceptions.

Example target shape:

```json
{
  "error": {
    "code": "translation_failed",
    "message": "All configured translators failed.",
    "request_id": "req_01J..."
  }
}
```

---

<a name="readme-architecture"></a>
## <img src="assets/readme/icons/architecture.svg" width="24" height="24" alt=""> Architecture

The service is deliberately thin. Translation-provider behavior stays in `Translators`; API concerns stay in `translators-api`.

```text
┌───────────────────────┐
│ Client                │
│ browser / app / tool  │
└───────────┬───────────┘
            │ HTTPS + JSON
            ▼
┌─────────────────────────────┐
│ translators-api             │
│                             │
│ auth · validation            │
│ routing · rate limits       │
│ fallback · caching          │
│ unified errors / responses  │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Translators                 │
│ common Python translation   │
│ interface                   │
└────────────┬────────────────┘
             │
     ┌───────┼────────┬─────────┐
     ▼       ▼        ▼         ▼
  Google    Bing     DeepL    other backends
```

### Fallback routing

`translator: "auto"` is intended to select a configured backend and move through a controlled fallback policy when a provider fails.

```text
request
  │
  ▼
preferred backend
  │
  ├── success ─────────► response
  │
  └── failure
        │
        ▼
next backend
  │
  ├── success ─────────► response
  │
  └── failure ─────────► continue / final error
```

Fallback order should be configurable. A single universal provider ranking is not appropriate for every language pair, network environment, or deployment.

### Caching

An optional cache can reduce duplicate upstream requests. Cache keys should include all translation-affecting inputs, such as:

```text
translator
source language
target language
request content
relevant provider options
```

Sensitive translation content should not be cached by default unless the deployment explicitly accepts that data-handling model.

### Production topology

```text
Internet
   │
   ▼
Reverse proxy / TLS
   │
   ├── access policy
   └── rate limiting
          │
          ▼
   translators-api
          │
          ▼
      Translators
```

A container-first deployment model is planned once the initial service implementation is complete.

---

<a name="readme-compatibility"></a>
## <img src="assets/readme/icons/compatibility.svg" width="24" height="24" alt=""> Compatibility

The upstream `translators` package currently declares Python **3.8+** support and exposes synchronous and asynchronous translation interfaces. Its package metadata also lists multiple provider-specific transport and request options. fileciteturn3file0L2-L2

The gateway itself is intended to support clients that can issue ordinary HTTP requests; clients do not need to be written in Python.

Provider availability is expected to vary over time. The upstream project currently lists a broad set of services, but individual services may change behavior or availability independently. fileciteturn2file0

---

<a name="readme-limitations"></a>
## <img src="assets/readme/icons/limitations.svg" width="24" height="24" alt=""> Limitations

`translators-api` is an integration and self-hosting layer. It is **not** the owner or operator of the translation services behind `Translators`.

This creates several important boundaries:

| Boundary | Consequence |
| :--- | :--- |
| Third-party providers | An upstream service can change, restrict, or disable access independently. |
| Network conditions | Availability can depend on geography, anti-bot systems, cookies, headers, or provider-side controls. |
| Translation quality | Results depend on the selected upstream provider. |
| Rate limits | Provider limits still apply even when requests enter through a single gateway. |
| Public hosting | An open instance can attract abuse and unexpectedly high upstream traffic. |
| Legal / policy | Deployments must respect the applicable upstream provider terms and local requirements. |

A self-hosted instance should therefore be treated as a controlled integration service, not as a guarantee of permanent access to every translator listed by the upstream project.

### Security baseline

Production deployments should:

- terminate traffic over HTTPS;
- require authentication for non-local access;
- enforce request and response size limits;
- set explicit upstream timeouts;
- apply per-client rate limits;
- avoid logging full translation content unless necessary;
- keep secrets outside source control;
- restrict diagnostic or administrative endpoints.

---

<a name="readme-roadmap"></a>
## <img src="assets/readme/icons/roadmap.svg" width="24" height="24" alt=""> Roadmap

- [ ] Initial HTTP server
- [ ] OpenAPI specification
- [ ] Text translation endpoint
- [ ] Batch translation endpoint
- [ ] HTML translation endpoint
- [ ] Translator discovery
- [ ] API-key authentication
- [ ] Rate limiting
- [ ] Configurable fallback policies
- [ ] Optional caching
- [ ] Health and readiness endpoints
- [ ] Docker deployment
- [ ] Integration tests
- [ ] Production deployment guide

The roadmap describes intended development direction and should not be interpreted as a promise of a particular release date.

---

<a name="readme-support"></a>
## <img src="assets/readme/icons/support.svg" width="24" height="24" alt=""> Support

Support helps sustain compatibility work, API implementation, documentation, testing, and maintenance.

<a href="https://cyojkoy.github.io/Payment/">
  <img src="assets/readme/support.svg" alt="Support translators-api" width="100%">
</a>

Canonical support page: **https://cyojkoy.github.io/Payment/**

---

<a name="readme-upstream"></a>
## <img src="assets/readme/icons/upstream.svg" width="24" height="24" alt=""> Upstream

This project is built around **[Translators](https://github.com/UlionTse/translators)** by [UlionTse](https://github.com/UlionTse).

Useful references:

- [GitHub repository](https://github.com/UlionTse/translators)
- [PyPI package](https://pypi.org/project/translators/)
- [Upstream README](https://github.com/UlionTse/translators#readme)

The upstream repository currently describes `Translators` as a Python library providing multiple free translation services through a common interface and ships a `fanyi` command-line entry point. fileciteturn2file0L1-L2

---

<a name="readme-license"></a>
## <img src="assets/readme/icons/license.svg" width="24" height="24" alt=""> License

This project is licensed under the **GNU General Public License v3.0**.

See [`LICENSE`](LICENSE) for the full text.

The upstream `Translators` project is also licensed under GPL-3.0, so downstream distribution and modifications should be handled with the applicable GPL obligations in mind. fileciteturn1file0L2-L2

<div align="center">

**translators-api** · one HTTP boundary for many translation backends

</div>
