# AGENTS.md

These instructions apply to Codex and all future coding agents working in this repository.

## Working practices

- Read `README.md` and relevant files in `docs/` before changing architecture or behavior.
- Make small, focused, reviewable changes. Do not mix unrelated refactors with feature work.
- Do not silently change the documented technology stack or architectural direction. Explain the need and obtain agreement first.
- Avoid unnecessary dependencies. Prefer standard-library or existing-project capabilities and justify every new package.
- State assumptions before or alongside implementation when requirements are ambiguous.
- Preserve API compatibility unless the task explicitly requires a breaking change. Document intentional breaking changes and migration steps.
- Use Alembic migrations for every database schema change; do not rely on ad hoc schema mutation.
- Keep authentication (establishing identity) separate from authorization (checking access to a resource or action).
- Validate all user-controlled input at system boundaries and use safe, typed validation throughout.

## Quality and verification

- Add or update tests for every new or changed behavior, including relevant failure and authorization cases.
- Run the applicable tests, formatters, linters, and type checks before declaring work complete.
- Show the exact verification commands used in the completion summary.
- Report failures honestly, including whether they appear related to the change.
- Do not mark work complete while applicable tests are failing.
- If a check cannot be run, explain why and identify what remains unverified.

## Security and repository hygiene

- Never expose or commit secrets, credentials, access tokens, private keys, production data, local databases, generated uploads, virtual environments, or build artifacts.
- Keep secrets in ignored environment files or a deployment secret manager. Commit only safe example environment files with placeholder values.
- Enforce resource ownership server-side; never rely on hidden UI controls for authorization.
- Avoid logging passwords, authentication tokens, private notes, or other sensitive values.
- Treat external URLs and metadata as untrusted input. Apply request timeouts, response-size limits, content-type checks, and SSRF protections.

## Completion report

Every completed task must include:

- A concise summary of files and behavior changed
- All assumptions made
- Tests, formatters, linters, and type-check commands run, with their outcomes
- Any failures, limitations, risks, or follow-up work

Do not commit changes unless the user explicitly requests a commit.
