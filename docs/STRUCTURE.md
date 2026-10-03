# RIV3R Low-Level Design

This document describes how the backend is assembled and where future code belongs.
Read it together with [TRUTH.md](TRUTH.md) before adding or changing an API.

## Runtime topology

```text
Client
  -> FastAPI routes and dependencies
  -> application services
  -> repository protocols
  -> Supabase/PostgreSQL or Redis adapters

PostgreSQL
  -> relational constraints and triggers
  -> transactional onboarding RPCs
  -> backend-only RLS boundary
```

`app.main` creates one Supabase async client, one Redis client, one Anthropic-backed
LLM adapter, and primary/fallback Voyage embedding adapters for the process. They
are stored on `app.state.connection` during the FastAPI lifespan. Closeable
resources are released on shutdown; repository instances are lightweight
request-scoped wrappers around the shared storage clients.

## Package responsibilities

### `app/api/<feature>`

Each feature package owns its HTTP boundary:

- `routes.py` declares paths, status codes, response models, and dependencies. It
  should translate HTTP input into one service call and contain little business
  logic.
- `schemas.py` contains request models and boundary validation. Every `Field` must
  have a useful OpenAPI description.
- `views.py` contains response models. Secrets and internal storage fields must not
  appear here.
- `dependencies.py` wires feature repositories, services, permission checkers, and
  feature-specific rate limits. It must depend on shared providers from
  `app.core.dependencies` rather than duplicating connection/authentication logic.

Current features are `auth`, `onboarding`, `projects`, and `users`.

### `app/services`

Services implement use cases and domain sequencing:

- `auth.py` handles login, refresh, and logout token behavior.
- `onboarding.py` hashes secrets, constructs identity claims, and invokes atomic
  onboarding repositories.
- `projects.py` enforces project membership, tenant, lifecycle, and
  publication-time embedding behavior.
- `project_embeddings.py` builds canonical project documents, validates Voyage
  vectors, and performs one primary-model attempt followed by one lower-tier model
  attempt.
- `users.py` authorizes organization directories, validates cached payloads, and
  coordinates cache-aside reads.
- `audit.py` resolves actor type and writes best-effort audit events.
- `duplicates.py` composes independent existence checks concurrently.

Services receive repository protocols through constructors. They must not construct
Supabase/Redis clients or import FastAPI request dependencies.

### `app/repositories`

- `contracts.py` contains narrow async `Protocol` interfaces consumed by services.
- `supabase.py` implements PostgreSQL/PostgREST storage operations and RPC calls.
- `redis.py` implements access-token revocation and fail-open organization-directory
  caching.

Repository methods own query construction and storage-specific response handling.
Business authorization belongs in services/permission checkers, but every mutation
must repeat security-critical and state-critical predicates to prevent races and
time-of-check/time-of-use bugs.

### `app/core`

- `config.py` loads cached environment-backed settings, including the
  JSON-configured list of browser origins allowed by CORS.
- `dependencies.py` exposes universal connections, shared repositories,
  provider-neutral AI clients, authentication, revocations, audit wiring, and
  duplicate-check composition.
- `permissions.py` defines async permission checkers and cross-tenant decisions.
- `exceptions.py` defines domain-aware HTTP errors.
- `exception_handlers.py` converts known errors into consistent JSON responses.
- `rate_limiter.py` implements Redis-backed fixed-window request limits.

Feature-specific providers do not belong in `app/core.dependencies`.

### Infrastructure and utilities

- `app/clients/connection.py` owns the process-wide Supabase, Redis, LLM, and
  embedding lifecycle.
- `app/clients/contracts.py` defines the provider-neutral chat and embedding
  interfaces used by application code. Concrete Anthropic and Voyage adapters keep
  SDK types and configured model names inside the clients package.
- `app/middlewares/middlewares.py` assigns request IDs and process-time headers.
- `app/utils/jwt.py` issues, hashes, and validates typed JWTs.
- `app/utils/password.py` hashes and verifies passwords.
- `app/utils/validators.py` contains reusable password, phone, and email-domain rules.
- `supabase/migrations` is the ordered, append-only database definition.

## Dependency direction

Allowed dependency flow:

```text
routes -> feature dependencies -> services -> repository protocols
                                     |              |
                                     v              v
                              core domain rules   adapters
                                                    |
                                                    v
                                            Supabase / Redis
```

Rules:

- Routes depend on service types and provider functions, never concrete storage.
- Services depend on protocols, utilities, schemas, and domain exceptions.
- Adapters may translate storage failures into stable domain errors when the database
  is the authoritative validator, as with onboarding duplicate conflicts.
- Core code must not import feature routes or feature dependency modules.
- Cross-feature infrastructure stays shared; feature orchestration stays local.

## Request flows

### Authentication

1. The route resolves `AuthService` and any rate-limit/audit dependencies.
2. Login verifies the password, issues typed access/refresh JWTs, and persists only
   the refresh-token hash.
3. `get_current_user` validates the access cookie, checks Redis revocation, reloads
   the current database user, and attaches membership ownership when relevant.
   `GET /api/auth/me` additionally resolves and returns the user's sorted effective
   permission keys through a backend-only PostgreSQL function and resolves the
   organization type for organization users. Resource users return a null type.
4. Refresh requires matching access/refresh identities and a valid stored refresh
   hash; logout revokes access in Redis and blacklists refresh in PostgreSQL.
