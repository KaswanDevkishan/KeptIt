# KeptIt Architecture

## High-level system architecture

KeptIt is planned as a browser-based React single-page application backed by a versioned FastAPI JSON API and PostgreSQL. The application stores original URLs, user content, permitted metadata, and organizational data; it does not store copies of copyrighted videos.

```text
Browser / mobile web
        |
        | HTTPS JSON API
        v
React + TypeScript  --->  FastAPI application  --->  PostgreSQL
                                  |
                                  | controlled, asynchronous enrichment
                                  v
                        Approved metadata providers
```

The web and API processes should be independently deployable. Metadata work should move to an asynchronous worker when its volume or latency justifies one; the MVP must not require a queue to complete a core save.

## Frontend responsibilities

- Render registration, login, library, Discovery, Space, tag, search, and filter experiences.
- Manage navigation and protected-route presentation with React Router.
- Validate inputs for immediate feedback while treating backend validation as authoritative.
- Send credentials safely, handle authentication state, and avoid persisting sensitive tokens in browser storage.
- Present accessible loading, empty, error, confirmation, and responsive states.
- Keep API transport, domain types, feature UI, and shared presentation components separate.

## Backend responsibilities

- Expose a versioned API with validated request and response schemas.
- Register and authenticate users, manage sessions, and enforce authorization.
- Normalize URLs, detect platforms, identify duplicates, and persist Discoveries.
- Manage Spaces, tags, search, filters, pagination, archive state, and deletion.
- Coordinate safe metadata enrichment without making third-party availability part of the save transaction.
- Produce structured logs and consistent errors without leaking sensitive information.

## Database responsibilities

PostgreSQL is the source of truth for users, server-side sessions, Discoveries, Spaces, tags, and their relationships. It provides transactional integrity, ownership constraints, uniqueness guarantees, indexes for library queries, and later full-text/vector capabilities. Alembic owns all schema evolution.

Implemented core entities include `users`, `user_sessions`, `discoveries`, `spaces`, and
`space_memberships`, `tags`, and `discovery_tags`.
Ownership is explicit on top-level user resources. A per-user unique constraint on the canonical
URL hash provides concurrency-safe duplicate protection.

## Core data-model direction

A **Discovery** is the core domain entity: one user's private memory of something found on the internet. A **Space** is a user-visible collection of Discoveries. Every Discovery, Space, and Tag has one owning User, and every read or mutation is scoped to that owner on the server.

Discovery preserves the accepted original URL, a versioned canonical form, deterministic platform classification, and personal context such as custom title, note, save reason, importance, favourite state, and archive state. Externally fetched source facts—title, description, thumbnail, creator or publisher, and publication time—live in a separate Metadata Record when enrichment is introduced. Future inferred summaries, topics, connections, Memory Threads, and Insights remain separately versioned and must not overwrite user-authored context or masquerade as source facts.

This separation lets the basic private library work without metadata providers or AI. It also provides an additive path toward the future Memory Engine: visits and feedback can describe memory behaviour; relational edges can connect Discoveries; and PostgreSQL-native vector records can later support semantic retrieval. These tables are introduced only with their product feature, privacy policy, and deletion behavior.

Detailed decisions and schemas are documented in:

- [Data model](data-model.md)
- [Database decisions](database-decisions.md)
- [Entity relationships](entity-relationship.md)
- [MVP schema](mvp-schema.md)
- [Spaces feature implementation plan](spaces-implementation-plan.md)
- [Tags implementation plan](tags-implementation-plan.md)

## Tags architecture (implemented)

Tags are private, user-authored cross-Space descriptors: a Space answers where a Discovery belongs,
while a Tag answers what it is about. `tags` owns stable names and `discovery_tags` represents the
many-to-many relationship. Both tables carry an owner boundary; membership uses immutable
`user_id`, a tenant-aware Tag foreign key, and the same narrow Discovery-owner trigger pattern as
the implemented Spaces feature. Owner-scoped service queries remain mandatory and foreign resources
behave as not found.

Discovery list/detail responses will include bounded `{id, name}` Tag summaries loaded without
N+1 queries. Assignment and one-Tag library filtering do not alter URL identity, metadata, AI
Summary behavior, archive state, or Space membership. User Tags remain distinct from AI Summary
topics. A later AI system may propose existing Tag IDs or candidate text for explicit acceptance,
but inferred suggestions require separate provenance and are not added to the user-authored Tag
tables automatically. See the [implementation plan](tags-implementation-plan.md),
[database decisions](tags-database-decisions.md), and [API contract](tags-api-contract.md).

## AI Summaries architecture (next phase)

