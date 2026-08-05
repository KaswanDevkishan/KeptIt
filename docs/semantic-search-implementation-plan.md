# Semantic Search: Production MVP Implementation Plan

## Status, assumptions, and product goal

This is the normative design for the phase after Tags. The portfolio MVP is implemented behind a
disabled-by-default flag. PostgreSQL with pgvector performs bounded exact cosine retrieval; SQLite
exists only as an automated-test fallback and is not a production semantic-search engine.
It assumes existing authentication, owner-scoped Discoveries, metadata, Spaces, Tags, optional AI
Summaries, keyword/filter behavior, trusted-origin policy, and safe errors remain authoritative.

Semantic Search solves recall when a user remembers meaning but not stored wording. It supports
KeptIt's memory-oriented promise by mapping an approximate memory—“that abandoned town video from
Japan”—to the user's saved context. Keyword search remains essential for exact titles, names,
identifiers, unembedded/new Discoveries, predictable filtering, and provider outages. Semantic
retrieval is additive, never a replacement.

The feature is optional because embedding inputs and queries may reveal private interests to a
third party and every call has latency/cost. KeptIt must start and all existing workflows must work
with the feature/provider off. Owner isolation, bounded input, explicit private-context consent,
quotas, and a backend-only provider boundary shape every decision.

## MVP scope and exclusions

The release creates one current searchable embedding per Discovery from an approved, deterministic
document; embeds a validated user query; ranks owned Discoveries; composes Space, Tag, platform,
favourite, and archive filters; provides safe match provenance where reliable; detects/re-embeds
stale rows; handles provider disablement/outages; and preserves keyword fallback. Indexing is
manual per Discovery plus explicit bounded owner backfill; Discovery creation never waits.

Excluded: chat, generative/RAG answers, public or shared search, cross-user recommendations,
image/audio/video embeddings, OCR, transcription, full-page extraction, personalized training,
cross-user learning/cache, graph search/databases, automatic Tags/Spaces, and second-LLM reranking.

## Search behavior

### Modes and first release

- `keyword` runs the existing lexical path and never calls an embedding provider.
- `semantic` returns only current, matching-space vectors above an evaluated threshold.
- `hybrid` is the recommended default: retrieve keyword and semantic candidates under identical
  relational filters, fuse rankings, and keep keyword-only Discoveries visible.

Queries are trimmed/whitespace-normalized Unicode of 2–500 code points and at most 2,000 UTF-8
bytes. Do not translate or force a language; the configured multilingual model handles it. Return
20 results by default, maximum 50. Each branch retrieves at most 100 candidates. Pagination uses a
short-lived opaque cursor bound to owner, normalized request hash, filters, ranking version, and
active model. Ranking changes can invalidate a cursor with safe `422`; do not promise snapshot
consistency across concurrent indexing.

Cosine similarity is `1 - cosine_distance`. A provisional **0.35** threshold rejects weak semantic
candidates; it is configuration validated against fixtures, not a universal truth. Semantic-only
returns an empty success when nothing clears it. Hybrid returns keyword results and declares
`no_confident_semantic_match`. Ties resolve by exact-title match, fused rank, semantic similarity,
then `created_at DESC, id DESC`.

Archive defaults to active. `archived` or `all` is explicit. Space/Tag/platform/favourite/archive
filters are SQL predicates shared by both branches and are not encoded as post-hoc UI filtering.
Exact normalized custom/metadata title matches receive a modest deterministic boost. If the
feature/provider is disabled or a query call fails, hybrid visibly falls back to keyword; explicit
semantic-only returns safe `503` when it cannot execute. No fake semantic results are produced.

## Input policy

The [embedding document specification](semantic-search-document-spec.md) is authoritative.

| Class | Default | Included fields |
| --- | --- | --- |
| User-authored | Partial | Custom title; notes/save reasons only with explicit private-context setting |
| Fetched metadata | Yes | Title, description, site name, publisher |
| Deterministic source | Yes | Platform and canonical hostname |
| AI-generated | Yes when present | Summary, key points, topics; no entities |
| Organizational | Opt-in | Tag and Space names only with private-context setting |

