# Semantic Search API Contract

## Contract rules

All routes are under `/api/v1`, require the existing opaque session cookie, return
`Cache-Control: no-store`, and apply trusted-origin protection to POST requests. Authentication
establishes identity; authorization scopes Discoveries, embeddings, joins, counts, ranking, and
pagination to the current User in SQL. A valid absent UUID and a foreign UUID return identical
`404 resource_not_found`. Strict schemas reject unknown fields.

The API never exposes raw vectors, input fingerprints, provider keys/bodies, private document text,
query vectors, internal leases, database details, or another User's indexing state.

## Endpoints

| Method and path | Purpose | Success |
| --- | --- | --- |
| `POST /search/semantic` | Semantic or hybrid owner-scoped search | `200` |
| `POST /discoveries/{discovery_id}/embedding` | Idempotently request initial/current indexing | `202` or `200` |
| `POST /discoveries/{discovery_id}/embedding/retry` | Retry eligible failed/stale indexing | `202` or `200` |
| `GET /discoveries/{discovery_id}/embedding/status` | Read safe embedding state | `200` |
| `POST /embeddings/backfill` | Optional bounded owner-only backfill | `202` or `200` |

No admin/global backfill route is part of the public API. The owner route is enabled only when the
backfill flag is on. It can never target another account.

## Semantic search

`POST /api/v1/search/semantic`

```json
{
  "query": "that abandoned town video from Japan",
  "mode": "hybrid",
  "filters": {
    "platform": ["youtube"],
    "space_id": null,
    "tag_id": null,
    "is_favourite": null,
    "archive": "active"
  },
  "limit": 20,
  "cursor": null
}
```

| Field | Contract |
| --- | --- |
| `query` | Required string; Unicode-trimmed; 2–500 code points and at most 2,000 UTF-8 bytes |
| `mode` | `hybrid` (default), `semantic`, or `keyword` |
| `filters.platform` | Optional distinct allowlisted values; maximum 8 |
| `filters.space_id` | Optional one owned Space UUID |
| `filters.tag_id` | Optional one owned Tag UUID |
| `filters.is_favourite` | Optional boolean |
| `filters.archive` | `active` default, `archived`, or `all` |
| `limit` | Default 20; minimum 1; maximum 50 |
| `cursor` | Optional opaque integrity-protected cursor bound to owner, normalized request, ranking version, and active model |

Whitespace is normalized for the provider but the query is not translated or persisted. A
foreign Space/Tag is safe `404`; malformed IDs and invalid/empty/oversized queries are `422`.

Response:

```json
{
  "items": [
    {
      "discovery": {
        "id": "b8d42b2a-b68c-4d0e-a2aa-40f17a74a1a2",
        "custom_title": "Fukushima ghost town documentary",
        "platform": "youtube",
        "is_favourite": false,
        "archived_at": null
      },
      "relevance": {
        "score": 0.82,
        "semantic_similarity": 0.79,
        "keyword_match": true,
        "match_reasons": ["title", "summary"]
      }
    }
  ],
  "next_cursor": null,
  "search": {
    "requested_mode": "hybrid",
    "effective_mode": "hybrid",
    "fallback_reason": null,
    "index_coverage": "partial",
    "indexed_count": 42,
    "eligible_count": 50,
    "ranking_version": "semantic-hybrid-v1"
  }
}
```

The existing public Discovery representation is reused in full; abbreviated fields above are only
for readability. `score` is a 0–1 presentation score from ranking v1, not a probability. Raw
distance is never exposed. `semantic_similarity` may be null for keyword-only candidates.
`match_reasons` is an allowlisted provenance category (`custom_title`, `metadata_title`,
`metadata_description`, `summary`, `topic`, `private_context`, `keyword`) and must be emitted only
when reliably derived; it never returns matched private text.

Hybrid candidate retrieval uses the same filters for both branches. Semantic candidates below the
configured evaluated threshold are discarded. Keyword candidates remain, including unembedded
Discoveries. Exact normalized title matches receive a deterministic boost. The default limit is
20; retrieve at most 100 candidates per branch, fuse with RRF, then paginate the stable fused list.
Because rankings can change after indexing, cursors are short-lived and invalidated by ranking/model
changes; invalid/stale cursors return `422 invalid_cursor`.

If semantic search is disabled, provider configuration is absent, the provider times out/rate
limits, or no confident semantic candidate exists:

- `mode=hybrid` returns `200` keyword-only results with `effective_mode: keyword` and an allowlisted
  `fallback_reason` (`feature_disabled`, `provider_unavailable`, `provider_rate_limited`,
  `provider_timeout`, `no_confident_semantic_match`, or `no_current_embeddings`);
- `mode=semantic` returns `503 feature_disabled` or `provider_unavailable` when it cannot execute,
  and returns `200` empty results for a successful query with no confident match;
- `mode=keyword` never calls an embedding provider.

