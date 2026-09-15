# translators-api

> A self-hosted translation API gateway powered by [Translators](https://github.com/UlionTse/translators).

[![Translators](https://img.shields.io/badge/powered%20by-Translators-blue)](https://github.com/UlionTse/translators)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

`translators-api` is designed to turn the Python [Translators](https://github.com/UlionTse/translators) library into a practical, unified HTTP service.

Instead of integrating different translation providers individually, clients can send one consistent API request and let the gateway handle translator selection, validation, failures, and service-specific details.

## Overview

```text
Client
  │
  │ HTTP / JSON
  ▼
┌──────────────────────────────┐
│       translators-api        │
├──────────────────────────────┤
│ Authentication               │
│ Request validation            │
│ Rate limiting                │
│ Translation routing           │
│ Fallback handling             │
│ Caching                      │
│ Unified responses             │
└──────────────┬───────────────┘
               │
               ▼
        ┌───────────────┐
        │  Translators  │
        └───────┬───────┘
                │
        ┌───────┼────────┬─────────┐
        ▼       ▼        ▼         ▼
      Google   Bing    DeepL    Other services
```

The project is intentionally separated from the upstream library. `translators-api` provides the HTTP/API layer while `Translators` remains responsible for communication with supported translation services.

## Features

The API is designed around the following capabilities:

- Unified HTTP API for multiple translation services
- Text translation
- Batch translation
- HTML translation
- Automatic translator fallback
- Explicit translator selection
- API-key authentication
- Rate limiting
- Optional response caching
- Request timeouts and controlled failure handling
- OpenAPI-compatible API documentation
- Self-hosted deployment

> **Project status:** the repository is currently being established. The API contract and service architecture are documented here first; implementation will be added incrementally.

## Why a Gateway?

The upstream `Translators` project already exposes a common Python interface such as `translate_text()` and `translate_html()`. This project adds the missing service boundary for applications that need to consume translation through HTTP rather than importing a Python package directly.

This makes the same translation backend usable from:

- Browser extensions
- Web applications
- Desktop applications
- CLI tools
- Mobile clients
- Server-side applications
- Other languages and runtimes

## API Design

The initial API is designed around versioned endpoints under `/v1`.

### `POST /v1/translate`

Translate a single text value.

```json
{
  "text": "你好，世界",
  "source": "zh",
  "target": "en",
  "translator": "google"
}
```

Example response:

```json
{
  "text": "你好，世界",
  "translation": "Hello, world",
  "source": "zh",
  "target": "en",
  "translator": "google"
}
```

### `POST /v1/translate/batch`

Translate multiple text values in one request.

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

### `POST /v1/translate/html`

Translate HTML while preserving the document structure.

```json
{
  "html": "<p>Hello, world!</p>",
  "source": "en",
  "target": "zh-CN",
  "translator": "bing"
}
```

### `GET /v1/translators`

Return available translator backends and their current availability.

### `GET /v1/languages`

Return the language identifiers exposed by the configured translator backends.

### `GET /health`

A lightweight health endpoint for deployment checks and reverse proxies.

```json
{
  "status": "ok"
}
```

## Automatic Fallback

A client can request `translator: "auto"` and allow the gateway to select a backend.

A typical fallback chain looks like:

```text
Primary translator
       │
       ├── success ──────► response
       │
       └── failure
              │
              ▼
        Next translator
              │
              ├── success ─► response
              │
              └── failure ─► continue / return error
```

Fallback policy should be configurable rather than hard-coded to one provider order. This allows deployments to prefer specific providers for particular language pairs or environments.

## Authentication

Deployments intended for network access should protect the API with an API key or another authentication mechanism.

Example:

```http
Authorization: Bearer YOUR_API_KEY
```

Do not expose an unrestricted public instance unless you have appropriate abuse protection, quotas, logging, and upstream-service policies in place.

## Rate Limiting

Rate limiting is intended to operate at the API boundary so one client cannot exhaust the translation backends or server resources.

A deployment can apply limits per:

- API key
- Client IP
- Endpoint
- Request size

Exact defaults will be defined by the implementation and should remain configurable.

## Caching

Optional caching can reduce repeated translation requests and lower pressure on upstream providers.

A safe cache key should include at least:

```text
translator + source + target + request content + relevant options
```

Do not cache private or sensitive text unless the deployment explicitly accepts that data-handling model.

## Deployment

The intended deployment model is a small self-hosted service behind a reverse proxy or container platform.

A typical production topology is:

```text
Internet
   │
   ▼
Reverse Proxy
   │
   ├── TLS
   ├── Authentication / access policy
   └── Rate limiting
          │
          ▼
   translators-api
          │
          ▼
      Translators
```

Container-based deployment will be supported as the implementation matures.

## Development

The service is expected to use Python and the upstream `translators` package as its translation engine.

The upstream project currently supports Python 3.8 and newer and exposes both synchronous and asynchronous translation interfaces. See the upstream documentation for translator-specific parameters and supported services.

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -U pip
```

The implementation will define the final development dependencies and startup command.

## Upstream Project

This project is built around:

**Translators** by [UlionTse](https://github.com/UlionTse/translators)

- Repository: <https://github.com/UlionTse/translators>
- PyPI: <https://pypi.org/project/translators/>
- License: GPL-3.0

`Translators` supports a large collection of translation services through a common Python API. Its supported providers and availability can change over time, so refer to the upstream project for the current list.

## Important Limitations

`translators-api` is a gateway around third-party translation services; it does not operate those services itself.

As a result:

1. A provider can change, restrict, or disable an endpoint without notice.
2. Availability can depend on network location, anti-bot systems, cookies, headers, or provider-side limits.
3. Translation quality depends on the selected upstream service.
4. A public API deployment must consider abuse, traffic costs, privacy, and each upstream provider's terms of service.

The gateway should therefore be treated as a self-hosting and integration layer, not as a guarantee of permanent access to every listed translator.

## Security Considerations

For production deployments:

- Use HTTPS.
- Require authentication for non-local access.
- Set request and response size limits.
- Configure strict upstream timeouts.
- Apply per-client rate limits.
- Avoid logging full translation content unless required.
- Store API credentials outside source control.
- Restrict administrative and diagnostic endpoints.
- Keep the upstream `translators` dependency updated and review upstream changes before upgrading.

## API Compatibility

The API is intended to provide a stable service-level contract even when the underlying translation provider changes.

Provider-specific options should be exposed only when they can be represented without making the public API tightly coupled to one backend.

## Roadmap

- [ ] Initial HTTP API implementation
- [ ] OpenAPI schema and interactive documentation
- [ ] Text translation
- [ ] Batch translation
- [ ] HTML translation
- [ ] Translator discovery
- [ ] Authentication
- [ ] Rate limiting
- [ ] Configurable fallback policies
- [ ] Optional caching
- [ ] Health and readiness checks
- [ ] Docker deployment
- [ ] Integration tests
- [ ] Production deployment documentation

## License

This project is licensed under the **GNU General Public License v3.0**.

See [LICENSE](LICENSE) for the full license text.

The project depends on and is designed around the GPL-3.0-licensed [Translators](https://github.com/UlionTse/translators) project.
