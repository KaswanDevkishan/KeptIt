# MVP Schema Recommendation

## Scope

The production schema has grown incrementally through authentication, Discoveries, metadata,
Spaces, and optional AI Summaries. The next approved growth phase adds `tags` and `discovery_tags`;
they are documented here but do not exist yet.

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
| `normalized_name` | `varchar(200)` | not null | Versioned NFKC/case-fold normalization | Unique with `user_id` |
| `description` | `varchar(500)` | null | User-authored plain text; empty becomes null | — |
| `created_at` | `timestamptz` | not null; current time | UTC | — |
| `updated_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(user_id, normalized_name)`, supporting unique `(user_id, id)`, owner-led pagination,
and non-empty checks. `normalized_name` uses the versioned NFKC/case-fold contract. Do not seed a
default Space; an unassigned Discovery is valid. The exact production schema is specified in the
[Spaces feature implementation plan](spaces-implementation-plan.md).

## `space_memberships`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner; immutable | FK to `users.id` `ON DELETE CASCADE` |
| `space_id` | `uuid` | not null | Space owned by current User | Tenant-aware FK with `user_id` to `spaces(user_id, id)` `ON DELETE CASCADE` |
| `discovery_id` | `uuid` | not null | Discovery owned by same User | FK to `discoveries.id` `ON DELETE CASCADE`; owner trigger |
| `created_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(space_id, discovery_id)`, owner-led Space contents index
`(user_id, space_id, created_at DESC, id DESC)`, and reverse index
`(user_id, discovery_id, space_id)`. The service must still query both parents under the current
`user_id` in the same transaction before inserting; the composite Space foreign key and
Discovery-owner trigger provide defense in depth without modifying Discoveries.

## `tags`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner | FK to `users.id` `ON DELETE CASCADE` |
| `name` | `varchar(50)` | not null | User-authored; trimmed; non-empty | — |
| `normalized_name` | `text` | not null | NFKC then Unicode case-fold comparison key | Unique with `user_id` |
| `created_at` | `timestamptz` | not null; current time | UTC | — |
| `updated_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(user_id, normalized_name)`, supporting unique `(user_id, id)`, non-empty checks, and
an owner-leading alphabetical index `(user_id, normalized_name, id)` if query-plan rehearsal shows
the appended pagination key is useful. Names are 1–50 Unicode code points after outer-whitespace
trimming; reject null/control characters. Do not collapse internal whitespace. Preserve display
spelling in `name`. No color column belongs in MVP.

## `discovery_tags`

| Field | PostgreSQL type | Null/default | Validation | Index/constraint |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; application-generated UUIDv4 | Valid UUID | Primary key |
| `user_id` | `uuid` | not null | Authenticated owner; immutable | FK to `users.id` `ON DELETE CASCADE` |
| `tag_id` | `uuid` | not null | Tag owned by same User | Tenant-aware FK with `user_id` to `tags(user_id, id)` `ON DELETE CASCADE` |
| `discovery_id` | `uuid` | not null | Discovery owned by current User | FK to `discoveries.id` `ON DELETE CASCADE`; owner trigger |
| `created_at` | `timestamptz` | not null; current time | UTC | — |

Add unique `(tag_id, discovery_id)`, `(user_id, discovery_id, tag_id)`, and
`(user_id, tag_id, created_at DESC, id DESC)`. The service loads both parents under the current
User; a composite Tag foreign key and narrow Discovery-owner trigger enforce same-owner assignment
in PostgreSQL. Deleting a Tag deletes memberships only. See the
[Tags implementation plan](tags-implementation-plan.md) for the normative schema.

## Naming and foreign-key conventions

- Use plural `snake_case` table names and singular `snake_case` column names.
- Name primary keys `id`; name foreign keys `<referenced_singular>_id`.
- Name constraints explicitly: `pk_<table>`, `fk_<table>_<column>_<target>`, `uq_<table>_<columns>`, and `ck_<table>_<rule>`. Name indexes `ix_<table>_<columns_or_purpose>`.
- Every foreign key states deletion behavior. Index foreign keys used for reverse lookup; PostgreSQL does not create those indexes automatically.
- Use `created_at`, `updated_at`, and state-specific timestamps such as `archived_at`, not generic `date` fields.
- API/domain terminology is Discovery and Space even if “save” remains a verb.

## Migration order

Use small Alembic revisions with reviewed downgrade behavior:

1. Existing revisions created identity, Discoveries, metadata, Spaces, and optional AI Summaries.
2. Revision `20260805_0007` creates `tags` and all of its named constraints/indexes.
3. The same focused revision creates `discovery_tags`, ownership enforcement, and indexes after both
   parent tables exist.

No backfill is required. Downgrade drops the join/trigger before Tags and must not alter existing
Discoveries or other implemented tables.

## Seed data

No production seed data is required. Registration creates Users; users create their own Spaces and Tags. Tests should use factories/fixtures with clearly synthetic credentials and URLs. Development-only sample data must be opt-in, deterministic, and never part of production migrations.

## Explicit exclusions from the planned Tags revision

Metadata and optional AI Summary tables arrived in their own implemented revisions; the Tags
revision does not change them. It adds no metadata history, generic jobs, visits/counters,
structured intents, connections, rediscovery records, Memory Threads, Insights, extracted
entity/topic tables, automatic or suggested Tags, embeddings, vector indexes, weekly digests,
sharing, collaboration, or graph database. Each later table must arrive with the behavior,
authorization cases, deletion rules, retention policy, and tests that make it useful.
