# Deployment rollback

Pause automatic deploys before incident work. Preserve evidence without copying private content or
secrets into tickets. Disable `SEMANTIC_SEARCH_ENABLED`, `AI_SUMMARIES_ENABLED`, and both real-
provider enablement flags first as emergency kill switches; rotate a suspected provider key and
stop any separately deployed worker. Keyword search and core saves remain available.

For frontend-only incidents, use Render's rollback to the last known-good static deployment, then
repeat route, API-origin, auth, and cache smoke tests. For backend incidents, roll back to a code
version compatible with the current database. Confirm `/health`, `/readiness`, authentication,
save, and ownership checks before resuming traffic/autodeploy.

Database rollback is not the default response. Take/verify a backup first. Review the exact
Alembic downgrade SQL, locks, data loss, extension dependencies, and compatibility with both old
and new application versions. Additive migrations should normally remain while application code
rolls back. Never downgrade a migration after it has accepted user data unless data loss is an
explicit approved decision. Irreversible or destructive migrations require a forward fix or a
tested restore into a new database followed by a controlled connection switch.

If the migration failed before traffic moved, Render's pre-deploy step keeps the new version from
serving. Diagnose using safe server logs, correct the migration/configuration, and redeploy. The
manual fallback is `DATABASE_MIGRATION_URL='<direct-url>' uv run alembic upgrade head` from
`backend/`; do not run it concurrently from multiple workers or shells.
