# Tags: Production Implementation Plan

## Status, assumptions, and product goal

This document is the normative design implemented by revision `20260805_0007` and its associated
backend and frontend feature code.
The design assumes the existing authentication, Discoveries, metadata enrichment, Spaces, optional
AI Summaries, trusted-origin policy, error envelope, and UUID conventions remain unchanged.

A Space answers **“Where does this Discovery belong?”** A Tag answers **“What is this Discovery
about?”** Spaces are navigable collections such as “University” or “Japan Trip”; Tags are compact,
cross-cutting descriptors such as “python”, “recipe”, or “read-later”. A Discovery can therefore
belong to a project Space while carrying several subjects that remain useful across every Space.

Tags are user-created and user-controlled in the first release. This keeps organization
predictable, avoids silently classifying private libraries, and establishes an explicit vocabulary
before any later suggestion system is considered. Stable Tag identities and relational
memberships can later be inputs to separately designed semantic search or AI suggestions, but this
phase adds no AI-generated Tags, suggestions, embeddings, vectors, or semantic behavior.

## MVP scope

An authenticated user can:

- create, list, read, rename, and permanently delete their own Tags;
- search the Tag list by display name and sort it alphabetically;
- assign one or more owned Tags to an owned Discovery and remove assignments;
- create a Tag from the Discovery assignment control and explicitly assign it;
- see compact Tag chips on Discovery cards and detail/edit views;
- filter the library by one Tag while combining existing filters;
- assign Tags to active or archived Discoveries without changing archive state.

The MVP explicitly excludes automatic or suggested Tags, nested Tags, shared/public/global Tags,
global taxonomies, aliases, merge workflows, semantic similarity, color intelligence, bulk tagging,
sharing, collaboration, and browser extensions. Bulk tagging has no compelling first-release need:
it adds selection, partial-failure, authorization, and lost-update complexity before ordinary Tag
use is validated.

## Domain terminology

- **Tag:** a private, user-authored, owner-scoped descriptor reusable across Discoveries.
- **DiscoveryTag / TagMembership:** one relational assignment of one Tag to one Discovery. The
  persistence table is `discovery_tags`; API and UI copy use “Tag assignment”, not “label”.
- **Tag display name:** the accepted, trimmed spelling returned to the user, such as `Python`.
- **Normalized Tag name:** the server-computed comparison key used only for per-user uniqueness.
- **User ownership:** every Tag has exactly one User; a membership can connect only parents owned by
  that same User. Authentication establishes identity and owner-scoped queries authorize access.
- **Tag filtering:** selecting a Tag to show owned Discoveries assigned to it, subject to the other
  active library filters.

Tags do not contain Discoveries in the product-language sense used for Spaces. They describe what a
Discovery is about and can cut across every Space.

## Database schema

All IDs are application-generated UUIDv4 values stored as PostgreSQL `uuid`. All instants are UTC
`timestamptz`. Clients never supply IDs for newly created rows, ownership keys, normalized names,
or timestamps. Alembic owns the eventual schema change.

### `tags`

| Field | PostgreSQL type | Null/default | Purpose | Constraints and indexes |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; application-generated UUIDv4 | Stable Tag identity | `pk_tags`; supporting unique `(user_id, id)` |
| `user_id` | `uuid` | not null; no default | Immutable owner/tenant key | FK `users.id ON DELETE CASCADE`; leads every private index |
| `name` | `varchar(50)` | not null; no default | Preserved trimmed display name | 1–50 Unicode code points; non-empty check |
| `normalized_name` | `text` | not null; no default | Server-derived uniqueness/sort key; never exposed | non-empty check; unique `(user_id, normalized_name)` |
| `created_at` | `timestamptz` | not null; current transaction time | Creation time | immutable after insert |
| `updated_at` | `timestamptz` | not null; current transaction time | Last display-name change | advances only on effective rename |

Named constraints and indexes:

