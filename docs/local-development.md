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

The current head includes Tags revision `20260805_0007`. Existing Discoveries begin untagged.
Semantic Search revision `20260805_0008` requires PostgreSQL with the `vector` extension. Enable
`SEMANTIC_SEARCH_ENABLED=true` with `EMBEDDING_PROVIDER=fake` for deterministic offline indexing.
Indexing is manual and creation never waits. The default document excludes notes, save reasons,
Tags, Spaces, URLs, and account data. Real-provider production remains blocked on a durable worker,
distributed controls, budgets, monitoring, and provider privacy approval.
The fake provider is intended for local tests. PostgreSQL uses exact pgvector `<=>` cosine search;
SQLite semantic ranking is test-only. Keyword mode and hybrid fallback remain available when the
feature/provider is off. Backfill is bounded and inline for this portfolio build. Cursor pagination,
private-context inclusion, HNSW, durable queues/workers, distributed quotas/rate limits, and
production monitoring/budgets/alerts are postponed.
For local browser verification, create Unicode-equivalent names, assign several Tags, combine one
Tag with Space/search/platform/favourite/archive filters, and delete a Tag while confirming its
Discoveries remain. Tag names and searches are private: do not persist them in browser storage,
log them, or send them to the AI Summary provider.

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

### Exercise metadata enrichment

Apply revision `20260805_0004`, save a Discovery, and use **Retry metadata** when its source details
are unavailable. The create response remains successful and initially returns nested metadata with
`pending` status. Generic HTML and GitHub repository enrichment need no secret. YouTube requires an
optional server-only `YOUTUBE_API_KEY`; without it, YouTube is safely marked unsupported.
Instagram, TikTok, Reddit, and X are not scraped.

Remote thumbnails load directly in the browser with `Referrer-Policy: no-referrer`; their host
still learns the browser IP and request. Metadata limits use the `METADATA_*` variables in
`backend/.env.example`. Never put provider keys in frontend variables.

### Exercise Spaces

Apply revision `20260805_0005`, sign in, and create a Space from the **My Spaces** sidebar. Assign
one Discovery to multiple Spaces from its **Add or remove Spaces** control, open each Space to
verify filtering, then rename and delete a Space. Confirm deletion removes the Space but leaves its
Discoveries in **All Discoveries**. A second account must not be able to read or mutate the first
account's Space or create a membership using either account's foreign resource UUID.

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

## Manual Gemini embedding check

Gemini is optional and uses the official `google-genai` SDK; no local ML model is required. Never
commit a key. Put `GEMINI_API_KEY` only in `backend/.env`, then set:

```dotenv
SEMANTIC_SEARCH_ENABLED=true
EMBEDDING_REAL_PROVIDER_ENABLED=true
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=1536
```

Restart the backend, re-index old Discoveries with the existing action, then search an exact title,
a paraphrase, and a vague remembered description. Verify Keyword mode still works and fake rows
show stale/not indexed until re-indexed; Gemini queries must never retrieve fake or OpenAI rows.
The approved Discovery text and each transient semantic query are sent to Google's Gemini API.
Notes, save reasons, Tags, Spaces, raw URLs, URL paths/query parameters, account/session data, and
internal IDs remain excluded. Queries and vectors are not logged, persisted, or exposed.

Free-tier eligibility and quotas are account-specific and may change. Production needs reviewed
quotas, rate limits, budgets, privacy terms, monitoring, and the documented durable worker gate.
Missing keys do not prevent startup, fake mode, Keyword mode, or other features.

## Stop local services

Stop the application processes with `Ctrl+C`, then stop PostgreSQL from the repository root:

```bash
docker compose down
```

This preserves the database volume. Use `docker compose down --volumes` only when you intentionally want to delete all local PostgreSQL data.
# Optional AI Summaries MVP

Apply Alembic revision `20260805_0006`, then set `AI_SUMMARIES_ENABLED=true` and
`AI_SUMMARY_PROVIDER=fake` for deterministic, network-free manual generation. The fake behavior
setting supports success, insufficient data, failure, timeout, rate limiting, unavailable,
unsupported, and malformed-output simulations. OpenAI requires `AI_REAL_PROVIDER_ENABLED=true`
and a server-only `OPENAI_API_KEY`. Gemini summaries use the existing official `google-genai`
dependency and require `AI_REAL_PROVIDER_ENABLED=true`, `AI_SUMMARY_PROVIDER=gemini`,
`AI_SUMMARY_MODEL=gemini-2.5-flash`, and a server-only `GEMINI_API_KEY`; no frontend AI
configuration is needed. All quota, concurrency, cooldown, retry, timeout, token, and cost-rate settings are listed
in `backend/.env.example`; blank rates produce a null cost estimate.

Only source metadata title, description, site, publisher, published date, platform, and canonical
hostname are provider inputs. Notes, save reasons, custom titles, raw URLs, identifiers, sessions,
and Spaces are excluded. Static higher-priority instructions treat metadata as untrusted and forbid
browsing, tools, link following, unsupported claims, sensitive-attribute inference, and unnecessary
copying. Summary deletion is available as a privacy control.

The portfolio executor is an in-process background task backed by lifecycle/claim fields. A process
restart can interrupt it. A separately deployed lease-polling worker, distributed abuse controls,
monitoring, provider privacy review, user disclosure approval, and budgets remain production
blockers. Semantic search, embeddings, Tags, Memory Threads, rediscovery, sharing, OCR,
transcription, downloads, and public summaries are explicit non-goals.
