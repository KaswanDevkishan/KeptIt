# AI Summaries API Contract

## Contract rules

All routes are under `/api/v1`, require the existing session cookie, and apply the existing trusted-origin protection to mutations. Requests and responses use strict schemas; unknown request fields are rejected. Valid foreign or absent Discovery UUIDs return the same `404 resource_not_found`, including on every other user's Discovery. Authentication establishes identity; owner-scoped queries authorize access.

The API never exposes provider credentials, raw prompts, raw provider responses, internal stack traces, input fingerprints, token/cost details, failure internals, or private operational metadata. Private responses use `Cache-Control: no-store`.

## Endpoints

| Method and path | Purpose | Success |
| --- | --- | --- |
| `POST /discoveries/{discovery_id}/summary` | Request first manual generation or idempotently observe existing work | `202` pending/processing; `200` existing terminal/current result |
| `POST /discoveries/{discovery_id}/summary/regenerate` | Explicitly generate from current approved inputs | `202` |
| `GET /discoveries/{discovery_id}/summary` | Read current representation | `200` |
| `DELETE /discoveries/{discovery_id}/summary` | Remove private generated output/state | `204` |

`GET` returns a representation even before a row exists (`status: unavailable`), so absence is not an error for an owned Discovery. DELETE is justified as a privacy control. After deletion, the Discovery remains and GET returns `unavailable`.

## Request schemas

Initial generation body (optional; omitted and `{}` are equivalent):

```json
{
  "use_personal_note": false
}
```

`use_personal_note` must be absent or `false` in the first release. `true` returns `422 note_context_not_supported` until the explicit opt-in feature, disclosure, fingerprinting, and provider policy are implemented. No body field may select provider, model, prompt, user, or Discovery inputs.

Regenerate body:

```json
{
  "confirm": true
}
```

`confirm` must be true. This makes the cost-generating replacement explicit. An `Idempotency-Key` header is required for both POST routes: 16–128 printable ASCII characters, scoped to authenticated user, route action, and Discovery, retained for a bounded period. Reusing a key with the same request returns the original outcome; reusing it with different input returns `409 idempotency_key_reused`.

DELETE has no body. It requires the normal UI confirmation but no special confirmation field.

## Summary representation

```json
{
  "status": "succeeded",
  "availability_reason": null,
  "summary": "A concise source-grounded description.",
  "key_points": ["One supported point."],
  "topics": ["subject phrase"],
  "entities": [
    {"name": "Example Organization", "type": "organization"}
  ],
  "language": "en",
  "confidence": 0.86,
  "insufficiency_reason": null,
  "generated_at": "2026-08-05T12:00:00Z",
  "last_attempted_at": "2026-08-05T12:00:00Z",
  "is_regenerating": false,
  "last_attempt_error": null,
  "can_generate": false,
  "can_retry": false,
  "can_regenerate": true,
  "retry_after_seconds": null
}
```

Public status is one of `unavailable`, `pending`, `processing`, `succeeded`, `failed`, `unsupported`, `insufficient_data`, or `stale`.

- Generated fields are non-null only for `succeeded` and `stale`. During regeneration, the public
  status remains `succeeded` or `stale` with `is_regenerating: true` while the internal work state is
  processing. `last_attempt_error` is null or the safe public error object from the latest failed
  regeneration; it never contains provider text.
- `insufficient_data` has a safe `insufficiency_reason` and empty generated collections.
- `failed` includes optional `error: {code, message, request_id}` using an allowlisted code, never a provider message.
- `unsupported` means platform/policy cannot supply approved metadata, not provider misconfiguration.
- `unavailable` means no request/current row; `can_generate` also reflects feature/configuration and sufficient preliminary input.
- For `unavailable`, `availability_reason` is the safe value `disabled`, `provider_unavailable`,
  `insufficient_data`, or null. It never identifies a vendor, key, or secret.
- Timestamps are RFC 3339 UTC. Confidence is null unless validated output exists.

Pending example:

```json
{
  "status": "pending",
  "summary": null,
  "key_points": [],
  "topics": [],
  "entities": [],
  "language": null,
  "confidence": null,
  "insufficiency_reason": null,
  "generated_at": null,
  "last_attempted_at": "2026-08-05T12:00:00Z",
  "is_regenerating": false,
  "last_attempt_error": null,
  "can_generate": false,
  "can_retry": false,
  "can_regenerate": false,
  "retry_after_seconds": null
}
```

## Behavior and status codes

### Generate