Raw URLs, paths/query strings, IDs, accounts/sessions, timestamps, thumbnail URLs, favourite/archive,
provider payloads, and full pages are excluded. The setting copy is **“Include my notes in semantic
search.”** Its disclosure explicitly names personal notes, save reasons, Tags, and Spaces and says
they are sent to the configured embedding provider. It defaults off. Disabling it immediately
makes affected vectors ineligible/stale until replaced. Private notes and organization can expose
health, identity, plans, or relationships; a vector is also private derived data, not anonymization.

## Embedding document construction

`semantic-discovery-v1` uses labeled LF-separated fields in fixed priority, NFC and bounded
whitespace normalization, deterministic deduplication, original-language text, explicit
provenance, and no missing placeholders. It is capped at 12,000 code points/24,000 UTF-8 bytes;
per-field caps and priority truncation occur before the provider. It excludes unnecessary URLs and
identifiers. SHA-256 of a length-delimited version/policy/provenance/document envelope is the
private input fingerprint. Prompt-like metadata is inert labeled data: no tools, instructions,
URLs, or provider options are derived from content.

## Provider abstraction and recommendation

Use a small typed boundary, not a plugin framework:

```text
EmbeddingProvider
  identity -> {provider, model, dimension}
  embed_one(text, purpose=document|query, timeout) -> {vector, usage?}
  embed_batch(texts, purpose=document, timeout) -> ordered results   # optional
```

The adapter validates finite floats, exact dimension, nonzero norm, response cardinality, timeout,
and cancellation. It classifies `timeout`, `rate_limited`, `authentication`, `unavailable`,
`unsupported_input`, `invalid_output`, and `internal` without returning provider bodies. Usage is
optional input tokens/units; absence is valid. Batch has a configured item/byte cap and preserves
order. A deterministic fake hashes normalized text into a stable, nonzero normalized vector and
can simulate every error/dimension case without network access.

| Option | Strengths | Trade-offs |
| --- | --- | --- |
| OpenAI embeddings | Simple Python/HTTP integration, documented usage/cost controls, established KeptIt adapter/key operations, stable selectable dimensions | Third-party private-data processing; model/price/rate policies require review |
| Gemini embeddings | Strong multilingual options and selectable dimensions | Adds provider/key/SDK operations and current model-policy review |
| Cohere embeddings | Search-query/document modes, multilingual model, selectable dimensions | Adds another vendor boundary and task-specific adapter semantics |
| Local sentence-transformer | Text stays local; offline after model acquisition | Model hosting/downloads, CPU/RAM, version pinning, packaging, and quality operations are materially heavier |

Recommend optional OpenAI `text-embedding-3-small`, pinned at 1,536 dimensions, because KeptIt
already has optional OpenAI server-only configuration and it minimizes new operational surface.
This is revisitable before migration and deployment: benchmark representative English/Japanese/
multilingual queries, verify current prices/rate limits/data controls, and compare at least one
local or vendor alternative. No live provider is required for development or CI.

## Database design

Enable pgvector through Alembic and add only `discovery_embeddings`:

| Column | PostgreSQL type | Null/default | Purpose and constraints |
| --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | Primary key |
| `discovery_id` | `uuid` | not null | Unique FK to `discoveries.id ON DELETE CASCADE` |
| `provider` | `varchar(50)` | not null | Allowlisted configured provider; nonempty |
| `model` | `varchar(200)` | not null | Exact configured identifier; nonempty |
| `embedding_dimension` | `integer` | not null | `> 0`, equals migration/configured dimension |
| `document_version` | `varchar(100)` | not null | Canonical construction identifier |
| `input_fingerprint` | `bytea` | not null | 32-byte SHA-256 for target attempt |
| `embedding` | `vector(1536)` | null | Present only for searchable success; finite/nonzero validated before write |
| `status` | `varchar(20)` | not null; `pending` | Stored: pending/processing/succeeded/failed/unsupported/stale |
| `generated_at` | `timestamptz` | null | Successful vector generation time |
| `last_attempted_at` | `timestamptz` | null | Latest started attempt |
| `failure_code` | `varchar(50)` | null | Allowlisted safe category |
| `failure_message_safe` | `varchar(240)` | null | Bounded, sanitized, no provider/content text |
| `usage_tokens` | `integer` | null | Provider-reported input usage; `>= 0` |
| `estimated_cost_minor_units` | `bigint` | null | Config-derived estimate; `>= 0` |
| `retry_count` | `smallint` | not null; `0` | Bounded `>= 0` |
| `available_at` | `timestamptz` | not null; current time | Backoff/runnable time |
| `processing_started_at` | `timestamptz` | null | Claim diagnostics/recovery |
| `lease_expires_at` | `timestamptz` | null | Durable lease deadline |
| `generation_token_hash` | `bytea` | null | Rejects late worker writes; never public |
| `created_at` | `timestamptz` | not null; current time | Creation |
| `updated_at` | `timestamptz` | not null; current time | State mutation |

