# Semantic Search Database Decisions

These decisions govern the proposed MVP. “Final” means the first-release contract; “revisitable”
marks an intentional evidence-based extension point.

Implementation note: revision `20260805_0008` creates `vector(1536)`. PostgreSQL retrieval uses
exact `<=>` cosine distance under owner and relational-filter predicates. HNSW remains postponed.
Portfolio execution, quotas, and backfill are process-local/inline; durable accounting and queue
infrastructure remain production work.

## SEM-ADR-001 — PostgreSQL plus pgvector

- **Context:** Retrieval is owner-scoped and combined with relational filters.
- **Decision:** Store/search vectors in existing PostgreSQL with pgvector.
- **Alternatives:** External vector database; arrays/JSON; application memory.
- **Consequences:** One authorization, transaction, backup, and deletion boundary; ANN scaling is
  less specialized but adequate for portfolio-sized per-user libraries.
- **Status:** Final until measured PostgreSQL limits demonstrate need.

## SEM-ADR-002 — Separate `discovery_embeddings`

- **Context:** Vectors have provider, dimension, lifecycle, privacy, and failure state.
- **Decision:** Add a dependent table, never columns on Discovery, Metadata Record, or AI Summary.
- **Alternatives:** Vector on those rows; generic embeddings table.
- **Consequences:** Clear provenance/additive disablement; one join.
- **Status:** Final.

## SEM-ADR-003 — One current row

- **Context:** History duplicates private derived data and complicates retrieval.
- **Decision:** Unique `discovery_id`; replace vector only after successful regeneration. Do not
  retain prior vectors. A stale/private-policy-mismatched row is ineligible for search.
- **Alternatives:** Immutable history; current pointer plus versions.
- **Consequences:** Bounded retention and simple reads; no rollback/comparison history.
- **Status:** Final for MVP; history revisitable for demonstrated audit/evaluation needs.

## SEM-ADR-004 — Exact search before HNSW

- **Context:** Each query sees only one owner's filtered corpus, expected to be small.
- **Decision:** Launch exact cosine distance with B-tree relational indexes. Add a partial HNSW
  index only after `EXPLAIN` and latency/load thresholds justify ANN. Do not launch IVFFlat.
- **Alternatives:** HNSW immediately; IVFFlat; external ANN.
- **Consequences:** Exact recall and simple filtered semantics; linear scans eventually cost more.
- **Status:** Final rollout order; threshold revisitable from measurements.

## SEM-ADR-005 — Cosine distance

- **Context:** Semantic similarity should be insensitive to magnitude and providers document
  cosine broadly.
- **Decision:** Validate nonzero finite vectors and rank with pgvector cosine distance (`<=>`),
  exposing bounded similarity `1 - distance`. Do not mix spaces/models.
- **Alternatives:** Inner product for normalized vectors; Euclidean distance.
- **Consequences:** Provider-neutral clarity; inner product may later improve measured normalized
  workloads but requires an explicit invariant.
- **Status:** Final for MVP; operator revisitable with evaluation.

## SEM-ADR-006 — Dimension and model identity are schema contracts

- **Context:** Model aliases and output dimensions change.
- **Decision:** Pin provider, exact model identifier, and configured dimension; validate every
  response. Use `vector(1536)` for the first migration. A dimension change requires a new migration
  and full re-embedding, or a new dimension-specific table/column during a zero-downtime transition.
  Never reinterpret old vectors.
- **Alternatives:** Unbounded `vector`; arrays; silent truncation.
- **Consequences:** Strong validation/indexability; model changes are deliberate migrations.
- **Status:** Final principle; initial dimension/provider revisitable before migration approval.

## SEM-ADR-007 — Provider/model coexistence is transitional

- **Context:** Queries and documents must inhabit the same vector space.
- **Decision:** One configured active provider/model/dimension serves a search request. Rows record
  their provenance; different models may coexist only during migration, but only matching active
  rows are queried. A partial ANN index, if added, targets one active tuple and `status='succeeded'`.
- **Alternatives:** Blend scores from models; per-user provider choice.
- **Consequences:** Correct similarity with simple behavior; migrations temporarily reduce coverage.
- **Status:** Final for MVP.

## SEM-ADR-008 — Versioned deterministic document

- **Context:** Re-embedding must be reproducible and privacy-auditable.
- **Decision:** Use `semantic-discovery-v1` from the document specification.
- **Alternatives:** Raw concatenation; provider-specific prompts; chunking.
- **Consequences:** Stable fingerprints and tests; policy changes require version bumps/backfill.
- **Status:** Final for v1; content policy revisitable by version.

## SEM-ADR-009 — Notes and save reasons require opt-in

- **Context:** They can contain the most sensitive user context.
- **Decision:** Exclude by default; one explicit account setting includes both and triggers
  re-indexing. Search queries remain private regardless.
- **Alternatives:** Always include; per-Discovery checkbox; never include.
- **Consequences:** Safer default but weaker recall for private memories until enabled.
- **Status:** Final default; consent granularity revisitable.

## SEM-ADR-010 — Tags and Spaces share private-context consent

