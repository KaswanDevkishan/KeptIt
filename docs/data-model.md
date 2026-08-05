# KeptIt Data Model

## Scope and principles

KeptIt's core record is a **Discovery**: a private record that a user chose to preserve from the internet, including both source facts and the user's context. A **Space** is a user-visible collection. A future **Memory Thread** groups related Discoveries for memory and rediscovery experiences.

The model separates four kinds of data so provenance and deletion policy remain clear:

| Data class | Examples | Authority |
| --- | --- | --- |
| User-authored | custom title, note, save reason, intent, importance, Spaces, Tags, feedback | The user; never overwritten by enrichment |
| Externally fetched | source title, description, thumbnail, creator, publication time | An external source, recorded with provenance and fetch time |
| Inferred | normalized platform, summaries, topics, connections, threads, insights | Deterministic code or a versioned algorithm/model |
| Operational and security | sessions, jobs, audit events | The service; access is restricted and retention is bounded |

Release labels below mean **MVP** (the first production-worthy product schema), **near-term** (after saving works), and **future** (documented only until a demonstrated feature needs it). The next authentication sprint should create only `users` and `user_sessions`; the rest of the MVP schema belongs to the following Discovery sprint.

## Identity and access

### User (`users`) — MVP

- **Purpose:** Account identity and ownership root for all private data.
- **Important fields:** `id`, normalized `email`, `password_hash`, `is_active`, `created_at`, `updated_at`. Email and password hash are security data.
- **Primary key:** Application-generated UUID (`uuid`, UUIDv7 preferred when library support is mature; UUIDv4 is acceptable initially).
- **Foreign keys:** None.
- **Unique constraints:** Case-insensitive normalized email.
- **Indexes:** Unique email index; optional operational index on active accounts only if a query requires it.
- **Deletion:** Account deletion starts a controlled purge. Sessions are revoked immediately; owned product data is permanently deleted after any recovery window; audit records are anonymized or retained only where justified.

### UserSession (`user_sessions`) — MVP

- **Purpose:** Revocable browser authentication without exposing a long-lived bearer credential to JavaScript. This is preferred over stateless access/refresh JWTs for the first-party web application.
- **Important fields:** `id`, `user_id`, `token_hash`, `created_at`, `expires_at`, `last_seen_at`, `revoked_at`; optionally bounded `user_agent` and coarse IP-derived security metadata if a written need and retention period exist. Store only a cryptographic token hash, never the cookie value.
- **Primary key:** UUID.
- **Foreign keys:** `user_id -> users.id`.
- **Unique constraints:** `token_hash`.
- **Indexes:** Unique token hash; `(user_id, expires_at)` for session management; expiry index for cleanup.
- **Deletion:** Cascade on user deletion. Logout may revoke first, then a cleanup job permanently deletes expired/revoked rows after a short security window.

## Core memory and organization

### Discovery (`discoveries`) — MVP

- **Purpose:** The user's durable memory of an internet discovery and the ownership boundary for its dependent records.
- **Important fields:** `id`, `user_id`, `original_url`, `canonical_url`, `canonical_url_hash`, `normalization_version`, inferred `platform`, user-authored `custom_title`, `personal_note`, `save_reason`, `importance`, `is_favourite`, `archived_at`, `created_at`, `updated_at`. `created_at` is save time. Source title and other fetched metadata do not belong here.
- **Primary key:** UUID.
- **Foreign keys:** `user_id -> users.id`.
- **Unique constraints:** `(user_id, canonical_url_hash)`, with collision-safe application comparison of `canonical_url` before declaring a duplicate.
- **Indexes:** `(user_id, archived_at, created_at DESC, id DESC)` for library pagination; `(user_id, platform, created_at DESC)`; unique duplicate index. Add search indexes only with the search feature.
- **Deletion:** Archive is reversible state, not deletion. Explicit permanent deletion cascades through joins and dependent private data; operational audit data must not retain private content.

### Space (`spaces`) — MVP

- **Purpose:** A user-created, user-visible collection that can contain many Discoveries.
- **Important fields:** `id`, `user_id`, `name`, optional `description`, `created_at`, `updated_at`.
- **Primary key:** UUID.
- **Foreign keys:** `user_id -> users.id`.
- **Unique constraints:** Case-insensitive `(user_id, normalized_name)`.
- **Indexes:** `(user_id, normalized_name)` unique; `(user_id, created_at)` if listing requires it.
- **Deletion:** Deleting a Space deletes memberships, not Discoveries. User deletion cascades.