Cross-field checks require vector/generated time only for succeeded; active leases only for
processing; safe failure fields only for failed; fixed fingerprint/token lengths; and retry/cost
bounds. Indexes: unique `discovery_id`; `(status, available_at, created_at)` partial for pending/
retryable work; `(lease_expires_at)` partial for processing; and Discovery FK lookup is covered by
uniqueness. Exact retrieval joins Discovery and uses existing owner/filter indexes. If HNSW is
later justified, create it concurrently as partial cosine index for the single active
provider/model/dimension and succeeded/non-null rows.

Idempotent POSTs also require a small durable `semantic_search_idempotency_keys` operational table
(or a reviewed existing generic equivalent): UUID primary key; non-null owner/Discovery-or-backfill
scope, action, 32-byte key hash, 32-byte request fingerprint, safe result code, `created_at`, and
`expires_at`; unique `(user_id, action, key_hash)` and an expiry-cleanup index. It stores neither
raw keys nor private response/query/document content, cascades with the User, and has bounded
retention. Daily quota reservations likewise require an atomic owner/day counter or a reviewed
generic usage ledger; process memory and provider dashboards are not concurrency authorities.

One row is replaced, not versioned. Different models may coexist only during a controlled rollout;
a query selects one matching provider/model/dimension. With `vector(1536)`, a dimension change is
an explicit expand/backfill/switch/contract migration (or a new dimension-specific table), never
an in-place reinterpretation. Old rows are not queried after the switch and are removed after
rollback window. No vector belongs on existing tables.

## pgvector decision

PostgreSQL plus pgvector preserves the existing ownership, transaction, cascade, backup, and
operational boundary. A separate vector database would duplicate private data and require
cross-system authorization/deletion consistency without demonstrated scale need.

Exact cosine search is enough while filtered per-user candidate sets are portfolio-sized (expected
hundreds to low tens of thousands) and measured p95 stays within the search budget. B-tree owner
and structured-filter indexes can reduce the exact candidate set before ordering by distance.
Benchmark with `EXPLAIN (ANALYZE, BUFFERS)` and representative skew.

HNSW becomes useful only when exact p95/load breaches an agreed target (initially 500 ms database+
service excluding provider query embedding) at representative corpus/concurrency. It offers a
better speed/recall trade-off than IVFFlat but costs memory, slower writes/builds, vacuum/reindex
operations, and approximate recall. IVFFlat needs trained lists and probe tuning, is sensitive to
data size/distribution, and is poorly justified for changing small corpora. Exact search remains
the recall baseline even after ANN.

Approximate indexes apply relational filters after candidate scanning in common plans, so tenant
and selective Tag/Space predicates can underfill results. Never build a partial index per user.
Use owner predicates in SQL regardless; tune iterative scans/overfetch only on a pinned pgvector
version; compare ANN recall against exact; consider partitioning only at demonstrated scale. A
provider/model/status partial vector index prevents mixed spaces but not per-tenant isolation.

Migration requires supported PostgreSQL, `CREATE EXTENSION IF NOT EXISTS vector`, extension
privilege, pinned tested pgvector version, and clean downgrade ordering. Render currently documents
pgvector support on PostgreSQL 13+ via `CREATE EXTENSION vector`; deployment must verify the exact
plan/version/region, migration privileges, backups, replicas, and extension upgrade procedure.
Alternative providers must meet the same requirements. No production enablement occurs otherwise.

