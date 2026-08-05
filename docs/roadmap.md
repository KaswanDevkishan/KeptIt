# KeptIt Development Roadmap

Implementation note (2026-08-05): Semantic Search now also supports optional deployable Gemini
embeddings through the official `google-genai` SDK, `gemini-embedding-001`, 1,536 output dimensions,
and retrieval document/query task types. Fake remains the automated-test default; provider changes
require re-indexing and matching provenance prevents vector-space mixing. Existing production gates
remain unchanged.

Implementation note (2026-08-05): optional manual AI Summaries are implemented behind
disabled-by-default flags with a deterministic fake, optional OpenAI adapter, owner-scoped API,
current-row deletion, derived staleness, quota/cooldown controls, and library-card UI. Production
enablement remains blocked on the worker and operational/privacy gates in the normative AI plan.
All later AI features remain postponed.

Each phase should remain deployable and reviewable. A phase is complete only when its criteria are met and applicable automated checks pass.

## Phase 0 — Product and repository foundation

**Goal:** Establish a shared product definition, architectural direction, and safe repository baseline.

**Deliverables:**

- Product definition and MVP boundaries
- Architecture documentation
- Repository foundation, agent guidance, and ignore rules

**Completion criteria:**

- README, product specification, architecture, and roadmap agree on scope and terminology.
- KeptIt is named consistently and semantic search is explicitly excluded from MVP.
- Repository hygiene rules cover secrets, generated artifacts, uploads, and local databases.
- No backend or frontend application code has been introduced.

## Phase 1 — Application scaffolding

**Goal:** Create a minimal, testable full-stack development environment.

**Deliverables:**

- FastAPI backend and React/Vite/TypeScript frontend scaffolding
- Health-check endpoint
- PostgreSQL connection and initial Alembic configuration
- Documented local development setup and safe example environment files
- Baseline formatting, linting, type checking, and test commands

**Completion criteria:**

- Both applications start locally from documented commands.
- The health endpoint reports application health without leaking internal details.
- A migration can run against a local PostgreSQL database.
- Baseline backend and frontend tests and quality checks pass in a clean checkout.

## Phase 2 — Authentication and protected access

**Goal:** Establish secure identity and private application boundaries.

**Deliverables:**

- Initial database migration containing only the User and server-side User Session schema
- User persistence model
- User registration
- Login and logout
- Secure password hashing and revocable, opaque-cookie session management
- Protected current-user API endpoint
- Separate authentication and authorization foundations
- Backend tests for registration, login, logout, session expiry/revocation, and protected access

**Completion criteria:**

- The reviewed Alembic migration creates only the authentication tables and can upgrade and downgrade in an isolated PostgreSQL test database.
- A user can register, log in, call the protected current-user endpoint, and log out.
- Invalid or expired sessions are rejected safely.
- Passwords and tokens never appear in application logs or API responses.
- Backend tests cover credential validation, duplicate registration behavior, session lifecycle, CSRF behavior where applicable, and protected endpoint access.
- No Discovery, Space, Tag, metadata, or frontend feature is implemented in this phase.

## Phase 3 — Discovery capture and Spaces organization

**Goal:** Establish the private non-AI core for preserving and organizing Discoveries.

**Deliverables:**

- Discovery, Space, and Space Membership migrations and models
- URL saving, validation, normalization, and duplicate detection
- Automatic platform detection
- Optional custom title, personal note, and save reason
- Edit, archive, restore, and delete actions
- Spaces
- Ownership enforcement across all resources

**Completion criteria:**

- Supported platform and representative generic URLs are detected and saved correctly.
- Equivalent URLs produce a clear per-user duplicate conflict, including under concurrent requests.
- Archive remains reversible, permanent deletion cascades dependent private data, and archived Discoveries still prevent duplicates.
- Cross-user authorization and backend persistence/API tests pass for Discoveries and Spaces.

**Discovery MVP status:** The private Discovery capture, retrieval, search/filter, edit,
favourite, archive/restore, and delete slice is implemented by revision `20260805_0003`. Spaces and
Tags remain intentionally postponed under the narrower Discovery MVP scope; no organization or
future-feature tables were created.

**Metadata enrichment status:** Revision `20260805_0004` adds the single current Metadata Record
and owner-triggered enrichment. Generic HTML, GitHub public repositories, optional official
YouTube metadata, safe unsupported states, SSRF controls, retry, and library presentation are
implemented. A durable worker, scheduling, distributed rate limits, and network-level egress
controls remain production follow-up.

**Spaces status:** Revision `20260805_0005` adds private owner-scoped Spaces and memberships with
database-enforced tenant consistency. Create/list/read/rename/delete, idempotent assignment,
removal, Space contents, and the responsive library UI are implemented. Tags remain postponed.