### SpaceMembership (`space_memberships`) — MVP

- **Purpose:** Many-to-many assignment of Discoveries to Spaces. “Membership” here means Discovery-to-Space membership, not user collaboration.
- **Important fields:** UUID `id`, immutable tenant `user_id`, `discovery_id`, `space_id`, and `created_at`; optional future user-defined ordering.
- **Primary key:** UUID `id`.
- **Foreign keys:** `user_id -> users.id`; tenant-aware `(user_id, space_id) -> spaces(user_id, id)`; and `discovery_id -> discoveries.id`. An ownership trigger verifies that the Discovery owner equals `user_id` without changing the Discovery schema.
- **Unique constraints:** `(space_id, discovery_id)` prevents duplicate assignment; supporting `(user_id, id)` uniqueness exists on Spaces for its composite foreign key.
- **Indexes:** Owner-led Space contents `(user_id, space_id, created_at DESC, id DESC)` and reverse Discovery lookup `(user_id, discovery_id, space_id)`.
- **Deletion:** Cascade when either parent is deleted. The Space composite foreign key and Discovery-owner trigger make cross-owner assignment impossible in the database; tenant-scoped service writes remain mandatory.

The complete normative schema, API, behavior, security, migration, UX, and test design is in the
[Spaces feature implementation plan](spaces-implementation-plan.md).

### Tag (`tags`) — MVP

- **Purpose:** Lightweight user-owned labels for cross-cutting description and retrieval.
- **Important fields:** `id`, `user_id`, `name`, `normalized_name`, `created_at`, `updated_at`.
- **Primary key:** UUID.
- **Foreign keys:** `user_id -> users.id`.
- **Unique constraints:** `(user_id, normalized_name)`.
- **Indexes:** The unique owner/name index.
- **Deletion:** Deleting a Tag deletes assignments, not Discoveries. User deletion cascades.

### DiscoveryTag (`discovery_tags`) — MVP

- **Purpose:** Many-to-many assignment of Tags to Discoveries.
- **Important fields:** `discovery_id`, `tag_id`, `created_at`.
- **Primary key:** Composite `(discovery_id, tag_id)`.
- **Foreign keys:** `discovery_id -> discoveries.id`, `tag_id -> tags.id`.
- **Unique constraints:** The composite primary key.
- **Indexes:** Reverse index `(tag_id, discovery_id)`.
- **Deletion:** Cascade with either parent. As with Space membership, owner equality is enforced by scoped service operations and authorization tests.

### DiscoveryIntent (`discovery_intents`) — near-term, documented only

- **Purpose:** Structured, potentially multiple intentions such as `read`, `watch`, `try`, `research`, or `share_privately`, while retaining the user's free-form reason on Discovery.
- **Important fields:** `id`, `discovery_id`, `kind`, optional user-authored `detail`, `status`, `created_at`, `completed_at`.
- **Primary key:** UUID.
- **Foreign keys:** `discovery_id -> discoveries.id`.
- **Unique constraints:** Consider `(discovery_id, kind)` only if product behavior prohibits repeated intent kinds.
- **Indexes:** `(discovery_id, status)` and, only for owner-filtered intent views, a denormalized `user_id` or join-based query index after measurement.
- **Deletion:** Cascade with Discovery. MVP uses nullable `discoveries.save_reason` rather than prematurely fixing an intent taxonomy.

## Source metadata and processing

### MetadataRecord (`metadata_records`) — near-term

- **Purpose:** Current permitted source facts, separate from the user's authorship and replaceable by later fetches. Start with one current record per Discovery; introduce immutable snapshots only if history becomes useful.
- **Important fields:** `id`, `discovery_id`, `source_title`, `description`, `thumbnail_url`, `creator_name`, `publisher_name`, `published_at`, `resolved_canonical_url`, `provider`, `provider_record_id`, `fetched_at`, `expires_at`, `status`, optional bounded `raw_metadata`.
- **Primary key:** UUID.
- **Foreign keys:** `discovery_id -> discoveries.id`.
- **Unique constraints:** `discovery_id` for the current-record design.
- **Indexes:** Unique Discovery lookup; optional `(provider, provider_record_id)` when provider refresh requires it; expiry index for refresh selection.
- **Deletion:** Cascade with Discovery. Replace or clear data when a source withdraws it or retention/terms require removal. Raw payload storage is discouraged.