## Ownership and tenant isolation

Every retrieval starts from `discoveries.user_id = current_user.id`, joins current eligible
embeddings, then applies structured predicates and ranking in SQL. Embeddings inherit ownership
only through non-null unique `discovery_id`; clients never supply owner IDs. Foreign/missing
Discovery routes are identical 404. Account deletion cascades Discoveries then embeddings; direct
Discovery deletion cascades immediately. There is no global vector/content cache, public index,
shared namespace, or query across owners. Approximate retrieval, if introduced, must pass explicit
cross-user leakage and exact-recall comparisons before rollout.

## Indexing lifecycle

Public states are `unavailable` (no row), `pending`, `processing`, `succeeded`, `failed`,
`unsupported`, and derived/stored `stale`.

```text
unavailable -> pending -> processing -> succeeded
                    |          |  \-> failed -> pending (bounded retry)
                    |          \----> unsupported
succeeded -- input/config change --> stale -> pending
processing -- expired lease ----------> pending or failed
```

Creation/upsert uses row locking plus unique Discovery identity. It recomputes the target
fingerprint and suppresses duplicate current/active requests. Workers claim with
`FOR UPDATE SKIP LOCKED`, set a random generation token hash and expiring lease, commit, call the
provider outside the transaction, then conditionally finalize only if token/fingerprint still
match. Heartbeats extend bounded leases; expired work retries with exponential backoff+jitter and
an attempt cap. Late results cannot resurrect deleted or superseded rows.

Custom title and approved metadata changes stale. AI Summary content regeneration stales when the
included content changes. Note/save-reason/Tag/Space changes stale only when private-context
consent is enabled. Favourite/archive changes never stale because they are filters. Platform/
hostname, document-policy, provider/model/dimension changes stale. Reads recompute target identity
for correctness; mutation events eagerly mark stale for responsiveness. Stale vectors are not
searched. Regeneration replaces the vector atomically on success; failure stays safely failed/stale
according to the UI contract and never searches known outdated private-policy content.

## Trigger strategy

Manual indexing best controls consent and cost but gives partial coverage. Automatic indexing after
save/enrichment improves coverage yet surprises users, couples costs to writes, and needs a durable
worker. User-configurable automation is the desired later state but needs account settings and
disclosure. Scheduled backfill is operationally useful but unsafe as an implicit global action.

First release: explicit per-Discovery indexing and explicit capped user backfill. The fake provider
may auto-index seeded/synthetic local data behind a development-only flag. Do not wait during
Discovery creation. After consent, worker maturity, budget controls, and outage behavior are proven,
offer account-level “Automatically index new Discoveries”; default remains off. Provider outages
leave queued work recoverable and keyword search healthy.

## Background processing and backfill

Local fake calls may execute synchronously after the API transaction or in a labeled in-process
task. Portfolio MVP may poll the database in-process, accepting restart interruption. Real-provider
production requires a separately deployed durable poller using leases/tokens above. It claims
bounded batches, groups provider batches only when supported, limits total texts/bytes, preserves
per-item outcomes, respects configured concurrency and provider `Retry-After`, uses capped
exponential backoff+jitter, stops claiming on graceful shutdown, finishes or releases current
leases, and recovers stale claims.

Backfill is owner-initiated, stable-order, idempotent, quota-reserving, resumable, and capped at 100
per request. It skips current/unsupported rows and pauses under provider budget/kill switch. A later
scheduled backfill may enqueue small fair batches across opted-in users; no user can monopolize the
queue. Redis/Celery is unnecessary until database polling is measured insufficient.

## Query embedding lifecycle

Validate content type/schema, normalize whitespace, enforce 2–500 code points/2,000 bytes, reject
control/null input, then call the active provider with query purpose and a short configured timeout.
Preserve language. Validate dimension/finite/nonzero norm before parameterized SQL. Track aggregate
usage and estimated cost against an atomic per-user daily query budget, but persist no text or
vector by default. Logs contain request ID, safe mode/outcome/timing, not query, Tags/Spaces, vector,
document, user-content, or provider body.

