# KeptIt

> Never lose anything interesting on the internet again.

KeptIt is a personal internet memory application for saving and rediscovering useful, entertaining, or inspiring content. It keeps references to content from Instagram, YouTube, TikTok, Reddit, X, articles, recipes, GitHub, and the wider web without copying the underlying media.

## The problem

Interesting links are scattered across browser tabs, bookmarks, messages, and platform-specific save lists. Those systems are difficult to organize and even harder to search by the details a person actually remembers. Links become stale, context is lost, and useful discoveries disappear into separate services.

## The proposed solution

KeptIt provides one private, searchable library for original URLs and the context around them. A Discovery can include permitted metadata, a custom title, a personal note, Spaces, and tags. The first release focuses on a reliable URL-saving workflow and keyword discovery; later releases can add summaries and semantic retrieval.

## MVP features

- User registration, login, and logout
- Save an original URL with automatic platform detection
- Optional custom titles and personal notes
- Spaces and tags
- A responsive saved-content library
- Keyword search and platform filters
- Edit, archive, and delete Discoveries
- Duplicate-link detection

Semantic AI search is not part of the first MVP.

## Optional AI Summaries

- Optional, source-grounded AI Summaries can be generated manually from approved fetched metadata.
  The offline fake requires no key; the OpenAI adapter requires explicit server-only configuration.
  Notes, save reasons, custom titles, raw URLs, account data, and Spaces are never sent.
- Suggested tags remain later work and are not part of the AI Summaries phase.
- Embeddings stored with PostgreSQL and pgvector
- Natural-language semantic and hybrid search
- An “ask my library” experience grounded in a user's Discoveries

Examples include finding “the Japanese abandoned town video” or “the tofu recipe I saved last month” without remembering an exact title.

## Planned technology stack

| Area | Technology |
| --- | --- |
| Frontend | React, Vite, TypeScript, React Router, CSS Modules or a similarly small styling system |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | PostgreSQL |
| Testing | pytest, React Testing Library, Vitest |
| Future search | Embeddings, pgvector, hybrid keyword and semantic search |
| Deployment | Render or another suitable production platform |

## Planned repository structure

```text
keptit/
├── backend/              # FastAPI application
├── frontend/             # React application
├── docs/
│   ├── architecture.md
│   ├── product-spec.md
│   └── roadmap.md
├── .gitignore
├── AGENTS.md
└── README.md
```

Phase 1 provides the application foundation, health check, database configuration, and a polished landing page. Product features begin in later phases.

The Discovery MVP provides an authenticated private library: users can save validated public
HTTP(S) URLs, add personal context, search and filter, favourite, edit, archive/restore, and
permanently delete their own Discoveries. URL identity is normalized conservatively without
fetching third-party content, and equivalent active or archived URLs are rejected per user.

Password recovery is available through `/forgot-password`. Reset links use short-lived,
single-use opaque tokens; PostgreSQL stores only each token's SHA-256 digest. A successful reset
changes the password without signing the user in and revokes every existing session for that
account. Local development writes reset links to the ignored
`backend/.local/password-reset-outbox.jsonl` file. Production still requires a real email provider
and IP/account-aware rate limiting.

Discovery endpoints are versioned under `/api/v1/discoveries`: create and list use the collection
route; get, patch, and delete use `/{discovery_id}`; archive and restore use POST action routes. All
require the existing session cookie, owner scope, and trusted-origin protection for mutations.
Platform detection supports Instagram, YouTube, TikTok, Reddit, X/Twitter, GitHub, and
`generic_web`.

Spaces are available under `/api/v1/spaces`. They are private, owner-scoped collections: a
Discovery can belong to multiple Spaces, duplicate names are rejected after Unicode normalization,
and deleting a Space removes only its memberships. The responsive library sidebar supports Space
creation, filtering, renaming, deletion, and per-card membership controls.