AI Summaries are optional private derived data in a separate one-current-row-per-Discovery table.
They never overwrite or masquerade as user-authored `custom_title`, `personal_note`, `save_reason`,
favourite/archive state, Space membership, or externally fetched Metadata Record fields. Discovery
capture, enrichment, and the rest of the library continue to work when the feature flag is off, no
provider is configured, or generation fails.

A small typed provider boundary accepts only bounded approved metadata and returns structured
candidate output plus provider/model/prompt provenance, safe classified errors, and usage where
available. The first release uses explicit manual generation; a durable database-backed worker
claims pending rows outside page/save latency before real-provider production use. Local startup
requires neither an AI key nor a live provider.

The lifecycle is `unavailable` (no row), `pending`, `processing`, then `succeeded`, `failed`,
`unsupported`, or `insufficient_data`; a successful result is presented as `stale` when its approved
metadata fingerprint no longer matches. Regeneration is explicit and preserves the previous valid
output until replacement succeeds.

The privacy-first input policy sends source title/description, site/provider, creator/publisher,
published date, deterministic platform, and canonical hostname only. It excludes user notes, save
reason, custom title, email/account/session data, Spaces, raw URLs, internal IDs, logs, and full
records. A future per-request note opt-in requires separate consent and fingerprints the note as
subjective context. Metadata is untrusted prompt data, the model has no tools or browsing, and
strict backend output validation and plain-text escaping remain the security boundary.

Stable summary IDs, source fingerprints, model identifiers, and prompt versions allow a future
semantic-search phase to reference a specific generated source. No embeddings, vectors, semantic
search tables, or automatic Tags belong to the AI Summaries schema. See the
[implementation plan](ai-summaries-implementation-plan.md),
[database decisions](ai-summaries-database-decisions.md),
[API contract](ai-summaries-api-contract.md), and
[prompt specification](ai-summaries-prompt-spec.md).

## Proposed backend modules

```text
backend/
├── app/
│   ├── api/             # Versioned routes and dependencies
│   ├── auth/            # Identity, password hashing, sessions/tokens
│   ├── core/            # Configuration, security, errors, logging
│   ├── db/              # Engine, sessions, base models
│   ├── models/          # SQLAlchemy persistence models
│   ├── schemas/         # Pydantic API contracts
│   ├── repositories/    # Scoped database access
│   ├── services/        # Use cases and authorization-aware orchestration
│   ├── metadata/        # Safe provider adapters and enrichment policy
│   └── main.py          # Application factory/entry point
├── migrations/          # Alembic revisions
└── tests/               # Unit, integration, and API tests
```

Exact package boundaries should be validated during scaffolding rather than treated as immutable.

The implemented Discovery slice uses `models/discovery.py`, `schemas/discovery.py`, focused
`services/urls.py` and `services/discoveries.py` modules, and authenticated routes in
`api/routes/discoveries.py`. The frontend keeps typed transport in `features/discoveries/api.ts`
and the responsive library workflow beside it. No generic repository abstraction or metadata
boundary was added for this phase.

## Proposed frontend modules

```text
frontend/src/
├── app/                 # Router, providers, application shell
├── api/                 # Typed HTTP client and API contracts
├── features/
│   ├── auth/
│   ├── library/
│   ├── discoveries/
│   ├── spaces/
│   ├── tags/
│   └── search/
├── components/          # Reusable presentation components
├── hooks/               # Shared React behavior
├── styles/              # Global tokens and minimal global styles
├── types/               # Shared client-side types
└── test/                # Test setup and helpers
```

Feature-specific components, styles, tests, and state should remain close to their feature.

## API request flow

1. The browser sends an HTTPS request to a versioned endpoint such as `/api/v1/discoveries`.
2. Middleware assigns a request ID, applies trusted-proxy and security policy, and records safe timing data.
3. Authentication establishes the current identity; route dependencies reject unauthenticated access where required.
4. Pydantic validates the request contract.
5. The service layer applies business rules and authorization, calling repositories with the current user's scope.
6. SQLAlchemy executes a transaction against PostgreSQL.
7. A response schema serializes an explicit, stable API representation.
8. Known failures become consistent JSON errors; unexpected failures are logged with correlation data and return a generic message.

## Authentication approach

Use email or another documented identifier plus a password hashed with a current adaptive algorithm such as Argon2id. Prefer secure, `HttpOnly`, `Secure`, appropriately scoped `SameSite` cookies for browser sessions. If cookies authenticate state-changing requests, add a deliberate CSRF defense. Rotate session identifiers on login and privilege changes, support server-side revocation or bounded session lifetimes, and rate-limit sensitive endpoints.