An optional five-minute in-memory cache uses an HMAC of user ID, normalized query, provider/model/
dimension, and policy/ranking version; entries never cross users, never use plaintext keys, are
bounded/LRU, disappear on restart, and are disabled unless justified. Apply per-user and IP-aware
limits, request-size bounds, concurrency caps, timeouts, and provider budgets. Tag searches and
semantic queries are private data, not analytics labels.

## Hybrid search design

Vector-only misses unembedded content/exact identifiers. Keyword-only misses paraphrases. Weighted
raw scores are hard to calibrate across lexical/vector scales. RRF is stable and simple. Retrieving
semantic candidates before structured filtering risks incorrect empty/foreign candidate behavior;
filters must constrain each SQL branch.

Recommended `semantic-hybrid-v1`:

1. Owner/filter both branches identically.
2. Retrieve up to 100 keyword ranks and 100 semantic ranks above threshold.
3. Calculate `RRF = 1/(60 + keyword_rank) + 1/(60 + semantic_rank)`, omitting absent terms.
4. Add a small `0.01` exact normalized title boost; this sample is explicitly tunable.
5. Order by boosted RRF, then semantic similarity, `created_at DESC`, and ID.

Exact title matches should normally lead. Tag/Space/platform/favourite/archive are hard filters, not
score features. Missing/stale/failed embeddings remain keyword discoverable. If provider/query
embedding fails or no semantic confidence exists, hybrid is keyword-only with a disclosed fallback.
No second LLM reranker is MVP; evaluation may justify it only as future work.

## API design

The exact [API contract](semantic-search-api-contract.md) defines authenticated POST semantic
search, per-Discovery index/retry, status, and optional bounded owner backfill. Mutations require
trusted Origin and hashed 16–128-character idempotency keys. Search supports semantic/hybrid/
keyword modes, all current filters, limit 1–50, opaque cursor, safe 0–1 relevance presentation,
nullable semantic similarity, and allowlisted non-content match reasons. It exposes no vectors,
fingerprints, tokens/costs, leases, or credentials.

Hybrid disabled/unavailable behavior is `200` keyword fallback; semantic-only inability is safe
`503`; successful no-confidence is an empty `200`. Per-user/IP rate limits return `429` with bounded
`Retry-After`. Owner lookup precedes status/index actions, and foreign/absent remains identical 404.

## Frontend UX

Use one search box with a compact mode control: **Keyword** and **Meaning**; “Meaning” sends hybrid
mode by default, described as “Find saved items by idea, even when the words differ.” Preserve all
existing filter controls. Do not add a generative answer box.

- Enter submits; Escape clears/closes suggestions; results and filters remain keyboard navigable.
- Show a bounded loading indicator and keep prior results labeled while refreshing; never invent
  placeholders that resemble results.
- Disabled/unavailable state says keyword search remains available and offers that action.
- No-results state distinguishes no filtered matches from no confident meaning match.
- Partial coverage shows “42 of 50 eligible Discoveries indexed” and an explicit **Index more**
  action; it does not imply excluded items were searched semantically.
- Stale cards/status offer retry; stale vectors do not influence results.
- Show “Matched by title/summary/topic/private context” only from reliable allowlisted provenance.
  Avoid numeric relevance badges initially; expose score to clients for diagnostics but label no
  percentage as confidence.
- Desktop uses the existing library toolbar; mobile places mode and filters in the existing sheet
  with full-width search and reachable controls. Preserve focus after results and announce loading/
  fallback/results through an accessible live region.
- Privacy settings explain the provider and default field policy, allow global opt-out, and state
  that notes/Tags/Spaces are sent only when the setting is on. Opt-out disables provider calls and
  offers deletion/replacement of embeddings per approved retention UX.

## Privacy and security

Provider keys are server-only secret-manager/environment values and never responses/frontend
configuration. Inputs, vectors, semantic queries, Tags, and notes are private. Disclose provider,
field categories, retention/training and region; require explicit opt-in before real-provider
indexing and separate private-context consent. Review provider zero-retention/data-control terms,
subprocessors, regional routing, deletion, and incident notification before production.