Tags are implemented as private, owner-scoped descriptors with relational Discovery assignments.
Users can create, search, rename, permanently delete, attach, detach, and filter by one Tag while
combining Space and existing library filters. Discovery cards show up to three neutral Tag chips.
Names use trimmed Unicode NFKC/case-fold uniqueness; limits are 500 Tags per user and 20 per
Discovery. Deleting a Tag removes memberships only. Automatic/suggested Tags and semantic search
remain excluded.

Metadata enrichment is a separate, best-effort phase. Saving creates a `pending` metadata record;
the owner can request enrichment without changing the original URL, custom title, note, or save
reason. Generic public HTML and public GitHub repositories are supported. YouTube uses the official
Data API only when `YOUTUBE_API_KEY` is configured. Instagram, TikTok, Reddit, and X are reported as
unsupported rather than scraped. KeptIt never downloads platform videos.

## Development roadmap

Development began with product and architecture decisions, followed by application scaffolding,
authentication, the core Discovery experience, safe metadata enrichment, Spaces, and optional
manual AI Summaries. Private, user-controlled Tags with relational assignments and one-Tag library
filtering are implemented. Automatic Tags,
AI suggestions, semantic search, and embeddings remain later, separate work. See
[docs/roadmap.md](docs/roadmap.md), the [Tags implementation plan](docs/tags-implementation-plan.md),
and the [AI Summaries implementation plan](docs/ai-summaries-implementation-plan.md).

## Privacy principles

- Collect only data necessary to provide the service.
- Keep each user's library private by default and enforce ownership on every resource operation.
- Store passwords only as strong salted hashes; never log credentials, tokens, or sensitive personal data.
- Give users clear controls to edit, archive, delete, and eventually export their data.
- Define retention and deletion behavior before production launch.
- Treat notes, search queries, summaries, tags, and embeddings as private user data.

## Platform-compliance principles

- Store original URLs, permitted metadata, user-authored content, and derived organizational data.
- Do not download, reproduce, host, or redistribute copyrighted videos.
- Prefer official APIs and documented embed or metadata mechanisms where available.
- Respect platform terms, robots directives, rate limits, attribution requirements, and content removal.
- Use conservative metadata fetching with strict network protections; a failed enrichment must never prevent saving a URL.
- Link users back to the original publisher and platform.

## Local development

Prerequisites are Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, npm, and Docker Compose. Copy each safe example environment file before starting:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Start the local PostgreSQL service:

```bash
docker compose up -d postgres
```

Install and start the backend:

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Install and start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Real frontend authentication requires the backend and PostgreSQL to be running and the
authentication migration to be applied. `frontend/.env`'s `VITE_API_BASE_URL` must point to the
backend origin. The backend's CORS and trusted-origin configuration must allow the frontend origin.
Sessions use a browser-managed HTTP-only cookie; frontend code never reads or stores its value.

Run the complete baseline checks:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests

cd ../frontend
npm test
npm run lint
npm run format:check
npm run build
```

Use `uv run ruff format .` and `npm run format` to apply backend and frontend formatting. See the [local development guide](docs/local-development.md) for configuration, URLs, migration workflow, and shutdown instructions.

## Deployment

Coming soon. The initial production target is Render or another suitable managed platform, with final infrastructure selected and documented before launch.

## Project documentation

- [Product specification](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Database decisions](docs/database-decisions.md)
- [Entity relationships](docs/entity-relationship.md)
- [MVP schema](docs/mvp-schema.md)
- [Spaces feature implementation plan](docs/spaces-implementation-plan.md)
- [Roadmap](docs/roadmap.md)
- [Local development](docs/local-development.md)
- [Spaces implementation plan](docs/spaces-implementation-plan.md)
- [AI Summaries implementation plan](docs/ai-summaries-implementation-plan.md)
- [AI Summaries database decisions](docs/ai-summaries-database-decisions.md)
- [AI Summaries API contract](docs/ai-summaries-api-contract.md)
- [AI Summaries prompt specification](docs/ai-summaries-prompt-spec.md)
- [Tags implementation plan](docs/tags-implementation-plan.md)
- [Tags database decisions](docs/tags-database-decisions.md)
- [Tags API contract](docs/tags-api-contract.md)
- [Coding-agent guidance](AGENTS.md)