### EnrichmentJob (`enrichment_jobs`) — near-term

- **Purpose:** Bounded, observable processing for metadata and later derived enrichments without blocking a Discovery save.
- **Important fields:** `id`, `discovery_id`, `job_type`, `status`, `attempt_count`, `available_at`, `started_at`, `finished_at`, `lease_expires_at`, safe `error_code`, `created_at`, `updated_at`.
- **Primary key:** UUID.
- **Foreign keys:** `discovery_id -> discoveries.id`.
- **Unique constraints:** A partial uniqueness rule may prevent more than one active job per `(discovery_id, job_type)`.
- **Indexes:** Partial queue index `(available_at, created_at)` for runnable states; `(discovery_id, job_type, created_at DESC)`.
- **Deletion:** Cascade with Discovery; completed jobs are permanently removed after a short operational retention period. Do not store third-party bodies or private notes in errors.

## Memory behaviour

### DiscoveryVisit (`discovery_visits`) — near-term

- **Purpose:** Append-only history that a user opened or revisited a Discovery through KeptIt.
- **Important fields:** `id`, `discovery_id`, `visited_at`, `visit_kind`, optional privacy-safe `surface` (library, search, digest). Do not store destination query strings or detailed browsing telemetry.
- **Primary key:** UUID.
- **Foreign keys:** `discovery_id -> discoveries.id`.
- **Unique constraints:** None; optional idempotency key if client retries create duplicates.
- **Indexes:** `(discovery_id, visited_at DESC)`; time index for retention cleanup. A cached counter can be added to Discovery only after measured need.
- **Deletion:** Cascade with Discovery and age out under an explicit retention policy.

### DiscoveryConnection (`discovery_connections`) — future

- **Purpose:** Directed or undirected relationship between two Discoveries, either authored by a user or inferred.
- **Important fields:** `id`, `user_id`, `source_discovery_id`, `target_discovery_id`, `connection_type`, `provenance`, optional `confidence`, `algorithm_version`, user-authored `note`, `created_at`.
- **Primary key:** UUID.
- **Foreign keys:** Both Discovery IDs to `discoveries.id`; `user_id -> users.id` makes tenant filtering explicit.
- **Unique constraints:** A normalized endpoint/type uniqueness rule once direction semantics are defined; check that endpoints differ.
- **Indexes:** `(user_id, source_discovery_id)`, `(user_id, target_discovery_id)`, and type as queries demand.
- **Deletion:** Cascade if either Discovery is deleted. Both endpoints must belong to `user_id`; inferred connections can be regenerated.

### RediscoveryEvent (`rediscovery_events`) — future

- **Purpose:** Record that KeptIt selected and presented a Discovery for rediscovery, supporting eligibility, frequency control, and evaluation.
- **Important fields:** `id`, `user_id`, `discovery_id`, optional `memory_thread_id`, `surface`, `reason_code`, `algorithm_version`, `presented_at`, optional `opened_at`, `dismissed_at`.
- **Primary key:** UUID.
- **Foreign keys:** `user_id`, `discovery_id`, optional Memory Thread.
- **Unique constraints:** Optional idempotency key per delivery, not a blanket Discovery uniqueness rule.
- **Indexes:** `(user_id, presented_at DESC)`, `(discovery_id, presented_at DESC)`, and eligibility-oriented recent-event indexes after the algorithm is known.
- **Deletion:** Cascade with Discovery/user; retain only as long as needed for the feature and evaluation.

### RediscoveryFeedback (`rediscovery_feedback`) — future

- **Purpose:** Explicit private feedback on a rediscovery recommendation.
- **Important fields:** `id`, `rediscovery_event_id`, `user_id`, `rating` or bounded `action`, optional `reason_code`, optional user-authored `comment`, `created_at`, `updated_at`.
- **Primary key:** UUID.
- **Foreign keys:** Event and User.
- **Unique constraints:** One current feedback record per `(rediscovery_event_id, user_id)` unless multiple actions are intentionally modeled.
- **Indexes:** Unique event/user; `(user_id, created_at DESC)`.
- **Deletion:** Cascade with event/user. Comments follow the stricter retention rules for private notes.

