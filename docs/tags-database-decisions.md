# Tags Database Decisions

These decisions govern the planned Tags MVP. “Final” is the intended first-release contract;
“revisitable” marks an explicit future decision point.

## TAG-ADR-001 — Tags remain separate from Spaces

- **Context:** Both organize Discoveries, but Spaces answer where an item belongs while Tags answer
  what it is about.
- **Decision:** Keep separate Tag and Space entities, memberships, APIs, and UI language.
- **Alternatives:** One typed taxonomy table; Tags as lightweight Spaces; free-form Discovery text.
- **Consequences:** Intent stays clear and each feature can evolve independently, at the cost of
  similar owner-scoped CRUD and membership code.
- **Status:** Final.

## TAG-ADR-002 — Relational `tags` and `discovery_tags`

- **Context:** A Discovery can have many reusable Tags and a Tag can describe many Discoveries.
- **Decision:** Use `tags` for identity/ownership/name and `discovery_tags` for each many-to-many
  assignment.
- **Alternatives:** Tag strings/IDs on Discovery; a generic polymorphic relationship; one Tag per
  Discovery.
- **Consequences:** Referential integrity, cascades, owner indexes, rename without rewriting every
  Discovery, and reliable filtering require a join.
- **Status:** Final.

## TAG-ADR-003 — Application-generated UUIDv4 primary keys

- **Context:** IDs cross API boundaries and current project conventions use application-generated
  UUIDs. Memberships benefit from stable identity and pagination tie-breaking.
- **Decision:** `tags.id` and `discovery_tags.id` are PostgreSQL `uuid` primary keys generated as
  UUIDv4 by the application.
- **Alternatives:** Composite membership primary key; bigint; database-generated UUID; UUIDv7 now.
- **Consequences:** Non-enumerable stable IDs and consistent API/model behavior; larger/random
  indexes than bigint. Pair uniqueness remains a separate constraint. UUIDv7 is project-wide future
  work and does not require rewriting UUIDv4 rows.
- **Status:** Final for this phase; future newly generated UUID version is revisitable project-wide.

## TAG-ADR-004 — Same-owner membership mirrors Spaces

- **Context:** A service defect or direct SQL insert must not attach one User's Tag to another
  User's Discovery.
- **Decision:** Store immutable `user_id` on `discovery_tags`; use a tenant-aware composite FK to
  `tags(user_id, id)` and a narrow PostgreSQL trigger verifying the Discovery owner. Services still
  load both parents with the authenticated owner in one transaction. Foreign/missing resources
  remain indistinguishable.
- **Alternatives:** Application-only checks; trigger for both parents; add `(user_id, id)` uniqueness
  to Discoveries and use two composite FKs; PostgreSQL RLS.
- **Consequences:** Direct inserts are protected and queries lead with tenant ownership without
  changing the existing Discovery schema. The trigger is PostgreSQL-specific and requires live
  PostgreSQL migration tests.
- **Status:** Final, matching the implemented Spaces strategy; RLS remains revisitable defense in
  depth.

## TAG-ADR-005 — NFKC plus Unicode case-fold normalization

- **Context:** Display spellings such as `Python`, `python`, full-width `Ｐｙｔｈｏｎ`, and outer
  whitespace variants should not create duplicate concepts for one User.
- **Decision:** Reject null/control characters; trim outer Unicode whitespace; preserve the result
  as display `name`; compute `normalized_name` as NFKC followed by Unicode default case folding.
  Do not collapse internal whitespace or punctuation. Enforce 1–50 display code points.
- **Alternatives:** Lowercase only; PostgreSQL collation/CITEXT; NFC; internal whitespace collapse.
- **Consequences:** Predictable application-owned cross-platform equivalence while preserving user
  spelling. Unicode runtime behavior needs pinned fixtures and a versioned collision plan for any
  later algorithm change.
- **Status:** Final for normalization v1; versioned changes are revisitable.

## TAG-ADR-006 — Unique normalized names per User

- **Context:** Duplicate names make assignment and filtering ambiguous, but separate Users have
  private independent vocabularies.
- **Decision:** Enforce unique `(user_id, normalized_name)` in PostgreSQL. The service maps the named
  constraint to `409 tag_name_conflict`.
- **Alternatives:** Global uniqueness; duplicates with different IDs; application pre-check only.
- **Consequences:** Concurrent duplicates are impossible within an account, while identical names
  across accounts disclose nothing and remain allowed.
- **Status:** Final.

## TAG-ADR-007 — No persisted Tag color in MVP

- **Context:** Color can aid scanning but adds meaning, contrast, validation, editing, and theme
  concerns.
- **Decision:** Store no color. Use neutral accessible chips and explicit selection/focus styling.
- **Alternatives:** Optional user-selected color; deterministic display color; system assignment.
- **Consequences:** Simpler schema/UI and no inaccessible or misleading color taxonomy. A future
  optional user preference would require accessibility research and a migration.
- **Status:** Final for MVP; user-selected color is revisitable with evidence.

## TAG-ADR-008 — Permanent delete removes memberships only

- **Context:** Tags are lightweight organization and have no archive need, while Discoveries must
  never disappear because organization is removed.