5. Audit logging runs after the primary operation and never changes its result.

### Onboarding

1. Pydantic validates organization/resource input and cross-field rules.
2. The service hashes the password, pre-generates UUIDs and tokens, and hashes the
   refresh token.
3. One repository RPC call invokes the relevant PostgreSQL function.
4. PostgreSQL takes advisory locks, performs authoritative duplicate checks, and
   inserts all related rows—including the owner's organization-type permission
   defaults—inside `onboard_organization_atomic` in one transaction.
5. The route sets authentication cookies and attempts an independent audit entry.

### Project creation

1. `get_current_user` authenticates and reloads the user.
2. Organization eligibility runs before the effective `projects.create` permission
   lookup.
3. Clients must pass the SPOC membership check; a RIV3R decision grants cross-tenant
   access and skips it.
4. The service derives organization and creator IDs from the current user. Draft
   creation relies on SQL defaults; immediate publication supplies status/time.
5. Immediate publication attempts the primary Voyage model, then the lower-tier
   Voyage fallback; draft creation skips embedding generation entirely.
6. The repository inserts the project and any embedding provenance in one write.
7. The route attempts a best-effort `project_create` audit after success.

### Project publishing

1. The project lookup and ordered authorization run concurrently; organization
   eligibility precedes the effective `projects.publish` lookup inside authorization.
2. The service applies 404, permission, tenant, and lifecycle checks in that order.
3. After validation, the service attempts the primary Voyage model and then the
   lower-tier Voyage fallback once. Both failures are logged but do not block
   publication.
4. The repository atomically writes publication and available embedding fields in a
   conditional update requiring a non-deleted draft; a client mutation also
   requires its organization ID.
5. If no row updates, the service re-reads once to classify a concurrent deletion,
   tenant change, or lifecycle conflict accurately.
6. The route attempts a best-effort `project_publish` audit after success.

### Organization user directory

1. `get_current_user` authenticates and reloads the caller.
2. Organization-level eligibility is checked before effective `users.view` access.
   Clients receive it directly and through `projects.create`; RIV3R receives it
   directly; agency owners receive it directly while unassigned agency users are
   denied this endpoint.
3. A non-RIV3R cross-tenant request is rejected before any cache or database read;
   an explicit RIV3R target must identify an existing organization.
4. The service reads `org_users:{org_id}` from Redis, validates cached records, and
   falls back to a safe-field Supabase query on a miss or cache failure.
5. Supabase results are cached for `CACHE_TTL`. Future user create, update, delete,
   restore, or organization-transfer workflows must evict every affected key after
   successful persistence; direct database changes currently rely on TTL expiry.

## Permissions

`PermissionChecker.check()` returns a `PermissionDecision`. Checkers raise a domain
`PermissionError` when access is denied and otherwise may grant capabilities such as
`cross_tenant`. `OrderedPermissionChecker` sequences organization eligibility before
database-backed effective-permission checks and merges their decisions.

`user_has_permission` recursively resolves direct grants and dependency edges in
PostgreSQL. Permission decisions are deliberately uncached so changes take effect on
the next request. RIV3R is cross-tenant in `OrganizationLevelPermissionChecker` but
still needs the endpoint permission. A privileged decision never removes the need
for state predicates in the final database mutation.

## Concurrency and transaction boundaries

- Use `asyncio.gather` only for independent operations. Never use it as a substitute
  for a database transaction.
- Multi-row, all-or-nothing PostgreSQL workflows belong in an RPC function or direct
  database transaction.
- Read-then-write state transitions must use a conditional mutation containing the
  previously validated state and tenant predicates.
- PostgreSQL and Redis cannot share an ACID transaction. Cross-store operations must
  be idempotent and designed for retry/reconciliation.
- Audit writes are intentionally separate and best-effort.
- Primary and fallback embeddings are both 1,024-dimensional Voyage 4-series
  vectors; provenance remains stored for observability and future re-embedding.

## Error contract

Known domain exceptions produce JSON containing `message` and `detail`:

- `AuthorizationError` -> 401
- `PermissionError` -> 403
- `NotFoundError` -> 404
- `DuplicateError` and `StateError` -> 409
- `RateLimitError` -> 429
- Pydantic request errors -> 400 through the registered handler
- Unexpected errors -> generic 500 without internal details

## Testing layout

- `tests/unit` checks utilities, services, permissions, and repository query shapes.
- `tests/api` checks HTTP validation, cookies, status codes, and response contracts
  with dependency overrides.
- `tests/integration` is opt-in and exercises real Supabase/Redis behavior using
  dedicated services.
- `supabase/tests/database` validates RLS and grants directly in PostgreSQL.

Every new API should cover success, validation, authentication, authorization,
tenant isolation, state errors, storage failures, and relevant races. Database
constraints or RPCs require a live integration/database test when feasible.

## Adding or changing an API

1. Read `TRUTH.md` and this document.
2. Confirm whether the change requires a migration, transaction, permission checker,
   conditional update, audit event, or rate limit.
3. Add or update the feature's schema, view, route, dependency provider, service,
   repository protocol, and adapter only where needed.
4. Keep independent reads concurrent; keep dependent mutations ordered or atomic.
5. Add unit/API tests and integration coverage proportional to storage risk.
6. Update `CHANGELOG.md`; update `README.md`, `TRUTH.md`, and this file whenever the
   change affects their documented surface.