**Spaces design status:** The production schema, ownership enforcement, API, UX, migration, security,
scalability, and test plan are recorded in the
[Spaces feature implementation plan](spaces-implementation-plan.md), consistent with the completed
implementation.

## Phase 4 — Library retrieval and interface

**Goal:** Make the Discovery library useful and accessible across supported web viewports.

**Deliverables:**

- Responsive Discovery library and detail/edit experiences
- Keyword search, platform filtering, Space and tag filtering, archive filtering, and stable pagination
- Favourite, archive, restore, and explicit delete interactions
- Registration and login interface plus protected navigation

**Completion criteria:**

- Core authentication, saving, organization, search, edit, archive, and delete journeys work on defined mobile and desktop viewports.
- Search and filters return stable, paginated, owner-scoped results.
- Critical frontend/backend workflow and accessibility tests pass.

**Discovery MVP status:** The responsive authenticated library, save/edit dialogs, empty state,
keyword/platform/archive/favourite filters, feedback, and destructive confirmation are complete.
Space and one-Tag filtering and membership controls are implemented.

## Phase 5 — Safe metadata enrichment

**Goal:** Improve Discovery source context without weakening reliability, privacy, or platform compliance.

**Deliverables:**

- Page titles, descriptions, and permitted thumbnails
- YouTube metadata through an approved mechanism
- Safe generic webpage metadata processing
- Bounded enrichment statuses, retries, and failed-metadata handling
- SSRF protections, timeouts, redirect limits, size limits, sanitization, and provider rate controls

**Completion criteria:**

- URL saving succeeds even when every metadata provider is unavailable.
- Approved sources enrich representative Discoveries and attribution links remain intact.
- Failure states are observable and understandable without exposing sensitive provider data.
- Security tests cover private addresses, malicious redirects, unsafe content types, and oversized responses.
- No copyrighted video is downloaded or hosted.

## Phase 6 — Optional AI Summaries

**Goal:** Add source-grounded generated understanding without making AI part of core storage or the
Discovery save path.

**Deliverables (only):**

- AI Summary database migration with one current owner-scoped dependent row per Discovery
- Small provider abstraction and deterministic fake development provider
- One optional real-provider adapter
- Explicit manual generation endpoint; retry and confirmed regeneration behavior
- Separate responsive AI Summary UI for every lifecycle state
- Usage and configurable estimated-cost tracking plus quotas/cooldowns/feature flags
- Backend, frontend, migration, authorization, concurrency, privacy, and prompt-injection tests
- AI Summary implementation, database, API, prompt, privacy, operations, and rollout documentation

**Completion criteria:**

- AI output never overwrites user-authored content, fetched metadata, operational state, or Space
  membership, and every existing non-AI workflow passes unchanged.
- Metadata is treated as bounded untrusted prompt data; notes/save reasons are excluded by default;
  provider keys remain backend-only; local startup and normal use require no provider.
- Generation is manual, non-blocking, owner-scoped, idempotent, cost-limited, observable, and
  durable before real-provider production rollout.
- No embeddings, semantic search, automatic Tags, Memory Threads, or rediscovery capability is
  introduced.

See the [AI Summaries implementation plan](ai-summaries-implementation-plan.md).

## Phase 7 — Private Tags

**Goal:** Add lightweight, user-controlled subjects that organize Discoveries across Spaces.

**Deliverables (only):**

- Tags Alembic migration
- Tag and Discovery Tag persistence models
- Owner-scoped Tag API
- Idempotent Tag membership API
- Bounded Tag summaries in Discovery responses
- Responsive Tag management and assignment UI
- One-Tag library filtering composed with existing filters
- Backend, frontend, migration, authorization, concurrency, cascade, and regression tests
- Updated Tags implementation, database-decision, API, architecture, schema, ER, and product docs

**Completion criteria:**

- Per-user normalized names and every same-owner membership are enforced in PostgreSQL and the
  service; another User's resources always appear not found.
- Deleting a Tag removes memberships and never deletes or changes Discoveries.
- Tag management, assignment, chips, and one-Tag filtering work accessibly on supported desktop and
  mobile viewports and compose predictably with Space and existing filters.
- The migration upgrades/downgrades cleanly on PostgreSQL, all new tests pass, and existing auth,
  recovery, Discovery, metadata, Spaces, and AI Summary behavior remains passing.
- No automatic/suggested Tags, semantic search, embeddings, Memory Threads, rediscovery, sharing,
  collaboration, or browser-extension functionality is introduced.

See the [Tags implementation plan](tags-implementation-plan.md),
[database decisions](tags-database-decisions.md), and [API contract](tags-api-contract.md).

## Phase 8 — Private Semantic Search

**Goal:** Add optional meaning-based retrieval while preserving keyword search and every existing
owner-scoped filter.