Never log query/document/vector, notes, Tags/Spaces, raw URL, provider bodies, credentials, or put
content/user IDs in metric labels. No account/session data or internal IDs go to providers. Use
safe classified errors, parameterized SQL/SQLAlchemy, strict types, finite/dimension/vector bounds,
timeouts, response-size bounds, TLS, least-privilege DB access, no-store responses, trusted origins,
and output escaping. Prompt-like metadata remains plain bounded text and has no tool capability.

Deletion cascades live embeddings; account purge includes them; backups expire on disclosed
schedule; provider retention/deletion is documented. Incident response can disable provider and
feature flags, revoke/rotate keys, stop workers, quarantine pending jobs, identify affected request
windows using content-free telemetry, notify per policy, and re-index/delete safely. Apply user/IP
rate limits, quotas, concurrency caps, and maximum vector candidate/result bounds.

## Cost controls

Use independent feature, real-provider, query, indexing, automatic-indexing, backfill, and admin
kill-switch flags. Defaults are off for real provider/automation. Configure per-user daily indexing
and query limits, concurrent work, batch items/bytes, document/query sizes, timeouts, retry count,
backoff, model/dimension, and provider monthly/daily budgets. Reserve quota atomically before work;
idempotent duplicates do not charge twice. Store provider usage where available and optional cost
minor units using deploy-time rates/currency—never hard-coded volatile prices. Budget exhaustion
stops new calls but preserves keyword search and queued state.

## Observability

Metrics: indexing accepted/attempted/succeeded/failed/unsupported/stale; duplicate suppression;
provider/query/indexing latency; semantic/hybrid/keyword query volume; query latency; zero-result
rate; fallback reason/rate; input usage and estimated cost; per-class rate limits; queue/backlog age
and size; retries; expired-lease recovery; batch size; indexed coverage; exact vector scan latency/
rows; HNSW recall and index scans if added. Alert on backlog age, stuck leases, failure/latency/cost
spikes, coverage regressions, and fallback increases.

Labels use safe low-cardinality provider/model/status/error/ranking versions only. Do not log or
label raw queries, vectors, documents, URLs/hostnames, titles, metadata, summaries, notes,
save reasons, Tag/Space names, emails, sessions, raw provider errors, request bodies, or high-
cardinality user/Discovery IDs. Use controlled request IDs for incident correlation.

## Testing strategy

Backend unit/service/API/PostgreSQL migration tests cover deterministic fake output and dimension;
document normalization/order/truncation/fingerprint; metadata, Summary, Tag, note-policy, title,
platform/hostname staleness; archive/favourite non-staleness; disabled/missing provider; timeout,
rate limit, auth, invalid/malformed dimension/nonfinite/zero vectors; concurrency, duplicate claims,
leases/late results; owner isolation/direct cross-user leakage; cascade; query validation and no
retention; cosine/threshold/ranking; hybrid RRF/exact-title boost; every structured filter; keyword
fallback; partial indexing; no confidence; usage/cost/quota; safe errors/log redaction; extension/
schema upgrade-downgrade; and all existing suites.

Frontend tests cover mode and explanatory copy; validation; loading/success/no result; disabled/
provider-unavailable; partial/stale indexing; keyword fallback; active filters; mobile layout;
keyboard/focus/live announcements; privacy disclosure/opt-out; indexing progress; no raw vector or
fake result; and existing flows. CI uses only fake vectors and never a live provider.

## Migration strategy

1. Preflight PostgreSQL/provider version, Render plan/region, extension availability/privilege,
   Alembic head, backups, and rollback.
2. Add `CREATE EXTENSION IF NOT EXISTS vector`; create the typed table/checks/FKs/queue indexes.
3. Use `vector(1536)` only after provider/dimension approval; add no ANN index initially.
4. Upgrade/downgrade/upgrade on PostgreSQL, verifying extension downgrade policy separately: drop
   the table but drop the shared extension only if this migration created it and no dependents exist.
5. Deploy additive schema, fake provider/backend, then UI behind disabled flags. Existing rows need
   no synchronous migration/backfill.
6. Use explicit bounded development/user backfill and monitor exact plans.
7. For dimension/model change: add compatible storage/table, dual-write/re-embed without mixed
   queries, switch active configuration after coverage/evaluation, retain rollback briefly, then
   remove old storage in a later migration.
