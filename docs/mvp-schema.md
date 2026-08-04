# MVP Schema Recommendation

## Scope

The smallest production-worthy product schema is seven tables: `users`, `user_sessions`, `discoveries`, `spaces`, `space_memberships`, `tags`, and `discovery_tags`. The next implementation sprint creates only `users` and `user_sessions`; the five Discovery and organization tables follow in the next phase.

All IDs are PostgreSQL `uuid`. All instants are `timestamptz` and UTC. Unless stated otherwise, UUIDs and timestamps are supplied consistently by the application or database and are not user-controlled.

## `users`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `email` | `citext` | not null | Trim; valid email; max 320 chars; normalize once at boundary | Unique |
| `password_hash` | `text` | not null | Encoded output of approved adaptive password hasher; never returned/logged; max 512 chars | Check non-empty |
| `is_active` | `boolean` | not null; `true` | Service-controlled | — |
| `created_at` | `timestamptz` | not null; current time | UTC instant | — |
| `updated_at` | `timestamptz` | not null; current time | UTC; update on mutation | — |

If avoiding the `citext` extension is operationally preferable, use normalized lowercase `text` with a unique index on `lower(email)`. Choose one approach in the first migration and test Unicode/case behavior; `citext` is recommended as PostgreSQL-native and mature.

## `user_sessions`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Existing User | FK to `users.id` `ON DELETE CASCADE`; index with expiry |
| `token_hash` | `bytea` | not null | Fixed output length for keyed/cryptographic token hashing; raw token exists only in cookie | Unique |
| `created_at` | `timestamptz` | not null; current time | UTC | — |
| `expires_at` | `timestamptz` | not null | Later than creation; bounded session lifetime | Index for cleanup |
| `last_seen_at` | `timestamptz` | null | UTC; updates should be rate-limited to avoid write amplification | — |
| `revoked_at` | `timestamptz` | null | UTC; null means not revoked | — |

Add unique index on `token_hash`, index `(user_id, expires_at)`, and index `expires_at`. Authentication accepts a session only when not revoked and not expired. Store no refresh token: the opaque cookie token selects this server-side session.

## `discoveries`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner | FK to `users.id` `ON DELETE CASCADE`; leads owner indexes |
| `original_url` | `text` | not null | HTTP(S), absolute, max 2,048 chars; preserve accepted user input | Check reasonable length/protocol at app boundary |
| `canonical_url` | `text` | not null | Versioned conservative normalization; max 2,048 chars | Compare after a hash match |
| `canonical_url_hash` | `bytea` | not null | Fixed SHA-256 digest of canonical URL | Unique with `user_id` |
| `normalization_version` | `smallint` | not null; `1` | Positive supported version | Check `> 0` |
| `platform` | `text` | not null; `webpage` | Application allowlist: `instagram`, `youtube`, `tiktok`, `reddit`, `x`, `github`, `webpage`; lowercase | Check allowed values; owner/platform index |
| `custom_title` | `varchar(300)` | null | User-authored; trim; empty becomes null; plain text | — |
| `personal_note` | `text` | null | User-authored; empty becomes null; max 10,000 chars; plain text | Check length |
| `save_reason` | `varchar(500)` | null | User-authored free form; empty becomes null | Check length |
| `importance` | `smallint` | null | Optional 1–5 only; do not require UI support initially | Check between 1 and 5 |
| `is_favourite` | `boolean` | not null; `false` | User-controlled | — |
| `archived_at` | `timestamptz` | null | UTC; null means active | Included in library index |
| `created_at` | `timestamptz` | not null; current time | Save time in UTC | Library ordering index |
| `updated_at` | `timestamptz` | not null; current time | UTC; update on mutation | — |

Constraints/indexes:

- Unique `(user_id, canonical_url_hash)` across active and archived Discoveries.
- Index `(user_id, archived_at, created_at DESC, id DESC)` for stable keyset pagination.
- Index `(user_id, platform, created_at DESC, id DESC)` for platform-filtered browsing.
- The service must compare `canonical_url` when an existing hash is found and fail safely on a true hash collision.

