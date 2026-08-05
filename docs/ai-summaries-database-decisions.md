# AI Summaries Database Decisions

These decisions govern the upcoming AI Summaries implementation. “Final” is the intended first-release contract; “revisitable” identifies an explicit extension point.

## AIS-ADR-001 — Separate derived-data table

- **Context:** AI output has different provenance, lifecycle, privacy, and failure states from a Discovery and its fetched Metadata Record.
- **Decision:** Store generated output in `ai_summaries`, related one-to-one to `discoveries`. Never place generated text in `discoveries` or `metadata_records` and never overwrite user-authored or fetched fields.
- **Alternatives:** Columns on `discoveries`; columns on `metadata_records`; a document store.
- **Consequences:** Provenance and deletion are clear and AI can be disabled without weakening the library; reads may require one extra join.
- **Status:** Final.

## AIS-ADR-002 — One current row, not immutable history

- **Context:** Regeneration may improve an output, but indefinite versions duplicate private derived data and complicate product semantics.
- **Decision:** Keep at most one current row per Discovery. Regeneration updates that row only after the new attempt succeeds; while it runs, retain the last successful output and expose `processing` with a regeneration indicator. A failed regeneration restores `succeeded` with the prior output and records safe attempt telemetry outside the public response. Do not retain prior successful versions initially.
- **Alternatives:** Immutable version per attempt; overwrite successful output when an attempt starts; separate current pointer and versions.
- **Consequences:** Simple reads and bounded retention; no user-visible history or rollback. Introduce version history later only for audit, comparison, or an embedding dependency that cannot be met by fingerprinted current rows.
- **Status:** Final for first release; history is revisitable with a documented retention reason.

## AIS-ADR-003 — Validated JSONB collections

- **Context:** Key points, topics, and entities are small ordered structures that are returned together and are not independently managed.
- **Decision:** Use JSONB columns validated by the application and database shape checks where practical. Store key points/topics as arrays of strings and entities as an array of bounded objects. Do not query JSONB for Tags or treat topics as Tags.
- **Alternatives:** Child tables; PostgreSQL arrays; one opaque JSON document.
- **Consequences:** Atomic replacement and a compact schema; application validation is essential and future independent query/edit needs may justify normalized tables.
- **Status:** Final for first release; normalization is revisitable.

## AIS-ADR-004 — Small provider boundary

- **Context:** Provider APIs, models, usage reporting, timeouts, and errors differ.
- **Decision:** Define one typed `generate(input, options) -> result` boundary with provider/model identifiers, prompt version, timeout/cancellation, structured output, usage, and safe classified failures. Implement a fake and at most one real adapter; no plugin framework.
- **Alternatives:** Provider calls in the service; a general AI framework; multiple initial providers.
- **Consequences:** Deterministic tests and replaceability with modest indirection; provider-specific capabilities remain inside the adapter.
- **Status:** Final boundary; initial provider is revisitable.

## AIS-ADR-005 — Manual first-release trigger

- **Context:** Generation costs money, sends approved data to a third party, and the repository has no durable production worker.
- **Decision:** The user explicitly selects **Generate AI summary**. Discovery creation and metadata enrichment never trigger AI automatically. Later account-level automatic generation requires a separate opt-in design.
- **Alternatives:** Automatic after enrichment; user-configurable automation now.
- **Consequences:** Predictable cost and disclosure, no save-path latency, and lower throughput; users must request each summary.
- **Status:** Final for first release; automation is revisitable.

## AIS-ADR-006 — Canonical input fingerprint

- **Context:** Retries must be idempotent and changed metadata must make old output visibly stale.
- **Decision:** Compute a SHA-256 fingerprint over a versioned, length-delimited canonical serialization of exactly the approved prompt inputs plus input-policy version. Store it as `bytea`. Do not include provider, model, or prompt version; those are regeneration policy, not source-input identity.
- **Alternatives:** Metadata `updated_at`; hash a full database row; no fingerprint.
- **Consequences:** Precise, privacy-safe change detection without storing the prompt; changing canonicalization requires an input-policy version bump.
- **Status:** Final.

## AIS-ADR-007 — Derived `stale` presentation state

- **Context:** PostgreSQL constraints cannot automatically update the summary whenever metadata changes, and persisted state can drift.
- **Decision:** Derive `stale` whenever a successful row's fingerprint differs from the current approved-input fingerprint. A service may also persist `stale` after metadata mutation as an optimization, but reads must verify it. Custom title, note, save reason, favourite/archive state, and Space changes do not invalidate under the default policy. Metadata input changes do.
- **Alternatives:** Database triggers; eager invalidation only; silently regenerate.
- **Consequences:** Correctness survives missed events; reads do bounded hashing work. No automatic cost is incurred.
- **Status:** Final.

## AIS-ADR-008 — Usage and estimated cost

- **Context:** Cost controls require per-attempt observability without storing private prompts.
- **Decision:** Store provider-reported input/output tokens on the current attempt and an optional estimated cost in configurable minor billing units. Keep pricing configuration outside prompts and code paths that assume fixed vendor pricing. Aggregate operational attempt metrics without content.
- **Alternatives:** Provider dashboard only; exact currency decimal; detailed prompt logs.
- **Consequences:** Per-user limits and cost review are possible; estimates may be absent or differ from invoices.
- **Status:** Final principle; currency/configuration details are revisitable before production.