Password recovery uses random opaque tokens delivered through a replaceable email boundary. Only
SHA-256 token digests are stored. Tokens expire, are single-use, and supersede earlier unused tokens
for the account. Confirmation changes the Argon2id password hash and revokes all active sessions in
one database transaction. Development delivery uses an ignored file outbox and fragment-based
frontend links; production must replace that backend and add distributed IP/account rate limits.

Authentication only establishes who the caller is. Its implementation should remain separate from authorization policy.

## Authorization approach

All private-resource queries and mutations must be scoped by the authenticated user's ID at the database access boundary. Services should verify ownership for Discoveries, Spaces, and tags, including relationship updates. Return non-enumerating not-found responses when appropriate. Frontend route guards improve user experience but are never an authorization control. Cross-user and insecure-direct-object-reference tests are required.

## Metadata-processing approach

The initial save transaction stores the validated original URL, normalized comparison fields, detected platform, and user-authored data. Metadata enrichment is best-effort and logically separate. Prefer official APIs or documented metadata mechanisms, cache permitted results, identify the application honestly, and honor terms, rate limits, and removal requirements.

Generic fetching must allow only public HTTP(S) destinations, resolve and re-check redirects, block private/reserved/link-local addresses, cap redirects, bytes, and duration, and accept only intended content types. Sanitize all third-party text and URLs before display. Record a bounded status such as pending, succeeded, unavailable, or failed; retries must be limited. Never download or persist copyrighted video media.

The implemented first enrichment slice creates one current `metadata_records` row atomically with
each Discovery and leaves it `pending`. `POST /api/v1/discoveries/{id}/enrich` performs a bounded
attempt outside Discovery creation; `/enrich/retry` has identical idempotent behavior. This manual,
in-process approach keeps saves and startup independent of third parties and avoids a premature
queue. The service boundary can be called by a durable background worker later.

The safe fetcher permits only HTTP(S), rejects credentials and every non-global resolved address,
checks each redirect, limits redirects, time, intended content types, and decompressed bytes, and
sends no cookies or caller-controlled headers. Provider adapters use GitHub's repository API with
safe HTML fallback and YouTube's official API when configured. DNS is validated immediately before
each request, but the high-level client does not pin that address through connection establishment;
production should add egress policy and/or a reviewed IP-pinning transport for stronger rebinding
defense.

## Duplicate-link detection approach

Duplicates are scoped to one user. Before insertion, compute a versioned canonical URL and hash and query for an existing active or archived Discovery. A database unique constraint on `(user_id, canonical_url_hash)` is authoritative and handles concurrent saves. The API should return a conflict with the existing Discovery's safe identifier rather than create a silent duplicate. Future product policy may allow an explicit duplicate override, but it is not assumed for MVP.

## URL normalization approach

Normalization is conservative and versioned so it does not incorrectly merge distinct resources:

- Parse with a standards-compliant URL parser and accept only `http` and `https`.
- Lowercase the scheme and internationalized hostname representation.
- Remove fragments, default ports, and an empty trailing path distinction where demonstrably equivalent.
- Normalize percent encoding and path dot segments without changing resource semantics.
- Remove only an explicit, tested allowlist of tracking parameters such as common `utm_*` fields.
- Apply tested platform-specific canonicalization for recognized share and canonical URL forms.
- Sort retained query pairs deterministically in normalization version 1; the conservative removal
  list is limited to common tracking fields, and meaningful names, values, and repeats remain.

Always retain the submitted original URL separately. Do not follow redirects solely to decide identity during the synchronous save because it adds latency, tracking, and SSRF risk.

## Error-handling approach

Define a stable error envelope containing a machine-readable code, safe message, optional field details, and request ID. Map validation, unauthenticated, forbidden/not-found, conflict, rate-limit, and server failures to suitable HTTP statuses. Do not expose stack traces, SQL details, credentials, or third-party response bodies. The frontend should distinguish actionable validation and conflict states from retryable service failures.

## Logging approach

Use structured logs with timestamp, severity, environment, service, request ID, route template, status, and duration. Avoid raw query strings and redact credentials, cookies, authorization headers, personal notes, search text, and tokens. Do not log full third-party page bodies. Production logs should be centralized with retention and access controls; error reporting should use correlation IDs and avoid sensitive payloads.

## Testing strategy

- **Backend unit tests:** URL normalization, platform detection, validation, authorization rules, and service behavior.
- **Backend integration/API tests:** PostgreSQL constraints, migrations, authentication lifecycle, ownership isolation, pagination, duplicate races, and error contracts.
- **Frontend component tests:** Forms, keyboard behavior, responsive state logic, filters, protected navigation, and success/error presentation with React Testing Library and Vitest.
- **End-to-end tests:** Critical register, login, save, search, edit, archive, and delete journeys once both applications exist.
- **Security tests:** Cross-user access, CSRF/CORS behavior, rate limits, malicious URLs, redirect-based SSRF, and unsafe metadata.
- **Quality checks:** Python and TypeScript formatting, linting, type checking, migration checks, and production builds in CI.