8. Rehearse on production-shaped data with locks, disk, backup/restore, extension upgrade, deploy
   ordering, rollback, and provider failover. Add HNSW concurrently only after evidence.

## Rollout plan

1. Approve these documents and unresolved product choices.
2. Implement document construction, deterministic fake, schema, and exact search.
3. Run a fake-provider development backfill and relevance fixtures.
4. Add one optional pinned real provider after legal/privacy/current-doc review.
5. Enable locally behind flags with real provider still opt-in.
6. Evaluate with limited consenting users and synthetic/consented labeled queries.
7. Tune threshold/RRF/title boost and publish evaluation results.
8. Deploy/prove the durable lease worker and distributed controls.
9. Add HNSW only when exact measured performance/scale justifies it and recall remains acceptable.
10. Rehearse migrations/rollback, approve blockers, then enable production gradually.

## Manual testing plan

With synthetic accounts and content, verify: exact-title query; paraphrase; vague memory; Japanese/
multilingual query; Tag+Space filters; platform/favourite/archive filters; partial coverage; stale
row after each included source change; no staleness for archive/favourite; provider disabled;
invalid key; rate limit; timeout; hybrid fallback; cross-user UUID/search isolation; deleted
Discovery during query/work; mobile mode/filter/progress; keyboard flow; large library latency and
stable cursor; no confident match; opt-in note retrieval then opt-out replacement; and no vector/
query/content in UI/logs.

## Completion criteria and production blockers

- **Schema/pgvector:** reviewed reversible Alembic migration, exact typed fields/checks/cascades,
  supported extension, exact-first query plans, and no vector on existing entities.
- **Provider/document/privacy:** deterministic fake plus one optional adapter pass contract tests;
  v1 construction/fingerprint and consent are exact; backend-only keys, disclosure, opt-out,
  deletion, retention/region review, and redaction are approved.
- **Indexing:** lifecycle, idempotency, leases, retries, stale recovery, backfill, quota, and delete
  races are proven; saves never wait.
- **Search quality:** an agreed multilingual/private fixture set demonstrates useful hybrid gains
  without unacceptable exact-title regression; threshold and fallback are documented.
- **API/frontend/filters:** contracts, safe owner behavior, accessible responsive UX, progress, and
  every current filter/keyword path pass.
- **Tests/migration/manual:** all new/applicable existing checks pass; PostgreSQL upgrade/downgrade,
  production-shaped query plans, and recorded manual scenarios pass.

Production is blocked by durable worker deployment and graceful recovery; distributed user/IP
limits; secret rotation; provider legal/privacy/retention/training/region approval; user consent
copy; budgets/alerts/kill switch; representative relevance/recall evaluation; Render pgvector and
resource verification; migration/backup/restore rehearsal; account-deletion verification; and
incident/runbook approval.

Unresolved product decisions: final provider/model/dimension after current benchmark/review;
semantic threshold and RRF/title boost after evaluation; daily query/index quotas and budget;
whether AI Summary inclusion needs separate consent; whether Tag/Space consent should split from
notes; exact opt-out deletion/replacement UX; search score exposure beyond API; automatic indexing
timing after the durable worker; and production database/search latency targets. None authorizes
chat, RAG, recommendations, sharing, rediscovery, Memory Threads, or other postponed work.

## Portfolio MVP implementation clarification

The portfolio release intentionally uses synchronous in-process per-Discovery indexing and bounded
inline owner backfill. These are acceptable locally but are not durable across process termination.
Results are bounded and `next_cursor` remains null; cursor pagination is postponed. Query/index
limits are local portfolio controls rather than distributed atomic rate limiting.

Postponed production work includes the durable worker and backfill queue, persistent distributed
quota accounting, distributed IP/user rate limiting, private-note/Tag/Space inclusion preferences,
HNSW, monitoring, budgets, alerts, and provider privacy approval. Real-provider production remains
blocked. The fake provider is for deterministic local tests. Exact pgvector `<=>` cosine search is
the PostgreSQL path; hybrid search retains keyword candidates, RRF, title boost, and fallback.
