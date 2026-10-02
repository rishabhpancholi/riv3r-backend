# Changelog

This changelog is reconstructed from the repository's Git history. Dates use the
commit dates recorded in Git.

## 2026-10-02 — Provider-neutral AI clients

- Added process-wide Anthropic and Voyage AI adapters behind application-owned LLM
  and embedding interfaces.
- Added shared `get_llm` and `get_embeddings` dependencies and required API-key and
  model settings.
- Configured Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for generation and
  Voyage 4 (`voyage-4`) for embeddings through environment-backed settings.
- Moved external-client lifecycle management from `app/db` to `app/clients` and
  guaranteed cleanup during FastAPI shutdown.
- Added best-effort audit logging for successful project creation and publishing.

## 2026-10-01 — Configurable CORS origins

- Added an environment-backed allowlist of browser origins and configured CORS to
  support credentialed API requests from those origins.

## 2026-09-29 — Packaging metadata

- Pointed the project metadata at `docs/README.md` so package builds and dependency
  synchronization no longer fail because of the absent root-level README.
- Updated the Docker build inputs and ignore rules to include that package README,
  allowing remote container builds to install the project successfully.

## 2026-09-29 — Projects and organization permissions

- Added the projects schema, pgvector-ready embeddings, lifecycle states, indexes,
  validation constraints, and backend-only access rules.
- Added project creation and atomic draft-to-published transitions.
- Added extensible permission checkers: clients are tenant-scoped, while RIV3R
  organizations may operate across tenants.
- Colocated feature-specific dependency providers with their API packages.
- Added project API, service, repository, permission, and concurrency tests.
- Added product, architecture, invariant, and changelog documentation with an
  explicit policy to keep those documents synchronized with future development.

## 2026-09-28 — Atomic onboarding

- Replaced multi-request onboarding writes with transactional Supabase RPCs.
- Made organization, owner, membership, resource profile, and initial refresh-token
  creation atomic.
- Added advisory locks and authoritative duplicate checks to onboarding functions.
- Removed the profile API/service and its obsolete tests.

## 2026-09-27 — Security and repository overhaul

- Introduced repository protocols with Supabase and Redis adapters.
- Strengthened JWT claim validation, token typing, expiry handling, and revocation.
- Added backend-only RLS policies and database verification tests.
- Added cross-table duplicate checks and expanded authorization coverage.
- Added opt-in integration tests for Supabase and Redis authentication lifecycles.
- Documented storage boundaries, RLS deployment, and integration-test isolation.

## 2026-08-16 — Authentication, verification, audit, and limits

- Replaced boolean verification flags with `in_progress`, `approved`, and `rejected`
  verification states.
- Updated authentication and onboarding behavior for the new verification model.
- Added audit logs and request timing metadata.
- Added login/onboarding rate limiting and corresponding tests.
- Corrected audit-service test behavior.

## 2026-08-15 — Test and CI foundation

- Added continuous integration.
- Added API, schema, service, JWT, password, and validator tests.
- Added reusable FastAPI test fixtures.

## 2026-08-12 — Initial backend

- Created the FastAPI application and health, onboarding, authentication, and profile
  foundations.
- Added Supabase and Redis connectivity, JWT/password helpers, middleware, and error
  handling.
- Added the initial users, organizations, memberships, refresh tokens, and resources
  schema with relationships and triggers.