Tests should use isolated databases and deterministic provider fakes; they must not depend on live social platforms.

## Semantic Search architecture (next planned phase)

Semantic Search is optional and additive. A versioned document builder creates one bounded text
representation per Discovery from an explicit privacy allowlist. Custom title, approved metadata,
platform/hostname, and available AI Summary content are included by default; personal notes, save
reasons, Tags, and Spaces require the explicit private-context setting. Raw URLs and account data
are excluded. A small replaceable embedding-provider boundary has a deterministic offline fake and
at most one optional real adapter; provider keys stay backend-only.

`discovery_embeddings` is a separate one-current-row dependent table in PostgreSQL using pgvector.
Its provider/model/dimension, document version, input fingerprint, vector, lifecycle, usage/cost,
and lease state support `pending`, `processing`, `succeeded`, `failed`, `unsupported`, and derived
`stale` behavior. Discovery/account deletion cascades vectors. Discovery saving never waits for an
embedding call. Manual indexing and bounded user backfill are first-release triggers; a separately
deployed database-backed lease worker is required before real-provider production use.

Retrieval starts with exact cosine search over only current embeddings joined to Discoveries owned
by the authenticated user and constrained by Space, Tag, platform, favourite, and archive filters.
Hybrid mode fuses bounded semantic and existing keyword rankings, boosts exact titles, and keeps
unembedded Discoveries keyword-discoverable. Keyword search remains available when Semantic Search
is disabled, unavailable, or has no confident match. HNSW is postponed until measured exact-search
latency and scale justify approximate retrieval; no external vector database, raw-vector API, chat,
or RAG answer generation is part of this phase. See the
[implementation plan](semantic-search-implementation-plan.md),
[database decisions](semantic-search-database-decisions.md),
[API contract](semantic-search-api-contract.md), and
[document specification](semantic-search-document-spec.md).

## Security considerations

- Validate and bound all input; parameterize database access through SQLAlchemy.
- Enforce authentication and per-owner authorization on the server.
- Use HTTPS, secure cookies, CSRF protection where applicable, a narrow CORS allowlist, and security headers.
- Protect metadata fetches against SSRF, DNS rebinding, redirect abuse, oversized responses, decompression bombs, and unsafe content.
- Hash passwords with an adaptive algorithm and rate-limit registration, login, save, and enrichment endpoints.
- Manage secrets outside source control and rotate them; grant database and platform credentials least privilege.
- Escape untrusted output and sanitize any allowed markup to prevent XSS.
- Pin and scan dependencies, review migrations, back up PostgreSQL, and test restoration.
- Define deletion, retention, incident response, and audit policies before production.

## Deployment overview

The likely initial deployment uses a managed platform such as Render for separate frontend/static, API, and PostgreSQL services. Configuration comes from environment variables and managed secrets. Deployments should run migrations as a controlled release step, expose a lightweight health endpoint, terminate TLS, and keep the API stateless. Production readiness requires CI gates, restricted network access, monitoring, alerting, database backups with restore tests, rollback procedures, and separately scalable worker infrastructure if asynchronous enrichment is introduced.
# AI Summaries implementation note

AI Summaries are an optional derived subsystem. Owner-scoped routes durably record current work;
typed fake/OpenAI adapters receive a privacy-minimized metadata envelope; strict validation stores
only normalized output and usage. Read-time SHA-256 fingerprint comparison derives staleness.
Regeneration preserves the previous success until replacement succeeds, and Discovery deletion
cascades. The local in-process executor is not a production-durable worker.
## Semantic Search implementation

Semantic Search is an optional additive backend subsystem. A deterministic document builder feeds
the fake or explicitly enabled OpenAI adapter; one `discovery_embeddings` row owns the current
`vector(1536)` and lifecycle state. Authenticated indexing/status/backfill routes remain owner
scoped through Discovery. PostgreSQL Meaning search uses bounded pgvector `<=>` exact-cosine and
keyword candidates under the same owner/filter predicates,
applies the existing relational filters, and fuses them with `semantic-hybrid-v1` RRF. Keyword
fallback keeps the library usable during disablement or provider outages. Raw queries are not
persisted and vectors never enter public schemas. The in-process portfolio executor is not
production durable; real-provider rollout requires a separate lease worker.
SQLite's in-memory cosine implementation exists only for isolated automated tests. Cursor
pagination, private-context settings, durable queues, distributed limits, HNSW, monitoring,
budgets, and alerts are postponed.
