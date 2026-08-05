# AI Summaries: Production Implementation Plan

## Status, assumptions, and product goal

This is the normative design for the next coding phase; no AI Summary code or schema exists yet. It assumes the implemented authentication, private Discoveries, Metadata Records, trusted-origin policy, and Spaces ownership model remain unchanged. “AI summary” means the complete generated record (summary, key points, topics, and optional named entities); “summary” alone means its concise prose field.

AI Summaries solve the loss of meaning that remains after a link has a title and description: they turn uneven source metadata into a short, scannable understanding. They follow metadata enrichment because the approved source facts are their grounding; running before enrichment would increase hallucination and make sparse output common. Clear summaries and key points support KeptIt's memory direction by helping a person recognize why a source may matter when revisiting it.

They are an optional derived enhancement, never core storage. Original URLs, user context, fetched metadata, organization, and all current workflows remain useful when AI is disabled, misconfigured, rate-limited, or unavailable. Generated output never overwrites or silently changes `custom_title`, `personal_note`, `save_reason`, favourite/archive state, Space membership, or fetched metadata.

## Scope

The first release generates from approved available metadata:

- a concise source-grounded summary;
- structured key points and topics (topics are not Tags);
- named entities only when explicitly supported by the source metadata;
- detected output language and bounded confidence;
- an explicit insufficient-data reason and uncertainty-aware wording;
- retry for eligible failures and explicit regeneration.

Prior successful history is not retained initially: no product, audit, or rollback need justifies duplicating private derived content. Regeneration preserves the current successful value until replacement succeeds. Immutable history may be introduced later only with a clear retention reason, user disclosure, deletion rules, and storage limits.

Excluded are semantic search, embeddings, automatic Tags, Memory Threads, rediscovery, library chat, recommendations, browser extensions, sharing/collaboration, public summaries, model fine-tuning, media transcription, OCR, video downloading, and full-page extraction beyond approved current metadata. Future compatibility is limited to stable IDs/fingerprints/version provenance; none of these features is designed or implemented here.

## User experience and first-release trigger

The first release is manual only. A Discovery detail view shows a separate labelled **AI summary** panel beneath fetched source metadata and before the user's personal note; a card may show a compact collapsed preview after success. User-authored fields keep their existing typography and labels. Generated content has an AI label, generation time, uncertainty cue where useful, and explanatory disclosure that approved source metadata may be sent to a third-party provider. It must never visually resemble editable personal notes.

| State | Presentation and action |
| --- | --- |
| `unavailable` | No request exists; show **Generate AI summary** only when enabled/configured and metadata is plausibly sufficient |
| `pending` | Durable request accepted; non-blocking queued indicator; Discovery remains usable |
| `processing` | First generation is underway; allow navigation and bounded polling; no duplicate action. Regeneration keeps the prior public success/stale state with a busy indicator |
| `succeeded` | Show summary, key points, topics, supported entities, language/uncertainty where useful, and explicit **Regenerate** |
| `failed` | Safe generic explanation; show **Retry** only for an eligible failure and cooldown |
| `unsupported` | Explain that the source/platform is not supported by the approved metadata policy; no provider blame |
| `insufficient_data` | Explain that available metadata cannot support a reliable summary; suggest metadata retry when applicable |
| `stale` | Keep old output visible with “Source metadata changed” and offer regeneration; never regenerate silently |

Missing metadata does not make the Discovery unusable. If title/description evidence is insufficient, generation records `insufficient_data` without a provider call where determinable. Metadata enrichment remains separately retryable. AI failures never block opening, editing, organizing, archiving, favouriting, or deleting the Discovery.

Generate, retry, and regenerate are explicit cost-generating actions with disabled duplicate-submit states. Regenerate requires confirmation and communicates that it may replace the displayed AI output, not any user or metadata field. No save, page load, metadata completion, background refresh, or deployment silently generates summaries.

## Provider abstraction and recommendation