## AIS-ADR-009 — User notes excluded by default

- **Context:** `personal_note` and `save_reason` can contain sensitive private context and are not necessary to summarize source metadata.
- **Decision:** Exclude both by default. A later per-request checkbox, **Use my note to improve this summary**, may send `personal_note` only after explicit informed consent; its inclusion becomes part of the fingerprint and disclosure. Never treat it as objective source truth. `save_reason` needs a separately justified opt-in.
- **Alternatives:** Always send notes; account-level blanket consent; never support notes.
- **Consequences:** Strong privacy default and source-grounded summaries; some personalization is postponed.
- **Status:** Final default; explicit opt-in is revisitable.

## AIS-ADR-010 — Record model and prompt versions

- **Context:** Output quality and interpretation depend on both model and instructions.
- **Decision:** Persist provider, exact model identifier, and immutable prompt version with every successful current output. A new prompt/model does not silently invalidate existing output; user regeneration adopts current configuration.
- **Alternatives:** Store provider only; automatically regenerate all old rows; overwrite version metadata before success.
- **Consequences:** Outputs are reproducible enough for diagnosis and rollout comparison without storing raw prompts.
- **Status:** Final.

## AIS-ADR-011 — Persist bounded failure state

- **Context:** Users need retryable status across requests and restarts.
- **Decision:** Persist classified `failure_code`, bounded sanitized `failure_message_safe`, attempt time, and status. Never persist stack traces, provider bodies, prompts, or credentials. Transient failures may retry within a bounded job policy; public messages remain generic.
- **Alternatives:** Logs only; raw provider errors; delete failed rows.
- **Consequences:** Durable UX and operational diagnosis with reduced leakage; safe classifications must be maintained.
- **Status:** Final.

## AIS-ADR-012 — No raw provider-response retention

- **Context:** Raw responses may repeat source/private text, include provider diagnostics, and exceed the validated contract.
- **Decision:** Validate in memory, retain only approved normalized fields and usage metadata, then discard the raw response. Temporary privacy-safe debugging must be explicitly approved, access-controlled, time-bounded, and disabled by default.
- **Alternatives:** Store all responses; encrypted debug archive; provider-side records only.
- **Consequences:** Smaller breach and retention surface; some vendor debugging evidence is unavailable.
- **Status:** Final default.

## AIS-ADR-013 — Cascade deletion

- **Context:** Derived output must not outlive its private source.
- **Decision:** `ai_summaries.discovery_id` uses `ON DELETE CASCADE`. Account purge cascades through Discovery. Backups expire under the disclosed backup schedule; provider deletion/retention behavior must be documented in user disclosure.
- **Alternatives:** Soft-delete summaries; orphan/anonymize output; retain for analytics.
- **Consequences:** Clear user deletion semantics; historical quality analysis must use non-content aggregate metrics.
- **Status:** Final.

## AIS-ADR-014 — Future embedding compatibility

- **Context:** A later semantic-search phase may embed generated summaries, but embeddings are excluded now.
- **Decision:** Stable summary UUID, input fingerprint, generated time, model, and prompt version identify the current source version. A future embedding table can reference `ai_summaries.id` and copy a summary-content fingerprint/version. It must cascade or be invalidated on replacement. Add no vector columns or tables now.
- **Alternatives:** Preserve every summary version now; embed Discovery directly; add placeholder vector fields.
- **Consequences:** Additive future migration remains possible without speculative schema.
- **Status:** Final for this phase; future embedding design is revisitable.

## AIS-ADR-015 — Database-backed work before production

- **Context:** Provider latency exceeds normal API latency, processes restart, and there is no Redis or production worker.
- **Decision:** Local development may execute the fake provider inline or in a short in-process task. A portfolio MVP may use an in-process task only with explicit loss-on-restart limitations. Production requires durable database-backed claiming/lease polling before enabling real-provider generation. Reuse the `ai_summaries` lifecycle row as the small work record initially; do not add Redis/Celery for the first release.
- **Alternatives:** Synchronous provider request; ephemeral task as production architecture; Redis/Celery now; a separate jobs table immediately.
- **Consequences:** No new infrastructure dependency and durable recovery with PostgreSQL, but polling/leases require careful concurrency tests. A general queue can replace it at scale.
- **Status:** Final production gate; queue technology is revisitable.

## AIS-ADR-016 — Durable hashed idempotency keys

- **Context:** A single current summary row cannot detect reuse of an older POST idempotency key
  after later requests, and in-memory keys fail across restarts/instances.
- **Decision:** Use a narrowly scoped `ai_summary_idempotency_keys` table unless a reviewed generic
  facility already exists. Store a hash of the key, owner/Discovery/action scope, request-payload
  fingerprint, safe result status, and bounded expiry—never private response content or the raw key.
- **Alternatives:** Remember only the latest key on `ai_summaries`; process-memory cache; Redis now;
  omit idempotency.
- **Consequences:** Reliable replay/conflict behavior and atomic concurrency protection require one
  small operational table and scheduled expiry cleanup.
- **Status:** Final requirement; reuse of a future generic facility is revisitable.
