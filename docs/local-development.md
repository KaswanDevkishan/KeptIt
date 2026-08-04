# Local development

KeptIt Phase 1 runs as three local processes: PostgreSQL in Docker, the FastAPI backend, and the Vite frontend. Python 3.11+, Node.js 20+, npm, and Docker Compose are expected.

## 1. Start PostgreSQL

From the repository root:

```bash
cp .env.example .env
docker compose up -d postgres
```

Only PostgreSQL runs in Docker. Its data is stored in the `keptit_postgres_data` named volume.

## 2. Install and run the backend

Using `uv`:

```bash
cd backend
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The API is available at <http://localhost:8000>, its development documentation at <http://localhost:8000/docs>, and its health endpoint at <http://localhost:8000/api/v1/health>.

The health endpoint reports process health only and deliberately does not query PostgreSQL. This keeps it usable during startup and makes its test independent of a database. Database readiness can be checked separately with `docker compose ps`.

Run backend checks from `backend/`:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```

Apply formatting with `uv run ruff format .`.

## 3. Install and run the frontend

In another terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The frontend is available at <http://localhost:5173>. In development only, its footer displays the current API connection status.

Run frontend checks from `frontend/`:

```bash
npm test
npm run lint
npm run format:check
npm run build
```

Apply formatting with `npm run format`.

## Configuration

Backend settings are loaded from `backend/.env` using Pydantic Settings. `CORS_ORIGINS` is a JSON array so origins remain an explicit allowlist. Frontend variables exposed to browser code must use Vite's `VITE_` prefix. The committed example files contain local-only placeholder credentials; do not put real credentials in them.

When the first database model is introduced, create a migration from `backend/` with:

```bash
uv run alembic revision --autogenerate -m "describe schema change"
uv run alembic upgrade head
```

Review every generated migration before applying it. Phase 1 intentionally has no schema revision because it defines no models.

## Stop local services

Stop the application processes with `Ctrl+C`, then stop PostgreSQL from the repository root:

```bash
docker compose down
```

This preserves the database volume. Use `docker compose down --volumes` only when you intentionally want to delete all local PostgreSQL data.