Use a small typed boundary, not a plugin framework:

```text
SummaryProvider.generate(
  input: SummaryInput,
  options: {model, prompt_version, timeout_seconds, request_id}
) -> SummaryProviderResult
```

`SummaryInput` contains only bounded approved fields. The result contains validated-structure candidates, provider/model identifiers, usage when available, and provider request ID only transiently for safe diagnostics. The adapter supports request timeout/cancellation where its client permits and maps failures into allowlisted categories: timeout, rate limited, unavailable, authentication/configuration, safety refusal, invalid output, and unknown transient/permanent. Provider exceptions/bodies never cross the boundary.

High-level comparison (exact pricing and current limits must be verified during implementation):

| Option | Fit | Trade-offs to verify |
| --- | --- | --- |
| OpenAI | Mature Python integration, strong schema-constrained output, detailed usage, broad documentation | Retention/privacy configuration, region availability, model-specific limits and pricing |
| Anthropic | Strong instruction following and structured/tool-style schemas, good Python support | Exact schema guarantees, usage/cost mapping, regional/privacy settings |
| Gemini | Structured output and competitive model range, Google ecosystem integration | Schema subset differences, quota model, data-control terms |
| Local model | Maximum deployment control and offline potential | Hosting/operations, weaker or variable JSON reliability, hardware cost, latency, quality evaluation |