**Implemented portfolio MVP deliverables (disabled by default):**

PostgreSQL/pgvector exact cosine retrieval, hybrid keyword fallback, manual indexing, bounded inline
backfill, and Meaning-mode UX are implemented for portfolio use. Durable production workers and
queues, persistent distributed quotas, IP/user rate limiting, cursor pagination, private-context
preferences, HNSW, monitoring, budgets, and alerting remain postponed production blockers.

- pgvector Alembic migration
- Separate one-current-row Discovery Embedding table
- Deterministic fake embedding provider
- One optional real embedding provider
- Versioned privacy-reviewed embedding document construction
- Owner-scoped indexing, retry, status, and bounded backfill endpoints
- Owner-scoped semantic/hybrid search endpoint composed with existing filters and keyword fallback
- Responsive accessible frontend search mode, privacy disclosure, and indexing progress UX
- Feature/provider flags, quotas, usage/cost tracking, budgets, and kill switch
- Backend, frontend, migration, authorization, concurrency, relevance, privacy, and regression tests
- Semantic Search implementation, database-decision, API, document, operations, and rollout documentation

**Completion criteria:**

- Every result belongs to the authenticated User; raw vectors never leave the backend; provider
  keys remain server-only; Discovery/account deletion cascades embeddings.
- The default document policy excludes notes, save reasons, Tags, and Spaces unless explicit
  private-context consent is enabled; input fingerprints and model/dimension changes drive staleness.
- Exact cosine search is proven before HNSW is considered, and no separate vector database is
  introduced without measured need.
- Hybrid retrieval preserves keyword-only Discoveries and Space, Tag, platform, favourite, and
  archive filters, with a clear keyword fallback on disablement/outage/no confident semantic match.
- Indexing never blocks Discovery creation; fake/local behavior needs no key; real-provider
  production waits for a durable worker, distributed rate limits, privacy approval, and budgets.
- All new and existing applicable tests pass and representative relevance fixtures demonstrate a
  useful gain without unacceptable exact-title regression.

Chat/RAG answers, Memory Threads, rediscovery, recommendations, sharing, automatic Tags/Spaces,
browser extensions, public search, and non-text embeddings are explicitly outside this phase. See
the [Semantic Search implementation plan](semantic-search-implementation-plan.md),
[database decisions](semantic-search-database-decisions.md),
[API contract](semantic-search-api-contract.md), and
[document specification](semantic-search-document-spec.md).

## Phase 9 — Capture and portability

**Goal:** Make KeptIt easier to use wherever links are discovered and keep user data portable.

**Deliverables:**

- Browser extension
- Mobile sharing integration
- Progressive Web App capabilities
- Validated import and export workflows

**Completion criteria:**

- Extension and mobile-share saves use the same authenticated, validated API rules as the web app.
- PWA behavior has documented browser support and safe cache handling for private data.
- Export produces a documented, portable format.
- Imports are previewable, idempotent where practical, and report invalid or duplicate records without losing valid entries.

## Phase 10 — Production and portfolio release

**Goal:** Harden, operate, deploy, and clearly present a production-ready portfolio application.

**Deliverables:**

- Production security review and hardening
- Rate limiting
- Monitoring and alerting
- Automated backups and tested restoration
- CI/CD with gated migrations and rollback procedures
- Accessibility audit and remediation
- Production deployment
- Portfolio documentation, architecture decisions, screenshots, and demonstration material

**Completion criteria:**

- Security review findings are resolved or explicitly risk-accepted and documented.
- Rate limits protect sensitive and costly endpoints without blocking normal workflows.
- Service and database alerts are actionable, and backup restoration is proven.
- CI blocks failing tests, checks, unsafe migrations, and broken production builds.
- Critical flows meet the stated accessibility target.
- The deployed service passes smoke tests and has documented incident and rollback procedures.
- Portfolio documentation explains product choices, tradeoffs, testing, security, and operations without exposing secrets or user data.

**Deployment-readiness status (2026-08-06):** Baseline private-beta deployment configuration is
implemented: Render web/static services, Neon/pgvector and controlled Alembic guidance, liveness
and database readiness, production environment validation, cross-site cookie/CORS policy, SPA
routing, security/cache headers, and deployment/rollback checklists. No cloud deployment was
performed and Phase 10 is not complete.

Remaining blockers stay visible: production password-reset email delivery; durable metadata/AI/
embedding workers; distributed IP/user rate limiting; monitoring and alerting; automated backups
and tested restoration; export and account deletion; accessibility and security audits; incident
response; secret rotation; provider privacy/legal review and consent; budgets; terms, privacy
policy, and other legal documents. A hosted private beta must not be described as production-grade
until these controls are implemented and verified.