- `fk_tags_user_id_users`: `user_id -> users.id ON DELETE CASCADE`.
- `uq_tags_user_id_normalized_name`: unique `(user_id, normalized_name)`, authoritative for races.
- `uq_tags_user_id_id`: unique `(user_id, id)`, supporting tenant-aware foreign keys.
- `ck_tags_name_nonempty` and `ck_tags_normalized_name_nonempty`.
- `ix_tags_user_normalized_name_id` on `(user_id, normalized_name, id)` for stable alphabetical
  owner listing. The unique index can satisfy much of this query; retain this covering order only
  if PostgreSQL plans show the appended `id` is useful for keyset pagination.

No color column is included. `text` is intentional because NFKC and case folding can expand a
value beyond the 50-code-point display limit; the normalized value is still bounded indirectly by
that input limit and never accepts arbitrary client input.

### `discovery_tags`

| Field | PostgreSQL type | Null/default | Purpose | Constraints and indexes |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; application-generated UUIDv4 | Stable membership identity and pagination tie-breaker | `pk_discovery_tags` |
| `user_id` | `uuid` | not null; no default | Immutable denormalized tenant key | FK `users.id ON DELETE CASCADE`; never client supplied |
| `tag_id` | `uuid` | not null; no default | Assigned Tag | tenant-aware FK `(user_id, tag_id)` to `tags(user_id, id) ON DELETE CASCADE` |
| `discovery_id` | `uuid` | not null; no default | Assigned Discovery | FK `discoveries.id ON DELETE CASCADE`; same-owner trigger |
| `created_at` | `timestamptz` | not null; current transaction time | Assignment time | unchanged by duplicate attach |

Named constraints and indexes:

- `fk_discovery_tags_user_id_users` with `ON DELETE CASCADE`.
- `fk_discovery_tags_user_tag` from `(user_id, tag_id)` to `tags(user_id, id)` with cascade.
- `fk_discovery_tags_discovery_id_discoveries` with cascade.
- `uq_discovery_tags_tag_id_discovery_id` on `(tag_id, discovery_id)` for pair uniqueness.
- `ix_discovery_tags_user_discovery_tag` on `(user_id, discovery_id, tag_id)` for listing Tags on
  a Discovery and loading card/detail summaries.
- `ix_discovery_tags_user_tag_created_id` on
  `(user_id, tag_id, created_at DESC, id DESC)` for Tag contents and filtered pagination.
- A `BEFORE INSERT OR UPDATE OF user_id, discovery_id` trigger verifies that the referenced
  Discovery exists and its `user_id` equals `NEW.user_id`.

The owner-led Tag index supports listing Discoveries for a Tag and filtering the user's library.
The reverse owner/Discovery index supports listing Tags for a Discovery and batched summary loads.
Deleting a Tag deletes only its memberships. Deleting a Discovery deletes its memberships. Account
deletion cascades Tags and memberships. No operation on these tables deletes a Discovery because a
Tag was deleted.

## Same-owner enforcement

The selected approach mirrors the current Spaces implementation:

1. Every service loads the Tag and Discovery with `(user_id, id)` predicates in the same
   transaction and derives `discovery_tags.user_id` from the authenticated caller.
2. `discovery_tags.user_id` is immutable tenant denormalization.
3. A composite foreign key proves the Tag belongs to that tenant.
4. A narrow trigger proves the existing Discovery belongs to the same tenant without altering the
   already implemented `discoveries` table.

Comparison:

| Approach | Strengths | Weaknesses | Decision |
| --- | --- | --- | --- |
| Denormalized `user_id` | owner-leading queries, explicit tenant key | alone does not prove parent ownership | Use as the enforcement anchor |
| Composite FKs to both parents | declarative and strong | would require new `(user_id, id)` uniqueness on Discoveries | Use for Tag only, matching Spaces |
| PostgreSQL trigger | protects direct inserts without changing Discovery | PostgreSQL-specific and needs direct tests | Use narrowly for Discovery ownership |
| Application-only checks | portable, good safe-error control | service bugs/direct inserts can cross tenants | Required, but insufficient alone |

The trigger must raise a stable integrity condition that the service maps without parsing database
text. Direct cross-tenant inserts fail in PostgreSQL. API lookups still return the identical
`404 resource_not_found` for absent and foreign parents, so database defense never becomes an
ownership oracle.