- **Context:** Names improve retrieval but can reveal health, identity, or projects.
- **Decision:** Exclude by default and include under the same explicit setting, with sorted values.
- **Alternatives:** Always include; Tags only; treat as filters only.
- **Consequences:** Structured filters always work; semantic recognition of organization is opt-in.
- **Status:** Final for MVP; separate controls revisitable.

## SEM-ADR-011 — AI Summary content is approved by default

- **Context:** Summaries/key points/topics are private derived text but were generated from approved
  metadata; they can materially improve retrieval.
- **Decision:** Include current successful/stale display content by default, excluding entities.
  If AI Summaries are absent/disabled, indexing works without them.
- **Alternatives:** Exclude all AI output; require another consent; embed only summary.
- **Consequences:** Better recall and coupling through fingerprints, without requiring summaries.
- **Status:** Revisitable before implementation after provider disclosure review.

## SEM-ADR-012 — SHA-256 input fingerprint and derived staleness

- **Context:** Timestamps over/under-invalidate and missed events occur.
- **Decision:** Hash exact versioned inputs. Reads/work claims recompute the target identity;
  mutation hooks may eagerly mark stale but are not the correctness boundary.
- **Alternatives:** `updated_at`; database triggers; unconditional regeneration.
- **Consequences:** Precise idempotency with bounded hashing.
- **Status:** Final.

## SEM-ADR-013 — Manual, bounded first indexing

- **Context:** Indexing sends data, costs money, and no durable production worker exists.
- **Decision:** Manual per-Discovery indexing plus explicit user-started bounded backfill. New saves
  never wait or auto-call a real provider. Account-level automatic indexing is later opt-in.
- **Alternatives:** Automatic after save/enrichment; schedule all; manual only forever.
- **Consequences:** Clear consent/cost, slower coverage.
- **Status:** Final for first release; automation revisitable after durable worker/disclosure.

## SEM-ADR-014 — Simple hybrid retrieval

- **Context:** Exact lexical matches and unembedded rows must remain discoverable.
- **Decision:** Retrieve bounded keyword and semantic candidate sets under identical owner/filters,
  fuse with reciprocal-rank fusion (RRF), then apply a deterministic exact-title boost and stable
  tie-break. Fall back to keyword-only on semantic failure/no confidence.
- **Alternatives:** Vector only; weighted incomparable raw scores; LLM reranking.
- **Consequences:** Robust scale-independent fusion; relevance tuning still needs fixtures.
- **Status:** Final approach; RRF constant/boost revisitable.

## SEM-ADR-015 — Do not retain semantic queries

- **Context:** Queries, Tags, and memory descriptions are private.
- **Decision:** Validate and embed in memory; do not store/log query text or vector by default. A
  per-process short-lived keyed-hash cache may retain encrypted/in-memory vectors for at most five
  minutes and must include user/provider/model/policy scope.
- **Alternatives:** Search history; shared cache; analytics samples.
- **Consequences:** Lower privacy/incident value; weaker product analytics and cache hit rate.
- **Status:** Final default; opt-in history requires separate design.

## SEM-ADR-016 — Usage and estimated cost

- **Context:** Provider billing is volatile and retries can amplify cost.
- **Decision:** Persist per-current successful/failed attempt usage tokens and optional estimated
  minor units from external configuration; aggregate queries separately without content. Never
  hard-code price.
- **Alternatives:** Provider dashboard only; detailed prompt logs.
- **Consequences:** Quotas/budgets are enforceable; estimates may differ from invoices.
- **Status:** Final principle; currency/rates revisitable configuration.

## SEM-ADR-017 — Cascade deletion and no global cache

- **Context:** Derived private data must not outlive sources or cross owners.
- **Decision:** `discovery_id ON DELETE CASCADE`; account purge cascades through Discovery. No
  content-addressed cross-user embedding cache. Query caches are user-scoped and expire.
- **Alternatives:** Orphan/anonymize; global URL embedding reuse; soft delete.
- **Consequences:** Clear deletion and duplicated provider work across users.
- **Status:** Final.

## SEM-ADR-018 — Durable worker is a production gate

- **Context:** Provider latency, outages, restarts, leases, and backfills exceed request lifetimes.
- **Decision:** Fake execution may run inline/in-process locally; portfolio MVP may use a labeled
  database-backed in-process poller. Real-provider production requires a separately deployed
  database lease worker. Do not add Redis/Celery without need.
- **Alternatives:** Synchronous API; ephemeral production tasks; new queue now.
- **Consequences:** Simple infrastructure with careful PostgreSQL concurrency; production is blocked
  until worker recovery is proven.
- **Status:** Final gate; worker technology revisitable.

## SEM-ADR-019 — Bounded resumable backfill

- **Context:** Existing libraries may be large and provider limits/outages are normal.
- **Decision:** An owner may enqueue a capped batch with a durable hashed idempotency key. Claims
  skip current rows, stop at quotas/budget/kill switch, and resume by stable Discovery order.
- **Alternatives:** One giant transaction; automatic global schedule; admin script.
- **Consequences:** Observable, interruptible progress; multiple user actions may be needed.
- **Status:** Final for MVP; scheduled backfill revisitable.
