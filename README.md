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

## Future AI features

- AI-assisted summaries and suggested tags
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

The backend authentication foundation provides registration, login, logout, and current-user APIs.
Frontend authentication screens remain scheduled for the library-interface phase.

## Development roadmap

Development begins with product and architecture decisions, followed by application scaffolding, authentication, the core Discovery experience, and safe metadata enrichment. AI enhancements follow only after the non-AI MVP is stable. Production hardening, accessibility, monitoring, backups, and deployment complete the portfolio release. See [docs/roadmap.md](docs/roadmap.md) for phased deliverables and completion criteria.

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
- [Roadmap](docs/roadmap.md)
- [Local development](docs/local-development.md)
- [Coding-agent guidance](AGENTS.md)