## Future intelligence

### MemoryThread (`memory_threads`) — future

- **Purpose:** A future grouping of related Discoveries, generated by an algorithm or deliberately curated by the user.
- **Important fields:** `id`, `user_id`, `title`, optional `description`, `provenance`, `status`, `algorithm_version`, `created_at`, `updated_at`.
- **Primary key:** UUID.
- **Foreign keys:** `user_id -> users.id`.
- **Unique constraints:** No title uniqueness; generated reruns may use an idempotency key.
- **Indexes:** `(user_id, status, updated_at DESC)`.
- **Deletion:** Deleting a Memory Thread deletes memberships and dependent generated insights, never its Discoveries.

### MemoryThreadMembership (`memory_thread_memberships`) — future

- **Purpose:** Many-to-many membership of Discoveries in Memory Threads with explainability and ordering.
- **Important fields:** `memory_thread_id`, `discovery_id`, `position`, optional `relevance_score`, `reason`, `created_at`.
- **Primary key:** Composite `(memory_thread_id, discovery_id)`.
- **Foreign keys:** Memory Thread and Discovery.
- **Unique constraints:** Composite key; optional `(memory_thread_id, position)` when positions are strict.
- **Indexes:** Reverse `(discovery_id, memory_thread_id)`.
- **Deletion:** Cascade with either parent. Both parents must share an owner.

### Insight (`insights`) — future

- **Purpose:** A generated, versioned observation grounded in one Discovery, a Memory Thread, or a digest period.
- **Important fields:** `id`, `user_id`, optional `discovery_id`, optional `memory_thread_id`, `insight_type`, `content`, `provenance`, `model`, `model_version`, `prompt_version`, `status`, `created_at`, `superseded_at`.
- **Primary key:** UUID.
- **Foreign keys:** User and nullable subject keys; a check constraint requires at least one defined subject strategy.
- **Unique constraints:** Optional generation idempotency key.
- **Indexes:** `(user_id, status, created_at DESC)` and subject lookups.
- **Deletion:** Cascade or purge with its source; derived content is private and cannot outlive all grounding sources. Superseded versions have bounded retention.

Embeddings and extracted entities/topics should eventually use purpose-built, versioned records associated with a Discovery or Metadata Record, not columns added now. Their exact schema depends on retrieval and provenance requirements.

## Operational accountability

### AuditEvent (`audit_events`) — near-term security subset; future product actions

- **Purpose:** Append-only evidence of security-sensitive actions such as login, logout, credential changes, account deletion, administrative access, and later high-value data operations.
- **Important fields:** `id`, nullable `actor_user_id`, `event_type`, `occurred_at`, `request_id`, `outcome`, privacy-safe `subject_type` and `subject_id`, optional bounded structured details. Never include passwords, tokens, notes, URLs, or generated private content.
- **Primary key:** UUID or time-ordered `bigint`; UUID keeps conventions consistent and is recommended initially.
- **Foreign keys:** Actor may use `ON DELETE SET NULL`; subject identifiers are deliberately not broad polymorphic foreign keys.
- **Unique constraints:** Optional request/event idempotency key.
- **Indexes:** `(actor_user_id, occurred_at DESC)`, `(event_type, occurred_at DESC)`, retention/partition key on `occurred_at` if volume later warrants it.
- **Deletion:** Append-only to the application. Retain for a defined security period, restrict access, and anonymize actor linkage after account deletion where possible.

## Recommended implementation sequence

1. **Authentication sprint:** `users`, then `user_sessions`. Add only the security audit events that have a concrete incident-response requirement; otherwise keep application logs until the audit boundary is agreed.
2. **Discovery sprint:** `discoveries`, `spaces`, `space_memberships`, `tags`, `discovery_tags`.
3. **Safe enrichment:** `metadata_records`, then `enrichment_jobs` when asynchronous processing is actually introduced.
4. **Memory behaviour:** introduce visits and rediscovery records only with their product experiences and retention controls.
5. **Future intelligence:** introduce connections, Memory Threads, insights, entities/topics, and embeddings only with evaluation criteria, provenance, deletion, and provider-disclosure policies.

This sequence preserves clean expansion points without making empty future tables part of the MVP.
