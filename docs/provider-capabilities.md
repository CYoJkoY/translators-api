# Provider capabilities

`GET /v1/translators` exposes gateway-local provider capability metadata in the `capabilities` object.

Each discovered translator has the following fields:

```json
{
  "text": "supported",
  "html": "unknown",
  "auto_source": "unknown"
}
```

Capability values are deliberately tri-state:

- `supported`: the gateway has explicit knowledge that the capability is available.
- `unsupported`: the gateway has explicit knowledge that the capability is unavailable.
- `unknown`: the gateway has not established support and therefore does not make a positive claim.

Provider discovery remains dynamic and comes from the installed `translators` package. The gateway does not maintain a large duplicated provider matrix.

Routing treats `unsupported` as ineligible for the corresponding operation. `unknown` remains eligible so the capability model does not silently reduce availability when the upstream library adds or changes providers.

For compatibility, the existing `translators`, `default`, `fallback`, and `state` fields remain unchanged.
