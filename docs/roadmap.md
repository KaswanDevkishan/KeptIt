# KeptIt Development Roadmap

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

## Phase 3 — Discovery capture and organization

**Goal:** Establish the private non-AI core for preserving and organizing Discoveries.

**Deliverables:**

- Discovery, Space, membership, Tag, and Discovery Tag migrations and models
- URL saving, validation, normalization, and duplicate detection
- Automatic platform detection
- Optional custom title, personal note, and save reason
- Edit, archive, restore, and delete actions
- Spaces and tags
- Ownership enforcement across all resources

**Completion criteria:**

- Supported platform and representative generic URLs are detected and saved correctly.
- Equivalent URLs produce a clear per-user duplicate conflict, including under concurrent requests.
- Archive remains reversible, permanent deletion cascades dependent private data, and archived Discoveries still prevent duplicates.
- Cross-user authorization and backend persistence/API tests pass for Discoveries, Spaces, and tags.

**Discovery MVP status:** The private Discovery capture, retrieval, search/filter, edit,
favourite, archive/restore, and delete slice is implemented by revision `20260805_0003`. Spaces and
Tags remain intentionally postponed under the narrower Discovery MVP scope; no organization or
future-feature tables were created.

**Metadata enrichment status:** Revision `20260805_0004` adds the single current Metadata Record
and owner-triggered enrichment. Generic HTML, GitHub public repositories, optional official
YouTube metadata, safe unsupported states, SSRF controls, retry, and library presentation are
implemented. A durable worker, scheduling, distributed rate limits, and network-level egress
controls remain production follow-up.

**Spaces design status:** The production schema, ownership enforcement, API, UX, migration, security,
scalability, and test plan are complete in the
[Spaces feature implementation plan](spaces-implementation-plan.md). Implementation remains pending;
it must not change authentication or existing Discovery behavior.

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
Space and Tag filtering remain postponed.

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

## Phase 6 — Memory behaviour and AI-assisted discovery

**Goal:** Add private memory behaviour and grounded intelligence after the non-AI product is stable.

**Deliverables:**

- AI summaries and automatic tag suggestions
- Carefully scoped revisit history and rediscovery feedback
- Discovery connections and Memory Threads backed by explainable relational records
- Versioned embedding pipeline and pgvector storage
- Semantic search
- Hybrid keyword and semantic ranking
- An “ask my library” experience grounded in owned Discoveries

**Completion criteria:**

- AI features are opt-in or clearly disclosed, with documented provider and data handling.
- Indexing is repeatable, versioned, observable, and updated or removed with source data.
- Authorization filters prevent any cross-user retrieval before ranking or generation.
- Evaluation fixtures demonstrate useful gains over keyword-only search for agreed queries.
- The product degrades safely when AI services are unavailable and never fabricates saved sources.

## Phase 7 — Capture and portability

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

## Phase 8 — Production and portfolio release

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