Recommend OpenAI for the optional initial real adapter because its documented strict JSON Schema
response format, granular usage reporting, Python support, and narrow HTTP/API surface minimize
first-release integration work. This is an engineering recommendation, not a quality or hype
claim. The recommendation was checked against the official
[OpenAI response-format reference](https://platform.openai.com/docs/api-reference/responses),
[usage reference](https://platform.openai.com/docs/api-reference/usage), and
[data-control documentation](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint),
including the fact that default retention and eligibility for stronger controls require deliberate
review. Gemini also documents structured JSON Schema output and explicitly requires application
validation; see its
[structured-output guide](https://ai.google.dev/gemini-api/docs/structured-output). Before
implementation, re-verify then-current rate limits, retention/training controls, regional
processing, model availability, and cost for every candidate. Anthropic or Gemini can replace
OpenAI behind the same boundary; a local model becomes appropriate only with measured quality and
operational capacity. No provider is mandatory for local startup: the feature defaults off or uses
the fake provider.

## Input data and privacy policy

Default approved inputs are the Metadata Record's source title, description, creator/publisher, published date, provider/site name when present; deterministic Discovery platform; and canonical hostname derived from the already accepted canonical URL. Each field is normalized and truncated to its prompt limit. Do not send the raw original/canonical URL.

Excluded by default and from the first release are `personal_note`, `save_reason`, email, account identifiers, user/session/reset data, internal IDs, Spaces/memberships, favourite/archive state, raw URLs/query strings, full rows, failure logs, thumbnails, provider payloads, and operational metadata. `custom_title` is also excluded because it is user-authored and source metadata is the grounding authority.

This minimizes private user disclosure and produces a source summary rather than a summary of the user's intent. A later per-generation checkbox—**Use my note to improve this summary**—may include `personal_note` only after clear provider disclosure and affirmative consent. The note must be framed as subjective context, never objective truth; inclusion must change the input fingerprint, be visible in the result provenance, and never alter the note. `save_reason` needs a separate justification and opt-in rather than piggybacking on note consent.

## Prompt strategy

Use immutable prompt identifier `ai-summary-v1` and the complete [prompt specification](ai-summaries-prompt-spec.md). Its high-priority instruction requires use of supplied material only; forbids unsupported claims, marketing language, sensitive-attribute inference, tool use/browsing, and unnecessary quotation; preserves uncertainty; limits copyrighted reproduction; treats optional notes as subjective; and returns strict JSON.

The output contains `summary`, `key_points`, `topics`, `entities`, `language`, `confidence`, and `insufficiency_reason`. Limits are: summary 600 code points; up to five 240-character key points; eight 60-character topics; ten entities with 120-character names and allowlisted types; BCP-47-like language/`und`; confidence 0–1; and a 240-character insufficiency reason. A semantic prompt/schema change creates a new prompt version. Existing rows retain their recorded version and remain readable; upgrades occur only on explicit regeneration, with no silent bulk rewrite.

## Output validation

The backend is authoritative and uses strict Pydantic/JSON Schema validation with unknown fields rejected. Parse only a JSON object; do not scrape JSON from surrounding prose. Enforce UTF-8 at the HTTP/provider client boundary, reject decoding failures, null bytes/control characters, invalid language/entity enums, non-finite or out-of-range confidence, HTML/Markdown where not allowed, maximum serialized response bytes, every string limit, and cross-field rules.

Normalize Unicode consistently, trim/collapse safe internal whitespace, convert empty strings to the allowed null/empty representation, and deduplicate topics/key points/entities using Unicode-normalized case-folded keys while preserving first order. Reject output that remains oversized after normalization. `summary: null` requires empty arrays and a non-empty insufficiency reason; a non-null summary requires a null insufficiency reason. Malformed output gets at most one identical-input structured retry; otherwise persist `invalid_provider_output`. Raw provider responses and prompts are discarded and never stored or logged.

## Relational database design

Use one current `ai_summaries` row per Discovery. All instants are UTC `timestamptz`; UUIDs follow project convention. JSONB values are application-validated bounded structures, not arbitrary provider documents.

| Field | PostgreSQL type | Null/default | Constraints | Purpose |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | not null; generated | primary key | Stable generated-record identity and future reference point |
| `discovery_id` | `uuid` | not null | FK `discoveries.id ON DELETE CASCADE`; unique | Ownership/source path and one current row |
| `status` | `varchar(32)` | not null; `pending` | check lifecycle allowlist | Durable lifecycle state; `unavailable` is absence, `stale` may be derived |
| `provider` | `varchar(64)` | null | safe identifier format/length | Adapter used for current successful/active attempt |
| `model` | `varchar(128)` | null | bounded non-secret identifier | Exact configured provider model |
| `prompt_version` | `varchar(64)` | null | version identifier format | Output instruction/schema provenance |
| `summary` | `varchar(600)` | null | length; success/stale consistency check | Concise generated prose |
| `key_points` | `jsonb` | not null; `[]` | array shape; app max 5 strings/240 chars | Ordered generated key points |
| `topics` | `jsonb` | not null; `[]` | array shape; app max 8 strings/60 chars | Generated subject phrases, never Tags |
| `entities` | `jsonb` | not null; `[]` | array shape; app max 10 typed objects | Explicitly supported named entities |
| `language` | `varchar(35)` | null | BCP-47-like/`und` check | Detected output language |
| `confidence` | `numeric(4,3)` | null | check 0–1 | Source-support confidence |
| `insufficiency_reason` | `varchar(240)` | null | status/cross-field check | Safe explanation for insufficient data |
| `input_fingerprint` | `bytea` | null | check 32 bytes | SHA-256 of canonical approved inputs/policy version |
| `generated_at` | `timestamptz` | null | required for successful output | Time current output completed |
| `last_attempted_at` | `timestamptz` | null | UTC | Cooldown/recovery/operations |
| `failure_code` | `varchar(64)` | null | safe allowlist/format | Classified last terminal failure |
| `failure_message_safe` | `varchar(240)` | null | bounded sanitized text | Non-sensitive durable explanation |
| `usage_input_tokens` | `integer` | null | check `>= 0` | Provider-reported current attempt input usage |
| `usage_output_tokens` | `integer` | null | check `>= 0` | Provider-reported current attempt output usage |
| `estimated_cost_minor_units` | `bigint` | null | check `>= 0` | Config-derived estimate in documented billing minor units |
| `attempt_count` | `smallint` | not null; `0` | check 0–configured maximum | Bounded retry/recovery control |
| `available_at` | `timestamptz` | null | required for pending retry | Earliest database-poll time |
| `processing_started_at` | `timestamptz` | null | processing-only | Stale-processing detection |
| `lease_expires_at` | `timestamptz` | null | processing-only | Worker claim recovery |
| `generation_token` | `uuid` | null | changes per accepted generation | Prevents late/cancelled worker writes |
| `created_at` | `timestamptz` | not null; current transaction time | immutable | Row creation time |
| `updated_at` | `timestamptz` | not null; current transaction time | update on mutation | Concurrency/state time |

The additional attempt/lease fields are required for the recommended database-backed production execution and should be in the same focused migration. If a separate generic jobs table exists before implementation, reevaluate them rather than duplicate queue state.

Indexes/constraints: unique `discovery_id`; partial runnable index `(available_at, created_at)` for `status='pending'`; partial lease index on `lease_expires_at` for `processing`; operational `(status, updated_at)` only if monitoring/cleanup queries need it. Cross-field checks require generated fields only in successful/insufficient shapes and failure details only where appropriate, while Pydantic remains authoritative for JSON contents. Do not add a denormalized `user_id`: ownership is enforced by joining/loading Discovery with `(discoveries.user_id, discoveries.id)` before every read/mutation; worker claims use trusted row relationships, never client IDs.

POST replay protection also requires a small content-free `ai_summary_idempotency_keys` operational
table unless a reviewed generic durable idempotency facility exists first. It stores generated UUID
`id`; non-null `user_id` and `discovery_id` foreign keys with cascade; `action` (`generate` or
`regenerate`); a SHA-256 `key_hash` rather than the client key; a request-payload fingerprint; safe
result HTTP status; and `created_at`/`expires_at`. Unique `(user_id, action, discovery_id, key_hash)`
prevents replay races, and an expiry index supports bounded deletion. It stores no prompt, output,
note, URL, provider response, or error body. Exact replay responses are reconstructed from current
owner-scoped state and safe result classification rather than storing private response payloads.

Regeneration atomically replaces current generated fields only after success. For resilience, the implementation may need temporary candidate output in memory and a short final transaction; old output remains until then. Metadata changes produce a different fingerprint and a read-time `stale` state. Custom title and all other user-field changes do not invalidate under the default input policy; note changes invalidate only in a future opt-in request that included the note. Deleting Discovery/account cascades the row. A future embedding record can reference `ai_summaries.id` plus a content/version fingerprint; no embedding schema is added now.

## Lifecycle, concurrency, and idempotency

```text
unavailable -> pending -> processing -> succeeded
                              |          |
                              |          +-> stale -> pending (explicit regenerate)
                              +-> failed -> pending (eligible retry)
                              +-> unsupported
                              +-> insufficient_data
```

`unavailable` is represented by no row. `pending` is a committed work request. A worker conditionally changes it to `processing` with a generation token and expiring lease. Success writes validated output/version/usage/fingerprint. Policy/platform impossibility becomes `unsupported`; inadequate evidence becomes `insufficient_data`; safe classified operational/provider errors become `failed`.

Only explicit requests transition terminal states back to `pending`. Automatic retry is limited to a small configured number of transient failures with bounded exponential backoff/jitter and still counts against usage/abuse controls; invalid credentials, unsupported, refusal, and invalid repeated output are not blindly retried. Regeneration from `succeeded`/`stale` keeps existing output and its public state until success, exposes a separate busy indicator, and records a safe latest-attempt error if replacement fails; it must not blank the output.

The unique Discovery constraint, transaction-level row lock or conditional update, active generation token, and idempotency record prevent duplicate generation. Concurrent first requests converge on one pending row; a second distinct request sees current work. A worker completes only if its token/lease still matches. Expired processing leases are recovered to pending until the attempt cap, then failed. Deletion/cancellation invalidates the token so late work cannot resurrect data.

The fingerprint covers exact approved normalized inputs and input-policy version. Metadata title, description, site/provider name, creator/publisher, publication date, platform, or canonical hostname changes invalidate the output. Mere Metadata Record status/timestamp changes do not if approved values are identical. Provider/model/prompt changes do not make source input stale; explicit regeneration adopts them.

## Trigger and background processing strategy

Three trigger options:

1. **Manual:** strongest cost/privacy clarity and no automatic load; selected for first release.
2. **Automatic after metadata succeeds:** convenient but surprising, costly, outage-sensitive, and requires durable orchestration; rejected now.
3. **User-configurable automatic:** best long-term control but adds settings/consent/quotas and job volume; postpone.

Never make Discovery creation or page latency wait for AI. A synchronous real-provider request is unacceptable for production due to long timeouts/retries and client disconnects. A short in-process task is convenient locally and tolerable for a clearly labelled portfolio demo, but process restarts lose work and multi-instance claims are unsafe.

The realistic first production implementation is PostgreSQL-backed polling using the lifecycle row: commit pending, claim with `FOR UPDATE SKIP LOCKED` or an equivalent conditional lease, call the provider outside the transaction, then conditionally finalize. Run the poller as a separately deployable worker process using the same code/service boundary. Local development can run a fake synchronously or enable an in-process poll loop. A portfolio MVP may document a single-process best-effort runner, but real-provider public production is blocked until the durable worker, leases, retry recovery, shutdown/cancellation, and monitoring are deployed. Redis/Celery is unnecessary now and revisitable at scale.

## API design

The precise contract is [AI Summaries API Contract](ai-summaries-api-contract.md). Owner-scoped authenticated routes are:

- `POST /api/v1/discoveries/{discovery_id}/summary` with optional `{ "use_personal_note": false }` and required `Idempotency-Key`;
- `POST /api/v1/discoveries/{discovery_id}/summary/regenerate` with `{ "confirm": true }` and required idempotency key;
- `GET /api/v1/discoveries/{discovery_id}/summary`;
- `DELETE /api/v1/discoveries/{discovery_id}/summary` as a privacy control.

Accepted durable work returns `202`, reads/current idempotent results `200`, deletion `204`, absent/foreign Discovery `404`, conflicts `409`, validation `422`, limits `429`, and disabled/misconfigured service `503`. Mutations require trusted origin. Errors use safe codes/messages/request IDs. Compact status/summary/topics nest in list responses; full output may nest in detail responses, without token/cost/provider-operational fields.

## Cost and abuse controls

- Manual generation and explicit confirmed regeneration only.
- Configurable per-user daily accepted-attempt limit, concurrent-active limit, and per-Discovery regeneration cooldown, reserved atomically.
- Production IP-aware plus account-aware endpoint limits; non-enumerating responses.
- Maximum prompt bytes and per-field caps; source description is truncated deterministically (recommended total input cap 8 KiB for v1).
- One configured economical schema-capable model; clients cannot select models.
- Provider output/token cap sized to the documented field maxima; no conversational history.
- Record provider usage and configurable cost estimate; do not hard-code or document volatile pricing.
- Short configured provider timeout, at most one structured-output retry, bounded transient retries, and no unbounded backoff loop.
- Free tier begins with a conservative configurable daily allowance and regeneration cooldown; review observed cost/quality before raising it.
- Environment feature flag defaults off, separate real-provider enable flag, server-only key, and an immediate admin kill switch that stops new claims while allowing reads/deletes.
- Provider/project budget alerts and upstream spend caps where available; quota denial occurs before provider invocation.

## Security, privacy, and retention

Provider keys exist only in backend/worker secret configuration; never frontend variables, responses, logs, database content, or committed examples. Log no raw input, prompt, personal note, metadata description, URL, raw output, provider body, credential, or token. Failure messages are allowlisted and sanitized. Metrics use coarse provider/model/status labels without user/Discovery IDs or content.

Fetched metadata is untrusted plain text. Serialize it in a distinct typed data envelope beneath fixed higher-priority instructions. The model has no tools, browser, network actions, code execution, or secrets. Validate and sanitize output, return it as plain text, and HTML-escape it in React. Do not render arbitrary Markdown; if formatting is later introduced, use an allowlist sanitizer and security tests.

User disclosure must identify that approved source metadata may be sent to a named third-party AI provider, link to relevant retention/privacy terms, state what is excluded, and offer opt-out by never generating plus deletion of generated output. The backend should use provider no-training/lowest-retention controls available under the chosen plan and document unavoidable provider-side retention. Live data cascades on Discovery/account deletion; encrypted backups age out on schedule. Account deletion must cancel pending work and invalidate leases. Before regional deployment, review provider processing regions, cross-border transfers, data-processing agreements, age/use restrictions, and applicable privacy law; regional routing is future deployment work, not assumed.

## Prompt injection and untrusted content

Webpage metadata may literally contain “Ignore previous instructions,” requests for credentials, malicious links, or model-directed commands. It is evidence text, never trusted instruction.

Mitigations are layered:

- fixed system/developer instructions state that metadata is untrusted data and cannot redefine the task;
- structured fields are JSON-escaped and delimited from instructions, never concatenated as a free-form prompt;
- length, Unicode, control-character, and content-shape validation occurs before submission;
- no model tools, browsing, link following, commands, or arbitrary URLs are enabled;
- provider structured-output mode and strict backend schema/size/enum validation are both required;
- output does not need links, HTML, Markdown, code, or commands and suspicious values are rejected/safely rendered;
- metadata instructions are never executed or echoed unnecessarily, and a model response can modify only the candidate AI row;
- raw responses cannot reach logs/UI or alter user/fetched/operational records.

Prompting reduces risk but is not the security boundary. Least capability, owner scoping, typed validation, plain-text escaping, and write isolation contain failures.

## Observability

Measure counters/rates for accepted attempts, provider invocations, successes, failures by safe category, insufficient/unsupported outcomes, retries, stale results, lease recoveries, duplicate suppression, rate-limit events, provider latency histogram, queue wait/processing duration, input/output tokens, and estimated cost. Alert on sustained success drop, latency, stuck leases, rate limits, cost anomalies, and configuration failures.

Never log/label raw metadata, metadata description, personal notes/save reasons, prompts, outputs, URLs/hostnames, email/account identifiers, sessions/reset tokens, full provider errors, request/response bodies, or high-cardinality Discovery/user IDs. Request IDs may correlate safely controlled logs; provider request IDs should be transient or tightly bounded and access-controlled if operationally essential.

## Testing strategy

Backend unit/service/API/migration tests must cover successful fake generation; schema and field normalization; malformed/oversized/non-UTF-8 provider output; timeout, rate limit, unavailable provider, invalid key/configuration, safety refusal; insufficient/unsupported metadata; injection text treated only as data; all user, metadata, favourite/archive, and Space fields unchanged; cross-user Discovery appearing not found; retry eligibility/cap; confirmed regeneration and failed-regeneration preservation; stale detection; metadata and fingerprint changes; custom title/note non-invalidation; concurrent/idempotent requests; lease recovery/late-token rejection; usage/cost recording; feature/real-provider disabled; safe errors/log redaction; DELETE and cascade; and unchanged auth, recovery, Discovery, metadata, and Spaces suites.

Frontend tests must cover unavailable/no-summary, generate, pending/processing polling, success, key points/topics/entities, failure/retry, regeneration confirmation, stale, insufficient/unsupported data, feature disabled, missing metadata guidance, safe plain-text rendering/injection strings, distinct custom title/note presentation, responsive mobile/desktop layout, keyboard/focus/live status accessibility, and all existing flows.

Use deterministic fake providers only in automated tests; never make live provider calls in CI. Migration tests run against PostgreSQL and verify upgrade/downgrade, constraints/indexes, and cascade. Concurrency tests prove at most one chargeable invocation.

## Rollout

1. Implement a deterministic development fake with success, insufficient, timeout, invalid-output, and rate-limit modes.
2. Test the real adapter locally with synthetic public metadata, a server-only key, small limits, and no committed captures.
3. Deploy schema/API/worker/UI behind disabled environment flags; reads and all non-AI behavior remain healthy.
4. Enable for limited consenting users with strict quota and budget alerts.
5. Review cost, schema-validity, source support, failure/insufficient rates, latency, privacy, and representative quality samples using synthetic/consented data.
6. Broaden only after thresholds and disclosures are approved.
7. Introduce/verify the durable worker before public scale; a real-provider production rollout cannot rely on ephemeral tasks.

## Manual testing plan

In a non-production environment with synthetic accounts/data:

1. Generate from rich title/description/publisher metadata; verify concise structured output and no other field changes.
2. Generate from sparse metadata; verify `insufficient_data` without invented claims/cost where locally detectable.
3. Use an unsupported platform/no approved metadata; verify `unsupported` and normal Discovery use.
4. Disable feature; verify controls/config-safe `503`, startup, saving, metadata, and browsing still work.
5. Configure an invalid key; verify safe failure with no key/provider body in UI/logs.
6. Simulate provider rate limit and timeout; verify bounded retry, cooldown/`Retry-After`, and no duplicate invocation.
7. Retry a transient failure; verify state transition and attempt cap.
8. Regenerate a success; verify confirmation, prior display preservation, cooldown, and atomic replacement.
9. Change metadata title/description; verify `stale`, then explicit regeneration. Change custom title/note; verify no staleness.
10. Verify personal note/save reason remain byte-for-byte unchanged and absent from provider fake capture.
11. Delete a Discovery during/after generation; verify cascade, invalidated lease, and no resurrection.
12. Attempt every route with another user's UUID; verify indistinguishable `404`.
13. Test malicious metadata containing instructions/HTML/links; verify it is treated as data and safely rendered.
14. Exercise mobile generate, polling, expanded key points, failure, retry, regenerate confirmation, and focus/status announcements.

## Completion criteria and production blockers

Implementation is complete only when:

- **Schema:** reviewed Alembic migration implements the table, checks, indexes, ownership path, cascade, upgrade/downgrade, leases, and no embeddings.
- **Provider:** typed fake plus one optional adapter pass contract/error/timeout tests; app starts and core works without a key/provider.
- **Privacy/security:** approved input allowlist, disclosure, opt-out/delete, log redaction, injection tests, backend-only secrets, provider retention review, and safe rendering are verified.
- **Cost:** atomic quotas, cooldown, caps, usage/estimate recording, timeouts/retries, feature flags, kill switch, alerts, and configurable pricing data work.
- **API/UI:** exact owner-scoped contract and every lifecycle/accessibility/responsive state work without changing existing Discovery behavior.
- **Tests/docs/manual:** all new and existing applicable suites/quality checks pass, API/prompt/operations docs match implementation, and the manual plan is recorded with outcomes.

Production remains blocked by a deployed durable worker with lease recovery; distributed/user+IP rate limiting; secret management and key rotation; provider legal/privacy/retention and regional review; user disclosure/consent copy; cost budgets/alerts/kill switch; monitoring/runbooks; backup/account-deletion verification; and representative quality/safety evaluation. Portfolio-only in-process execution must be labelled non-production.

Unresolved product decisions before coding are the exact initial schema-capable model (after current verification), per-user daily allowance, regeneration cooldown, total prompt/token cap, whether cards show full or compact output, quality thresholds, exact provider disclosure wording, provider-side retention plan/region, billing minor-unit convention, and whether DELETE should be exposed in the first UI. None blocks the architectural direction; each must become configuration or an accepted product decision before production.