## Name normalization

Normalization version 1 is an application-domain contract:

1. Require a string and reject a null byte or any Unicode control character (`Cc`).
2. Trim leading and trailing Unicode whitespace.
3. Reject an empty result; enforce 1–50 Unicode code points on this display value.
4. Preserve that trimmed value as `name`.
5. Apply Unicode NFKC to the display value.
6. Apply Unicode default case folding.
7. Do **not** collapse, remove, or reinterpret internal whitespace or punctuation.
8. Reject an empty normalized result and enforce the database storage bound.

The backend owns normalization; clients may preview it but cannot submit `normalized_name`.
Shared fixtures pin the runtime's Unicode behavior, and any semantic change requires a versioned
collision review rather than silently rewriting stored values.

`Python`, `python`, `Ｐｙｔｈｏｎ`, and ` python ` all normalize to `python` and conflict for one User.
Different Users may independently create any of those display forms. Keeping `name` separate
preserves the accepted spelling while normalized equality remains predictable.

Internal whitespace is not collapsed: `machine learning` and `machine  learning` remain distinct.
This avoids silently changing intentional names; the UI may help users notice repeated whitespace.

## Duplicate behavior

- Creating a per-user normalized duplicate returns `409 tag_name_conflict` with a safe `name`
  field detail. A pre-check improves UX, but the named unique constraint resolves races.
- Renaming to another owned Tag's normalized name returns the same conflict and rolls back.
- A rename that changes only this Tag's display spelling/case succeeds and preserves its ID and
  memberships.
- The same normalized name is allowed for different Users.
- Unicode/case equivalents follow the normalization contract, not database collation.
- `PUT` attachment is idempotent: first creation returns `201`; an existing exact pair returns
  `200` with its existing membership and unchanged `created_at`.
- Concurrent duplicate attachments converge on one row through the unique pair constraint.

## Rename and deletion semantics

Rename updates `name`, `normalized_name`, and `updated_at` atomically. It never changes the Tag ID,
owner, memberships, Discovery records, or URLs. Equal stored values are a successful no-op and do
not advance `updated_at`. Concurrent renames are last-write-wins when both are unique; a competing
duplicate is mapped from the named constraint to `409`. Conditional requests/ETags are postponed
unless real multi-device overwrites justify them.

Delete is permanent in the live database and requires clear UI confirmation. It cascades only
`discovery_tags`; Discoveries, Spaces, metadata, and AI Summaries remain unchanged. After deletion,
an active Tag filter is cleared and the user returns to the unfiltered library. An already open
assignment menu or settings view refetches; a stale action receives safe `404` and removes the Tag
from local state. Once the transaction commits, the same name may be recreated as a new Tag with a
new UUID. Backups expire under the documented retention policy rather than being selectively
rewritten.

## API design

