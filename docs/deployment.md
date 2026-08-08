# Private-beta deployment

KeptIt's target topology is:

```text
Browser -> Render Static Site -> Render FastAPI Web Service
                                  |-> Neon PostgreSQL + pgvector
                                  `-> Gemini embedding API (backend only)
```

The frontend and API are separate origins. Only `VITE_API_BASE_URL` enters the frontend build.
`DATABASE_URL`, `DATABASE_MIGRATION_URL`, `GEMINI_API_KEY`, and all other secrets are backend-only.
The initial `onrender.com` hosts can be cross-site, so the documented pattern is an HTTP-only
session cookie with `SameSite=None; Secure`, explicit HTTPS CORS origins, credentials-enabled
requests, and mandatory trusted `Origin` checks for mutations. Do not set a cookie domain; the
host-only API cookie uses path `/` and is never readable by JavaScript.

This generated-domain configuration is compatible with desktop browsers that permit third-party
cookies, but it is **not reliable mobile authentication**. The generated hosts are different sites,
and mobile privacy controls can refuse to store or send the API cookie. `SameSite=None` permits
cross-site cookie use; it cannot override a browser's third-party-cookie blocking policy.

The production-safe topology is two HTTPS custom subdomains under one registrable domain:

```text
https://app.example.com  -> Render static site
https://api.example.com  -> Render FastAPI service
```

These remain separate origins (so credentialed CORS and trusted `Origin` checks still apply) but
are the same site. Configure `CORS_ORIGINS=["https://app.example.com"]`,
`FRONTEND_PASSWORD_RESET_URL=https://app.example.com/reset-password`,
`VITE_API_BASE_URL=https://api.example.com`, `SESSION_COOKIE_SECURE=true`, and
`SESSION_COOKIE_SAMESITE=lax`. Keep the cookie host-only without `Domain`, plus `Path=/`,
`HttpOnly`, and the bounded `Max-Age`. Render manages TLS for both custom domains. Disable the
generated Render subdomains after cutover if appropriate, then retest CORS, trusted origins, login,
refresh, and logout on the final hosts.

A same-origin `/api` reverse proxy is also sound, but Render static-site rewrites do not document a
general API reverse proxy. It requires an additional proxy/service topology, so it is not the
simpler supported option here. No custom-domain-only application code is required: the existing API
base URL, CORS allowlist, trusted-origin check, and cookie settings support sibling subdomains.

This is a private-beta topology, not a claim of production-grade operations. Password-reset email,
durable AI workers, distributed rate limiting, monitoring, tested backups, account deletion, and
legal/privacy review remain blockers.

## 1. Create and prepare Neon

1. Create a Neon project in a region near Render. Create separate least-privilege application and
   migration roles where the selected Neon plan permits it. Do not commit either credential.
2. In Neon SQL Editor, run `CREATE EXTENSION IF NOT EXISTS vector;` using an authorized role.
3. Verify with `SELECT extname FROM pg_extension WHERE extname = 'vector';`.
4. Copy the pooled TLS URL for `DATABASE_URL`. Copy the direct/unpooled TLS URL for
   `DATABASE_MIGRATION_URL`; Alembic uses this value and falls back to `DATABASE_URL` locally.
   Preserve Neon's required `sslmode=require` (or provider-supplied TLS options). Runtime pooling
   is bounded to five base connections plus two overflow connections and uses `pool_pre_ping`.
5. From a trusted release environment, test migration SQL, take/confirm a restorable backup before
   destructive migrations, then run:

   ```bash
   cd backend
   DATABASE_URL='<runtime-url>' DATABASE_MIGRATION_URL='<direct-url>' uv run alembic upgrade head
   uv run alembic current
   ```

   The documented head is `20260805_0008`. Migration `0008` creates/uses pgvector and
   `discovery_embeddings.embedding` as `vector(1536)`. Never run migrations at import time or in
   each web worker.
6. Verify the column without selecting vectors:

   ```sql
   SELECT format_type(a.atttypid, a.atttypmod)
   FROM pg_attribute a
   WHERE a.attrelid = 'discovery_embeddings'::regclass
     AND a.attname = 'embedding';
   ```

   In a non-production fixture transaction, validate cosine support with two synthetic vectors:
   `SELECT ('[1,0]'::vector(2) <=> '[1,0]'::vector(2));` and roll the transaction back.

## 2. Create the Render services

Connect the repository as a Blueprint using root [render.yaml](../render.yaml). It deliberately
defines no Render database. The backend uses Python 3.12, a frozen `uv` install, one Uvicorn worker,
`0.0.0.0:$PORT`, no reload, a pre-deploy Alembic step, and
`/api/v1/readiness` as the traffic health check. The pre-deploy command runs once per deploy before
new code serves traffic; failures fail the deploy visibly. Manual fallback is a Render Shell or
trusted release runner executing `uv run alembic upgrade head` with the same direct migration URL.

Populate every `sync: false` variable in Render's secret/config UI:

- `DATABASE_URL`: pooled Neon runtime URL.
- `DATABASE_MIGRATION_URL`: direct Neon migration URL.
- `CORS_ORIGINS`: JSON array containing only the final frontend origin, for example
  `["https://keptit-web.onrender.com"]`.
