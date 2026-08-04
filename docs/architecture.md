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

Initial entities are `users`, `user_sessions`, `discoveries`, `spaces`, `space_memberships`, `tags`, and `discovery_tags`. Ownership is explicit on top-level user resources. A per-user unique constraint on the canonical URL hash provides concurrency-safe duplicate protection.

## Core data-model direction

A **Discovery** is the core domain entity: one user's private memory of something found on the internet. A **Space** is a user-visible collection of Discoveries. Every Discovery, Space, and Tag has one owning User, and every read or mutation is scoped to that owner on the server.

Discovery preserves the accepted original URL, a versioned canonical form, deterministic platform classification, and personal context such as custom title, note, save reason, importance, favourite state, and archive state. Externally fetched source facts—title, description, thumbnail, creator or publisher, and publication time—live in a separate Metadata Record when enrichment is introduced. Future inferred summaries, topics, connections, Memory Threads, and Insights remain separately versioned and must not overwrite user-authored context or masquerade as source facts.

This separation lets the basic private library work without metadata providers or AI. It also provides an additive path toward the future Memory Engine: visits and feedback can describe memory behaviour; relational edges can connect Discoveries; and PostgreSQL-native vector records can later support semantic retrieval. These tables are introduced only with their product feature, privacy policy, and deletion behavior.

Detailed decisions and schemas are documented in:

- [Data model](data-model.md)
- [Database decisions](database-decisions.md)
- [Entity relationships](entity-relationship.md)
- [MVP schema](mvp-schema.md)

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
- Sort query parameters only where ordering is known not to be meaningful.

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

## Future semantic-search architecture

After the MVP is stable, a background pipeline can build a permitted text representation from Discovery titles, descriptions, notes, summaries, tags, and other approved fields. It chunks where useful, creates embeddings through a replaceable provider interface, and stores model/version metadata alongside vectors in PostgreSQL with pgvector. Updates and deletion enqueue re-indexing or vector removal.

Search can combine PostgreSQL full-text ranking with vector similarity, apply user ownership and filters before returning results, and fuse rankings in the service layer. “Ask my library” responses must be grounded only in the authenticated user's retrieved Discoveries, link to sources, tolerate missing source content, and disclose AI processing. Derived data follows the same deletion and privacy rules as its source.

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