The precise normative contract is [Tags API Contract](tags-api-contract.md). All routes are under
`/api/v1`, require the existing session cookie, return private `Cache-Control: no-store` responses,
and apply trusted-origin protection to mutations.

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /tags` | Search/list owned Tags | `200` paginated collection |
| `POST /tags` | Create Tag | `201` plus `Location` |
| `GET /tags/{tag_id}` | Read owned Tag | `200` |
| `PATCH /tags/{tag_id}` | Rename owned Tag | `200` |
| `DELETE /tags/{tag_id}` | Permanently delete owned Tag | `204` |
| `PUT /tags/{tag_id}/discoveries/{discovery_id}` | Idempotently attach | `201` created or `200` existing |
| `DELETE /tags/{tag_id}/discoveries/{discovery_id}` | Detach | `204` |
| `GET /tags/{tag_id}/discoveries` | List assigned Discoveries | `200` paginated collection |

Tag-oriented pair routes match the existing Spaces API. Discovery responses provide the reverse
view, so a separate Discovery-oriented mutation surface would duplicate semantics and is omitted.
If a future bounded atomic replacement endpoint is justified, it should be
`PUT /discoveries/{id}/tags` with explicit set-replacement and concurrency rules; it is not MVP.

`GET /tags` accepts `limit` (default 50, 1–100), opaque `cursor`, optional trimmed `q` (1–50 code
points), and `sort=name_asc|updated_desc` (default `name_asc`). Search is owner-scoped substring
matching over `normalized_name`; escaped `ILIKE` is adequate for bounded Tag counts, with no new
extension. List results include `discovery_count` across active and archived Discoveries.

`GET /tags/{id}/discoveries` accepts the existing library filters and pagination contract plus
`archive=active|archived|all`; default is active. Ownership is applied before every join/filter.
Malformed UUIDs/queries are `422`; absent and foreign valid resources are identical `404`; name
conflicts are `409`. Unknown request fields are rejected.

Discovery list and detail responses nest bounded Tag summaries:

```json
"tags": [
  {"id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "name": "Python"}
]
```

The array is sorted by normalized name then ID and capped by the maximum Tags per Discovery, so no
extra count/truncation contract is needed. It exposes neither `user_id` nor `normalized_name`.

## Discovery integration

- **Create/save:** after the core Discovery save succeeds, the UI may assign selected existing or
  newly created Tags. Discovery persistence must not depend on Tag requests. Partial assignment
  failure leaves the saved Discovery intact and offers retry.
- **Edit/detail:** an accessible multi-select shows authoritative owned Tags, permits explicit
  create-then-assign, and sends bounded idempotent pair mutations.
- **Cards/list/search:** render the nested sorted summaries as compact chips. Long lists wrap to a
  second line and then use a disclosure such as “+3”, while the data remains accessible.
- **Filters:** one active Tag ID is represented in library state/query parameters. A deleted or
  foreign Tag produces safe not-found handling and clears stale client state.
- **Archived Discoveries:** retain and display memberships; archived filtering controls visibility.

Tags do not change Discovery URL identity, duplicate detection, metadata, AI Summary generation or
staleness, Space membership, favourite state, or archive semantics. User Tags are not AI Summary
topics, and neither is automatically converted into the other.

## Frontend UX

Add a compact **Tags** section within the authenticated app shell near, but visually distinct from,
**Spaces**. The primary library remains the focus; management controls live in a Tags view or
popover rather than on every card.

- The Tag list has loading, error, empty, search, pagination, and alphabetical states. Empty copy
  explains that Tags describe subjects across Spaces.
- **New Tag** opens a labelled single-field dialog with length guidance. Creation from the
  assignment multi-select selects and assigns the new Tag only after successful creation.
- Rename preserves input and focuses the server error on conflict. Delete confirmation names the
  Tag and states that Discoveries remain.
- Chips on cards are buttons only when they activate filtering; otherwise use noninteractive text.
  Do not place rename/delete controls on cards.
- Multi-select uses a keyboard-operable combobox/listbox or checklist with visible focus, clear
  selected state, escape/close behavior, and screen-reader announcements.
- Desktop uses the app shell/sidebar without crowding Spaces. Mobile uses a filter sheet and a
  full-width assignment sheet/dialog with reachable touch targets.
- Long names wrap or ellipsize only when the full name is available via accessible text; never
  shrink text below readable size.
- Optimistically attach/detach only when rollback and an accessible failure announcement are
  implemented. Create, rename, and delete wait for authoritative success.
- An empty filtered library says no Discoveries match the active Tag and offers **Clear Tag
  filter**, not **Create Discovery** as the only recovery.

## Tag color decision

Color is postponed. User-selected colors require validation, contrast handling, editing controls,
and meaning that has not been validated. Persisted system-assigned colors create data without user
intent. Deterministic display colors can change with themes and may imply unsupported categories.
Neutral chips with strong typography and selected/focus states are sufficient for MVP. A future
optional color field requires accessibility rules and evidence that it improves scanning.

## Search and filtering

The first release supports exactly one Tag filter. Multiple-Tag AND/OR controls are postponed to
avoid ambiguous chips and empty-result surprises. The Tag filter combines with existing criteria
using AND:

```text
owned AND archive-state AND tag AND optional-space AND optional-platform
      AND optional-favourite AND optional-keyword
```

Only the Tag dimension is single-select; other existing filters retain their current semantics.
Selecting a second Tag replaces the first. A Tag filter works with a Space filter, allowing
cross-Space browsing when no Space is selected and focused browsing when one is. Search results
show the same Tag summaries. Default archive behavior remains active-only; choosing archived/all
does not alter memberships.

## Security and privacy

- Every Tag and membership path is authenticated and owner-scoped before filtering or aggregation.
- The application checks both parents; composite FK plus trigger rejects cross-user direct inserts.
- Foreign and absent Tags/Discoveries have the same status, code, body shape, and no private detail.
- Tag endpoints are private and non-cacheable; there is no public enumeration or autocomplete.
- Mutations retain secure cookies, narrow CORS, trusted-origin/CSRF protection, parameterized SQL,
  strict JSON content types, unknown-field rejection, request-size limits, and output escaping.
- Tag names are private user-authored data. Do not include them in logs, metrics labels, audit
  detail, analytics, exception reports, or provider input. Log route templates and safe codes.
- Apply per-user and IP-aware production rate limits to create/rename/delete and membership
  mutations. Bound list sizes, Tag counts, assignments, and request bodies.
- Account deletion cascades Tags and memberships. Tag deletion is permanent in live storage and
  backup copies age out under the disclosed schedule.

## Concurrency and transactions

- Create/rename run in one transaction and catch the named normalized-name unique constraint.
- Attach loads both owned parents and inserts within one transaction. The unique pair constraint
  and tenant constraints are authoritative; duplicate races read and return the owned existing row.
- Detach and delete use owner-scoped writes. Delete racing with attach either commits first and
  makes attach fail safely, or attach commits first and is then cascaded. No orphan survives.
- Frontend state is a cache: after conflict, delete, or multi-action changes it refetches the
  authoritative Tag/membership projection.
- Constraint failures map by constraint identity/SQLSTATE, never by parsing localized error text.
- No external call belongs in a Tag transaction.

## Migration strategy

Use one focused Alembic revision after the deployed AI Summary head:

1. Preflight PostgreSQL version, current Alembic head, existing names, UUID convention, and the
   implemented Spaces trigger pattern.
2. Create `tags`, named checks, unique constraints, and owner/name index.
3. Create `discovery_tags`, named FKs/uniqueness, owner-leading indexes, and the Discovery-owner
   trigger/function. Reuse the same reviewed trigger function as Spaces only if it is deliberately
   generic and has identical error semantics; otherwise create a narrowly named function.
4. Validate upgrade, downgrade, and upgrade again on PostgreSQL. Downgrade drops memberships and
   their trigger/function before Tags and removes only objects introduced by this revision.
5. Deploy additive schema before backend, then owner-scoped API behind a disabled feature flag,
   then frontend; enable after smoke tests. Do not downgrade after user writes without an explicit
   data-loss decision.

There is no backfill and no seed. Existing Discoveries begin with zero Tags. No Discovery column is
altered. PostgreSQL is authoritative for trigger/constraint tests. SQLite, if still used for fast
unit tests, cannot validate the PostgreSQL trigger, composite behavior, collation, or concurrency;
those cases must run against PostgreSQL and never be skipped as equivalent coverage.

## Testing strategy

Backend tests cover:

- authenticated creation and unauthenticated rejection;
- trimming, control/null rejection, maximum length, NFKC/full-width equivalence, case folding,
  empty normalized names, and preservation of display spelling;
- duplicates rejected within one User and allowed across Users;
- owner-only list/search/count/sort/pagination, owned read, and foreign Tag as not found;
- rename/no-op/casing-only rename, conflict rollback, delete, and name recreation;
- Discovery survival after Tag deletion;
- attach, idempotent/duplicate/concurrent attach, detach, multiple Tags per Discovery, and one Tag on
  multiple Discoveries;
- foreign Tag, foreign Discovery, mixed-owner pair, random ID, malformed ID, safe identical errors,
  trusted-origin enforcement, and direct database same-owner rejection;
- one-Tag library filtering combined with Space/platform/favourite/archive/search;
- cascades on Discovery, Tag, and account deletion;
- query-count/N+1 assertions and representative PostgreSQL query plans;
- all existing auth, recovery, Discovery, metadata, Spaces, and AI Summary suites remain passing.

Frontend tests cover the Tags list, empty/search/loading/error states, create, duplicate error,
rename, delete confirmation/copy, Tag chips, assign/remove, several Tags on one Discovery, one-Tag
filtering, empty filtered state, Space-filter interaction, long names, keyboard/focus behavior,
optimistic rollback if used, representative mobile layouts, and regressions in all existing flows.

Migration tests upgrade/downgrade PostgreSQL and inspect all types, defaults, named constraints,
indexes, trigger behavior, cascades, and concurrent uniqueness. End-to-end testing covers create →
assign several Tags → combine Tag and Space filter → rename → detach → delete while proving every
Discovery remains.

## Performance and scalability

Expected queries are an owner's alphabetical Tag page, batched Tags for a Discovery page, paginated
Discoveries for one Tag, attach/detach, and owner/name conflict lookup. Owner-leading indexes match
these paths. Discovery lists must fetch summaries with one batched query or aggregate/subquery,
never one query per card. Counts use one grouped owner-scoped query.

Initial hard product limits are **500 Tags per User** and **20 Tags per Discovery**. The service
locks the owning User row for Tag creation and the owned Discovery row for first attachment before
counting/inserting, so concurrent requests cannot bypass the caps. PostgreSQL concurrency tests
verify that serialization; unique constraints remain authoritative for identity. These generous
portfolio-scale limits bound payloads and abusive writes. Raise them only from observed need and
query-plan review.

Tag listing is keyset-paginated (default 50, maximum 100); Discovery lists retain existing stable
pagination. `ILIKE` substring search over at most 500 normalized names needs no trigram dependency.
Future bulk operations require bounded, atomic contracts. Future AI suggestions can reference
existing owned Tag IDs or present candidate text through a separate inferred-data design; no schema
redesign is required for human Tags. A graph database is unnecessary for two ordinary many-to-many
query paths and would weaken the single PostgreSQL ownership boundary.

## Rollout plan

1. Approve this plan, [database decisions](tags-database-decisions.md), and
   [API contract](tags-api-contract.md).
2. Implement the migration, models, normalization, services, and owner-scoped API.
3. Implement the Tags management, assignment, card, and filtering UI.
4. Run all new and existing automated checks.
5. Rehearse migration, triggers, cascades, concurrency, and query plans on live PostgreSQL.
6. Browser-test desktop/mobile, keyboard, focus, long names, failures, and combined filters.
7. Open a focused feature-branch PR with schema/API/UI/test/docs review.
8. Deploy to production later using migration-first, flag-controlled rollout and privacy-safe
   monitoring.

## Completion criteria

- **Schema:** reviewed migration matches every field, named constraint, owner index, cascade, limit,
  and clean downgrade; no backfill or Discovery change.
- **Ownership:** service predicates, tenant-aware FK, and trigger reject every cross-user path; safe
  errors reveal no existence or name.
- **API:** every documented route/schema/status/filter/sort/pagination/idempotency rule is exact.
- **UX:** management, assignment, chips, confirmation, responsive and accessible states work
  without cluttering the library.
- **Filtering:** one Tag composes predictably with Space, platform, favourite, archive, and keyword.
- **Tests:** backend, frontend, migration, authorization, concurrency, cascade, regression, and
  query-plan checks pass on PostgreSQL; manual browser results are recorded.
- **Documentation:** README, architecture, data model, ER diagrams, schema, roadmap, and dedicated
  Tags documents agree.
- **Boundaries:** no automatic/suggested Tags, AI coupling, semantic search, embeddings, vectors,
  hierarchy, aliases, merge, bulk tagging, sharing, or collaboration is introduced.

## Unresolved decisions before coding

No architectural decision blocks implementation. The approved limits are 500 Tags per User and 20
Tags per Discovery. The implemented presentation shows three chips before overflow and places the
responsive Tags section separately beneath Spaces.