Provider runtime errors do not expose secrets and do not turn valid hybrid requests into 500s.

## Index one Discovery

`POST /api/v1/discoveries/{discovery_id}/embedding`

Request body is `{}`. `Idempotency-Key` is required: 16–128 printable ASCII characters, hashed at
rest and scoped to owner, Discovery, action, and current target fingerprint.

- `202 Accepted`: durable pending work recorded; `Location` points to status.
- `200 OK`: the current target already succeeded or identical active work exists; no new cost.
- `422 embedding_input_unsupported`: the canonical document would be empty.
- `429 embedding_limit_exceeded`: user quota/abuse limit, with bounded `Retry-After` when known.
- `503 feature_disabled` or `provider_not_configured`: no work is created.

Discovery saving and metadata enrichment never wait for this route or provider execution.

## Retry

`POST /api/v1/discoveries/{discovery_id}/embedding/retry`

```json
{"confirm": true}
```

Requires a new `Idempotency-Key`, `confirm: true`, and an owned row in `failed`, `stale`, or an
expired recoverable `processing` state. It returns `202` for accepted work or `200` if the same
request already completed/current state needs no work. `409 embedding_not_retryable` covers a
current success or permanent unsupported state; `409 embedding_processing` covers a live lease.
`429 retry_limit_exceeded`/`Retry-After` applies. Concurrent calls can create at most one active
claim/provider charge.

## Embedding status

`GET /api/v1/discoveries/{discovery_id}/embedding/status`

```json
{
  "status": "succeeded",
  "is_searchable": true,
  "generated_at": "2026-08-05T12:00:00Z",
  "last_attempted_at": "2026-08-05T11:59:58Z",
  "can_index": false,
  "can_retry": false,
  "retry_after_seconds": null,
  "error": null
}
```

Public status is `unavailable`, `pending`, `processing`, `succeeded`, `failed`, `unsupported`, or
`stale`. `unavailable` means no row and still returns `200` for an owned Discovery. `stale` is
derived from current document/configuration even if stored status has not been updated. Provider,
model, dimension, fingerprint, vector, tokens/cost, retry count, leases, and private-context field
names are not returned.

## Bounded backfill

`POST /api/v1/embeddings/backfill`

```json
{
  "limit": 100,
  "include_stale": true
}
```

`limit` is 1–100 and defaults to 50. `Idempotency-Key` is required. The service owner-scopes
eligible Discoveries, uses stable `(created_at, id)` order, skips current/active work, reserves
quota atomically, and enqueues at most the requested and configured cap. It never embeds inline.

```json
{
  "status": "accepted",
  "requested": 100,
  "queued": 37,
  "skipped_current": 50,
  "skipped_unsupported": 3,
  "remaining_eligible": 10
}
```

Return `202` when rows were queued, `200` for an idempotent replay or nothing eligible, `404` is not
used for empty libraries, `429` when quota/budget prevents any reservation, and `503` when feature,
provider, worker, or backfill is disabled. Counts include only the caller's library and reveal no
content. There is no global cursor or account selector.

## Safe errors and common statuses

```json
{
  "error": {
    "code": "provider_temporarily_unavailable",
    "message": "Meaning-based search is temporarily unavailable. Keyword search is still available.",
    "request_id": "req_opaque",
    "details": null
  }
}
```

Allowed public codes include `resource_not_found`, `validation_error`, `invalid_cursor`,
`feature_disabled`, `provider_not_configured`, `provider_temporarily_unavailable`,
`embedding_processing`, `embedding_not_retryable`, `embedding_input_unsupported`,
`embedding_limit_exceeded`, `query_limit_exceeded`, `retry_limit_exceeded`,
`idempotency_key_reused`, and `internal_error`. Details may name invalid fields but never echo
query, Tag, Space, note, provider text, vector, document, credential, or database data.

| Status | Meaning |
| --- | --- |
| `200` | Search/read/idempotent completed request |
| `202` | Durable indexing/backfill accepted |
| `401` | No valid session |
| `404` | Owned resource absent or foreign |
| `409` | Active/nonretryable state or idempotency conflict |
| `415` | Body content type is not JSON |
| `422` | Invalid bounded path/query/body/header/cursor |
| `429` | Per-user/IP/query/index/cost limit; safe `Retry-After` |
| `503` | Feature/provider/worker unavailable when fallback is not applicable |

Rate limits are per authenticated user plus IP-aware production controls. Provider calls have a
short configured timeout. Query vectors live only for the request or a private short-lived cache;
no semantic query or raw query vector is persisted or logged.

## Portfolio implementation clarification

The current portfolio API returns bounded results with `next_cursor: null`; cursor pagination is
postponed. Fake-provider work and capped owner backfill run inline, so this is not a durable queue.
Idempotency headers are validated and current/active work is suppressed, while durable historical
key replay storage is postponed with the worker. Limits are single-process controls; distributed
user/IP accounting is a production blocker. Keyword fallback remains available.
