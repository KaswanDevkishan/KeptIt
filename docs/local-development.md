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

Authentication uses a first-party opaque session cookie. The raw token is sent only in the
`HttpOnly` cookie; PostgreSQL stores its SHA-256 digest. Local HTTP development sets
`SESSION_COOKIE_SECURE=false`. Every production environment must use HTTPS and set
`SESSION_COOKIE_SECURE=true`. Cookie name, SameSite policy, path, and duration are configurable
through the corresponding `SESSION_*` settings in `backend/.env.example`.

State-changing authentication requests reject untrusted browser origins. Production additionally
requires an `Origin` header, and `CORS_ORIGINS` must contain only the deployed first-party frontend.
This origin check is the initial CSRF control; a future cross-site client or broader cookie policy
requires a reviewed synchronizer-token or signed double-submit design before deployment.

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

For real registration and login, PostgreSQL must be running and `uv run alembic upgrade head` must
have applied the authentication migration. `VITE_API_BASE_URL` must match the backend origin (the
local default is `http://localhost:8000`), while backend `CORS_ORIGINS` and trusted-origin settings
must include the frontend origin (`http://localhost:5173` by default). Frontend API requests include
browser credentials, but JavaScript never reads or persists the opaque HTTP-only session cookie.

To exercise the authentication flow manually:

1. Open `/register`, create an account, and confirm navigation to `/app`.
2. Refresh `/app` and confirm the current-user check restores the authenticated view.
3. Log out and confirm revisiting `/app` redirects to `/login`.
4. Log back in, then verify incorrect-password and duplicate-registration messages are generic and
   actionable.

Automated frontend authentication tests mock the HTTP boundary and run with the normal frontend
test command below; they do not require a running backend.

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

Create future model migrations from `backend/` with:

```bash
uv run alembic revision --autogenerate -m "describe schema change"
uv run alembic upgrade head
```

Review every generated migration before applying it. The authentication revision creates only
`users` and `user_sessions`.

## Authentication security follow-up

Before public production launch, add rate limits for registration and login, abuse monitoring and
an account-lockout policy, email verification, password reset, and scheduled deletion of expired or
revoked sessions. Account deletion remains deliberately undefined. Revisit CSRF protection before
supporting cross-site deployments or changing the cookie's SameSite policy.

## Stop local services

Stop the application processes with `Ctrl+C`, then stop PostgreSQL from the repository root:

```bash
docker compose down
```

This preserves the database volume. Use `docker compose down --volumes` only when you intentionally want to delete all local PostgreSQL data.