- **Decision:** Deleting an owned Tag permanently removes it and cascades `discovery_tags` only.
  Discoveries, Spaces, metadata, and AI Summaries survive. The deleted name may be recreated with a
  new ID.
- **Alternatives:** Soft delete/archive; prevent deletion while in use; delete Discoveries.
- **Consequences:** Simple honest deletion and immediate name reuse; no undo beyond the UI
  confirmation and backup-retention policy.
- **Status:** Final.

## TAG-ADR-009 — One Tag filter in the first release

- **Context:** Multiple selections require an explicit AND/OR model and more complex UI/state.
- **Decision:** Permit one active Tag filter. It combines with Space, platform, favourite, archive,
  and keyword filters using AND; selecting another Tag replaces it.
- **Alternatives:** Multi-Tag AND; multi-Tag OR; user-selectable boolean logic.
- **Consequences:** Predictable first-release behavior and simpler URLs. Multi-Tag filtering can be
  added without schema change after observed demand.
- **Status:** Final for MVP; multi-Tag semantics are revisitable.

## TAG-ADR-010 — Nested Tags postponed

- **Context:** Hierarchy introduces cycles, inherited filtering, navigation, deletion, and rename
  semantics not needed for lightweight subjects.
- **Decision:** Tags are flat. Add no parent key or closure/path table.
- **Alternatives:** Adjacency list; materialized path; nested-set model.
- **Consequences:** Simple mental model and queries; users cannot encode hierarchy in the product.
- **Status:** Final for MVP; hierarchy requires separate product evidence and design.

## TAG-ADR-011 — Tag aliases and merge postponed

- **Context:** Aliases/merge could reconcile evolving vocabularies but introduce canonical identity,
  redirects, auditability, concurrency, and conflict behavior.
- **Decision:** Each Tag has one display name. No alias table, redirect, or merge workflow.
- **Alternatives:** Alias strings on Tag; alias table; automatic merge on duplicate rename.
- **Consequences:** Rename remains simple and duplicates conflict rather than silently merging.
- **Status:** Final for MVP; aliases and explicit merge are revisitable together.

## TAG-ADR-012 — Relational memberships, not JSONB

- **Context:** Membership is queried in both directions, filtered, authorized, constrained, and
  cascaded.
- **Decision:** Use relational `discovery_tags`; JSONB must not represent membership.
- **Alternatives:** JSONB array on Discovery or Tag; PostgreSQL UUID array.
- **Consequences:** Foreign keys, pair uniqueness, owner enforcement, indexes, and cascade behavior
  are database-enforced. Reads require joins.
- **Status:** Final.

## TAG-ADR-013 — Bounded Tag summaries in Discovery responses

- **Context:** Cards/detail/edit controls need Tag identity and display names; per-card follow-up
  calls cause N+1 traffic.
- **Decision:** Nest sorted `{id, name}` summaries in Discovery list and detail responses. Never
  expose owner or normalized name. Fetch them in a batched/aggregated query.
- **Alternatives:** Separate request per Discovery; IDs only; full Tag objects with counts/times.
- **Consequences:** Simple rendering and filtering with bounded payload growth. Discovery response
  schemas gain an additive `tags` array.
- **Status:** Final for MVP; projection shape is revisitable only through compatible API evolution.

## TAG-ADR-014 — Bound Tags per User and per Discovery

- **Context:** Unbounded private vocabularies and memberships can amplify queries, payloads, and
  abusive writes.
- **Decision:** Start with 500 Tags per User and 20 Tags per Discovery, enforced transactionally in
  the service and covered by PostgreSQL concurrency tests.
- **Alternatives:** No caps; much smaller caps; database triggers/counter columns.
- **Consequences:** Predictable card payloads and portfolio-scale operations without counter schema.
  Exact caps should be confirmed before coding and can be raised without migration.
- **Status:** Revisitable product limits; boundedness is final.

## TAG-ADR-015 — Future AI suggestions do not own or mutate Tags

- **Context:** Later AI may propose subjects, but user Tags are private authored organization and
  silent model writes would confuse provenance.
- **Decision:** The current schema remains the authoritative human Tag vocabulary. A later
  suggestion feature may propose an existing owned Tag ID or candidate text, but it cannot create,
  attach, rename, or delete a Tag without explicit user confirmation.
- **Alternatives:** Let the model automatically reuse/create user Tags; seed global Tags; treat AI
  topics as Tags.
- **Consequences:** Stable user control and future compatibility without speculative columns. A
  separate inferred-data design is needed if suggestions must be persisted.
- **Status:** Final boundary; suggestion UX/storage is future.

## TAG-ADR-016 — Automatic Tags remain separate inferred data

- **Context:** A future automatic classification has provenance, confidence, model version,
  consent, staleness, and deletion needs that user Tags do not.
- **Decision:** If automatic Tags are ever approved, store them as separate inferred suggestions or
  assignments with provenance; do not masquerade them as rows/memberships authored by the User.
  Explicit acceptance may create/reuse an ordinary owned Tag and membership.
- **Alternatives:** Reuse `discovery_tags` with an origin flag; silently create ordinary Tags;
  global inferred taxonomy.
- **Consequences:** User-authored truth stays clear and removable AI data can follow its own
  lifecycle. No inferred table or origin column is added now.
- **Status:** Final provenance principle; the automatic feature itself is postponed.