`platform` is inferred by deterministic application logic, not fetched metadata. Source title, description, thumbnail, creator/publisher, and publication time wait for `metadata_records` in the enrichment phase.

## `spaces`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner | FK to `users.id` `ON DELETE CASCADE` |
| `name` | `varchar(100)` | not null | User-authored; trimmed; non-empty | — |
| `normalized_name` | `varchar(100)` | not null | Stable trim/case normalization | Unique with `user_id` |
| `description` | `varchar(500)` | null | User-authored plain text; empty becomes null | — |
| `created_at` | `timestamptz` | not null; current time | UTC | — |
| `updated_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(user_id, normalized_name)`. Do not seed a default Space; an unassigned Discovery is valid.

## `space_memberships`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `space_id` | `uuid` | not null | Space owned by current User | FK to `spaces.id` `ON DELETE CASCADE`; composite PK first |
| `discovery_id` | `uuid` | not null | Discovery owned by same User | FK to `discoveries.id` `ON DELETE CASCADE`; composite PK second |
| `created_at` | `timestamptz` | not null; current time | UTC | — |

Primary key `(space_id, discovery_id)` and reverse index `(discovery_id, space_id)`. The service must query both parents under the current `user_id` in the same transaction before inserting.

## `tags`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner | FK to `users.id` `ON DELETE CASCADE` |
| `name` | `varchar(50)` | not null | User-authored; trimmed; non-empty | — |
| `normalized_name` | `varchar(50)` | not null | Stable trim/case normalization | Unique with `user_id` |
| `created_at` | `timestamptz` | not null; current time | UTC | — |
| `updated_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(user_id, normalized_name)`. Preserve display casing in `name`.

## `discovery_tags`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `discovery_id` | `uuid` | not null | Discovery owned by current User | FK to `discoveries.id` `ON DELETE CASCADE`; composite PK first |
| `tag_id` | `uuid` | not null | Tag owned by same User | FK to `tags.id` `ON DELETE CASCADE`; composite PK second |
| `created_at` | `timestamptz` | not null; current time | UTC | — |

Primary key `(discovery_id, tag_id)` and reverse index `(tag_id, discovery_id)`. Enforce same-owner assignment in scoped service operations and cross-user tests.

## Naming and foreign-key conventions

- Use plural `snake_case` table names and singular `snake_case` column names.
- Name primary keys `id`; name foreign keys `<referenced_singular>_id`.
- Name constraints explicitly: `pk_<table>`, `fk_<table>_<column>_<target>`, `uq_<table>_<columns>`, and `ck_<table>_<rule>`. Name indexes `ix_<table>_<columns_or_purpose>`.
- Every foreign key states deletion behavior. Index foreign keys used for reverse lookup; PostgreSQL does not create those indexes automatically.
- Use `created_at`, `updated_at`, and state-specific timestamps such as `archived_at`, not generic `date` fields.
- API/domain terminology is Discovery and Space even if “save” remains a verb.

## Migration order

Use small Alembic revisions with reviewed downgrade behavior:

1. Enable an approved UUID approach and `citext` if selected; create `users`.
2. Create `user_sessions` and its indexes. This completes the next authentication coding phase.
3. Create `discoveries` and duplicate/library indexes.
4. Create `spaces` and `tags`.
5. Create `space_memberships` and `discovery_tags`.

Steps 3–5 belong to the following Discovery phase. Splitting identity from product tables makes authentication independently reviewable; joins must follow both parents.

## Seed data

No production seed data is required. Registration creates Users; users create their own Spaces and Tags. Tests should use factories/fixtures with clearly synthetic credentials and URLs. Development-only sample data must be opt-in, deterministic, and never part of production migrations.

## Explicit exclusions

The first schema does not include fetched metadata, metadata history, enrichment jobs, visits or counters, structured intents, connections, rediscovery events or feedback, Memory Threads, Insights, extracted entities/topics, summaries, embeddings, vector indexes, weekly digests, sharing, collaboration, or a graph database. Audit Events should be added only when the authentication implementation defines concrete security events and retention; privacy-safe structured application logs can cover the initial development environment.

These exclusions are deliberate. Each future table should arrive with the behavior, authorization cases, deletion rules, retention policy, and tests that make it useful.
