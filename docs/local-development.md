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

### Exercise password recovery locally

The default `EMAIL_BACKEND=development_file` performs no network calls. To test recovery:

1. Open `/forgot-password`, enter the registered account email, and submit. The page always shows
   the same success message, including for unknown and inactive accounts.
2. Open the newest JSON line in `backend/.local/password-reset-outbox.jsonl` and copy its
   `reset_url`. This ignored file intentionally contains a live development-only reset link; do not
   publish, commit, or use this backend in production.
3. Open the link, choose a password of 12–1,024 characters, and submit. The fragment token is kept
   only in component memory and removed from the visible URL immediately.
4. Sign in with the new password. Confirm the old password and every pre-reset browser session no
   longer work.

Reset tokens expire after `PASSWORD_RESET_TOKEN_LIFETIME_SECONDS` (30 minutes by default), are
single-use, and supersede earlier unused tokens. PostgreSQL stores only SHA-256 digests of the raw
tokens. Apply revision `20260805_0002` with `uv run alembic upgrade head`; its downgrade target is
the authentication revision `20260804_0001`.

Automated frontend authentication tests mock the HTTP boundary and run with the normal frontend
test command below; they do not require a running backend.

### Exercise the Discovery library

Apply Discovery revision `20260805_0003` after password recovery:

```bash
uv run alembic upgrade head
```

Then sign in at `/app`, save representative URLs, and verify search, platform/favourite/archive
filters, editing, favourite toggling, archive/restore, and confirmed permanent deletion. Save the
same URL again with a fragment or tracking parameter to verify the safe duplicate conflict. A
second account may save the same canonical URL but cannot read or mutate the first account's UUID.

Normalization version 1 lowercases scheme/host, removes default ports and fragments, converts an
empty path to `/`, removes the explicit `utm_*`, `fbclid`, and `gclid` allowlist, and sorts retained
query pairs while preserving path case and meaningful values. It rejects non-HTTP(S), credentials,
malformed/missing hosts, localhost, and literal non-global IP targets. No URL is fetched. Future
normalization changes must introduce a new version and collision-reporting migration/backfill;
existing canonical values and original URLs must not be silently overwritten.

This phase deliberately adds no Spaces, Tags, metadata fetching, thumbnails, AI, semantic search,
Memory Threads, rediscovery, sharing, extensions, or public libraries.

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
`users` and `user_sessions`. Password recovery adds only `password_reset_tokens` in the following
revision.

## Authentication security follow-up

Before public production launch, add distributed IP/account-aware rate limits for registration,
login, and password-reset requests; abuse monitoring and an account-lockout policy; email
verification; scheduled deletion of expired, used reset tokens and expired/revoked sessions; and a
real email-provider adapter with delivery monitoring. Account deletion remains deliberately
undefined. Revisit CSRF protection before supporting cross-site deployments or changing the
cookie's SameSite policy.

## Stop local services

Stop the application processes with `Ctrl+C`, then stop PostgreSQL from the repository root:

```bash
docker compose down
```

This preserves the database volume. Use `docker compose down --volumes` only when you intentionally want to delete all local PostgreSQL data.