- `202 Accepted`: durable request recorded as pending/processing. Return the representation and `Location` pointing to GET. The HTTP request never waits for a real provider.
- `200 OK`: same approved-input fingerprint already succeeded, is insufficient, unsupported, stale/current according to policy, or the same idempotent request already completed. No new cost.
- `409 summary_generation_in_progress`: a different generation/regeneration is already active; include a safe current representation where consistent with the project error envelope.
- `422 insufficient_metadata`: the backend can determine before enqueue that no approved fields can support generation. It may instead persist/return `insufficient_data`; implementation must choose one consistently, with persisted `insufficient_data` recommended.
- `429 summary_limit_exceeded`: user daily limit or abuse limit; return `Retry-After` when known.
- `503 feature_disabled` or `503 provider_not_configured`: no work is created. These are deliberately distinct safe configuration codes but disclose no secret name/value.

### Retry

There is no separate retry endpoint. Calling POST `/summary` after a retryable `failed` state requests a retry using a new idempotency key. Retry is allowed only for allowlisted transient failures, within attempt and daily limits. Permanent unsupported/insufficient states require changed metadata or explicit regeneration after conditions change.

### Regenerate

- Requires an existing terminal result or stale result and explicit confirmation.
- Enforces a per-Discovery cooldown. A cooldown failure is `429 regeneration_cooldown` with `Retry-After`.
- Returns `202`; existing successful output remains readable until replacement succeeds.
- A failed regeneration does not destroy the prior successful output. It returns to `succeeded` or
  `stale`, sets a safe `last_attempt_error`, and remains operationally observable without exposing
  private or provider details.
- Concurrent requests are serialized through row locking/conditional state transition; only one provider call is charged.

### Read and delete

- GET returns `200` for every owned Discovery, including `unavailable`.
- DELETE returns `204` when a row existed and was deleted. It is idempotent for an owned Discovery with no summary and also returns `204`; a missing/foreign Discovery returns `404`.
- Deleting while processing marks/cancels the claim where practical and prevents a late worker from recreating output through a generation/lease token check.

## Error envelope

```json
{
  "error": {
    "code": "provider_temporarily_unavailable",
    "message": "AI summary generation is temporarily unavailable. Try again later.",
    "request_id": "req_opaque",
    "details": null
  }
}
```

Allowed public categories include `resource_not_found`, `validation_error`, `feature_disabled`, `provider_not_configured`, `summary_generation_in_progress`, `summary_limit_exceeded`, `regeneration_cooldown`, `provider_temporarily_unavailable`, and `summary_generation_failed`. Field details may identify invalid client fields but never echo untrusted content. Provider authentication errors map to the safe configuration response; timeouts, rate limits, invalid output, and upstream bodies are not passed through.

Common statuses:

| Status | Meaning |
| --- | --- |
| `200` | Read/current or idempotently completed request |
| `202` | Durable work accepted |
| `204` | Summary deleted/idempotently absent |
| `401` | No valid session |
| `404` | Discovery absent or not owned |
| `409` | Active generation or idempotency conflict |
| `415` | Unsupported body content type |
| `422` | Invalid path/body/header contract |
| `429` | Product/rate/cooldown limit; safe `Retry-After` |
| `503` | Feature disabled or provider not safely configured |

Provider runtime failures normally appear as persisted `failed` after a previously accepted `202`, not as the initiating response.

## Discovery response integration

List/card responses should include only a compact nested projection to avoid payload growth:

```json
{
  "ai_summary": {
    "status": "succeeded",
    "summary": "A concise source-grounded description.",
    "topics": ["subject phrase"],
    "generated_at": "2026-08-05T12:00:00Z"
  }
}
```

Detail responses may embed the full public representation, or the frontend may call GET; choose one pattern consistently after measuring query/payload cost. The recommended first release embeds the compact projection in Discovery lists and the full projection in a single-Discovery response, while retaining GET as the polling and stable feature contract. When the feature flag is off, use `ai_summary: null` (and hide controls); this does not affect any other Discovery field or route.

The property name is always `ai_summary`. It is visually and structurally separate from `custom_title`, `personal_note`, `save_reason`, fetched metadata, favourite/archive state, and Space memberships. Topics are generated subject phrases, never Tags.

## Rate limiting and origin policy

Apply per-user daily generation limits, per-Discovery cooldowns, concurrent-work limits, and IP-aware production abuse limits. Rate-limit checks occur before creating work and atomically reserve quota to prevent concurrent bypass. Provider `Retry-After` values are bounded and not blindly relayed. Mutation routes require a trusted `Origin` under the existing cookie/CSRF policy; API clients do not bypass ownership or idempotency.