- `FRONTEND_PASSWORD_RESET_URL`: that exact origin plus `/reset-password`.
- `GEMINI_API_KEY`: backend-only key. It may be omitted while Semantic Search remains disabled.
- `VITE_API_BASE_URL` on the static site: public HTTPS API origin, without `/api/v1` or a trailing
  slash.

The Blueprint retains `SameSite=None` so the generated Render URLs remain usable in desktop
browsers that allow third-party cookies. Change it to `lax` in Render when same-site custom
subdomains are active. The Blueprint sets secure production cookies, disables the local email
backend, disables API docs, and leaves AI Summaries and Semantic Search off. Production validation
rejects insecure cookies, `SameSite` other than `Lax` or `None`, empty/HTTP/localhost frontend origins, reset URLs on another origin,
the development email outbox, default cursor secrets, incoherent real-provider configuration, and
Semantic Search enablement before its durable-worker gate is removed deliberately. AI Summaries
may use the single-process in-process executor for this private beta only.

To enable Gemini AI Summaries on the backend, set `AI_SUMMARIES_ENABLED=true`,
`AI_REAL_PROVIDER_ENABLED=true`, `AI_SUMMARY_PROVIDER=gemini`,
`AI_SUMMARY_MODEL=gemini-3.6-flash`, and a non-empty backend-only `GEMINI_API_KEY`. The Gemini key
is shared configuration only when both independently gated features use Gemini; configuring
Gemini embeddings does not enable summaries. OpenAI remains supported instead with
`AI_SUMMARY_PROVIDER=openai`, `AI_SUMMARY_MODEL=gpt-4.1-mini`, and a backend-only
`OPENAI_API_KEY` (plus the same two enablement flags).

Create the backend first, verify `GET /api/v1/health` (process liveness) and
`GET /api/v1/readiness` (database `SELECT 1`, safe `200`/`503` only), then create the static site.
After Render assigns the frontend URL, set the final CORS/reset variables and redeploy the backend.
Set the frontend API URL and rebuild. The SPA rewrite in the Blueprint makes refresh/direct
navigation work for `/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, and `/app`.
It applies only to the static site; API traffic goes directly to the backend origin.

## 3. Browser and feature verification

Use a fresh browser profile. Confirm register, login, refresh of `/app`, protected requests,
logout, and cookie attributes in browser developer tools. Requests must include credentials;
CORS must return the one requesting allowed origin plus credentials, never `*`. Test an untrusted
origin and confirm mutations fail. Verify save, duplicate detection, metadata retry, Tags, Spaces,
archive/restore, delete, and logout. Production password reset is intentionally unavailable until
a real delivery adapter exists; `EMAIL_BACKEND=disabled` silently delivers nothing and the public
flow must not be advertised as operational.

For Gemini, first satisfy the durable-worker, privacy/consent, rate-limit, budget, monitoring, and
provider-review blockers. Then set `SEMANTIC_SEARCH_ENABLED=true`,
`EMBEDDING_REAL_PROVIDER_ENABLED=true`, `EMBEDDING_PROVIDER=gemini`,
`EMBEDDING_MODEL=gemini-embedding-001`, `EMBEDDING_DIMENSION=1536`, and a non-empty backend key.
Re-index every Discovery after any provider/model/dimension change; mixed vector spaces are never
searched. Test exact titles, paraphrases, vague and multilingual queries, all relational filters,
and irrelevant queries. `SEMANTIC_SEARCH_MIN_SIMILARITY=0.35` is only a starting point and must be
evaluated with realistic private-beta fixtures. Weak matches are discarded; hybrid mode reports
keyword fallback when quota, provider, or confidence prevents semantic results.

Review logs after all smoke tests. They must not contain credentials, database URLs, cookies,
password/reset tokens, queries, notes, Tag names, embedding documents/vectors, raw provider
responses, or API keys. The initial Uvicorn command disables request access logs because raw paths
can contain private resource identifiers; error logs remain available at the configured level and
unexpected stack traces stay server-side.

## Security headers and limitations

The static site sends nosniff, no-referrer, permissions, framing, CSP, and cache headers. Vite's
hashed assets are immutable; `index.html` is not cached. HSTS is left to Render's managed HTTPS
edge. The CSP permits HTTPS images because metadata thumbnails are remote and provider-controlled;
this means thumbnail hosts still receive the browser IP. `connect-src https:` accommodates the
separate configurable API origin; narrow it to the final API hostname in the Render dashboard if
the deployment no longer needs a portable Blueprint.

## Free-tier limitations

Render free web services spin down after inactivity, have cold starts, and are unsuitable for
serious production traffic; in-process background work can be interrupted and there is no durable
worker. Expired interrupted work is converted to a safe retryable failure when the summary is next
read; work is not resumed automatically. Use one backend instance only.
Neon free usage/storage/compute and connection limits apply, and compute may suspend.
Gemini quotas are account-specific and change; availability and permanent free access are not
guaranteed. Provider outages/rate limits fall back to keyword search. Approved embedding documents
and transient semantic queries are sent to Google when Gemini is enabled.
