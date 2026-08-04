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

- User registration
- Login and logout
- Secure password hashing and session management
- Protected API and frontend routes
- Separate authentication and authorization foundations

**Completion criteria:**

- A user can register, log in, access a protected screen, and log out.
- Invalid or expired sessions are rejected safely.
- Passwords and tokens never appear in application logs or API responses.
- Automated tests cover credential validation, session lifecycle, CSRF behavior where applicable, and protected-route access.

## Phase 3 — Core saved-content MVP

**Goal:** Deliver the complete non-AI workflow for saving, organizing, and finding links.

**Deliverables:**

- URL saving, validation, normalization, and duplicate detection
- Automatic platform detection
- Responsive saved-content library
- Edit, archive, restore, and delete actions
- Collections and tags
- Keyword search, platform filtering, archive filtering, and pagination
- Ownership enforcement across all resources

**Completion criteria:**

- All MVP user journeys work on defined mobile and desktop viewports.
- Supported platform and representative generic URLs are detected and saved correctly.
- Equivalent URLs produce a clear per-user duplicate conflict, including under concurrent requests.
- Search and filters return stable, paginated, owner-scoped results.
- Cross-user authorization and critical frontend/backend workflow tests pass.

## Phase 4 — Safe metadata enrichment

**Goal:** Improve saved-item context without weakening reliability, privacy, or platform compliance.

**Deliverables:**

- Page titles, descriptions, and permitted thumbnails
- YouTube metadata through an approved mechanism
- Safe generic webpage metadata processing
- Bounded enrichment statuses, retries, and failed-metadata handling
- SSRF protections, timeouts, redirect limits, size limits, sanitization, and provider rate controls

**Completion criteria:**

- URL saving succeeds even when every metadata provider is unavailable.
- Approved sources enrich representative items and attribution links remain intact.
- Failure states are observable and understandable without exposing sensitive provider data.
- Security tests cover private addresses, malicious redirects, unsafe content types, and oversized responses.
- No copyrighted video is downloaded or hosted.

## Phase 5 — AI-assisted discovery

**Goal:** Add private, grounded natural-language discovery after the MVP is stable.

**Deliverables:**

- AI summaries and automatic tag suggestions
- Versioned embedding pipeline and pgvector storage
- Semantic search
- Hybrid keyword and semantic ranking
- An “ask my library” experience grounded in owned saved items

**Completion criteria:**

- AI features are opt-in or clearly disclosed, with documented provider and data handling.
- Indexing is repeatable, versioned, observable, and updated or removed with source data.
- Authorization filters prevent any cross-user retrieval before ranking or generation.
- Evaluation fixtures demonstrate useful gains over keyword-only search for agreed queries.
- The product degrades safely when AI services are unavailable and never fabricates saved sources.

## Phase 6 — Capture and portability

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

## Phase 7 — Production and portfolio release

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
