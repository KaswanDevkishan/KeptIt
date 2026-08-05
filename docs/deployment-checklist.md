# Deployment checklist

## Before deployment

- [ ] Production blockers and private-beta risk acceptance are reviewed.
- [ ] Neon project/region, least-privilege roles, TLS URLs, connection limits, and backups are reviewed.
- [ ] `vector` extension exists and Alembic head is `20260805_0008`.
- [ ] Migration SQL and rollback impact are reviewed; a restorable backup exists before destructive work.
- [ ] Render Blueprint validates; CI backend/frontend checks pass.
- [ ] No secret is present in Git, frontend variables, Blueprint values, logs, or build output.

## Backend

- [ ] Runtime and direct migration URLs are set in Render.
- [ ] `ENVIRONMENT=production`, `SESSION_COOKIE_SECURE=true`, and `SESSION_COOKIE_SAMESITE=none`.
- [ ] CORS is a JSON HTTPS allowlist containing only the final frontend origin.
- [ ] Password reset URL uses that origin; `EMAIL_BACKEND=disabled` until real delivery exists.
- [ ] Cursor secret is generated; docs are absent; one worker binds `$PORT` without reload.
- [ ] Pre-deploy migration succeeds; `/health` is 200 and `/readiness` is 200 without details.

## Frontend and browser

- [ ] `VITE_API_BASE_URL` is the HTTPS backend origin and the production build succeeds.
- [ ] SPA refresh works on `/`, auth routes, reset routes, and `/app`.
- [ ] Security/cache headers are present and remote thumbnails are reviewed.
- [ ] Register, login, protected refresh, save, metadata, Tags, Spaces, delete, and logout pass.
- [ ] Cookie is host-only, HttpOnly, Secure, SameSite=None, path `/`; token is absent from JavaScript.
- [ ] Allowed CORS credentials work; wildcard/untrusted/missing mutation origins fail.
- [ ] Logs contain no secrets or private content.

## AI and search

- [ ] AI Summaries and Semantic Search remain off unless every documented production gate is met.
- [ ] Gemini key is backend-only; model/dimension are `gemini-embedding-001`/1536.
- [ ] Existing Discoveries are re-indexed after provider/model changes.
- [ ] Realistic exact/paraphrase/vague/multilingual relevance and all filters are tested.
- [ ] Keyword fallback is verified for disabled provider, quota/rate limit, outage, and weak matches.
