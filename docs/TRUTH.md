# RIV3R System Truths

This is the living checklist of invariants that future APIs must preserve. It
summarizes the current migrations and application code; if it drifts, executable
schema and code remain authoritative and this file must be corrected.

## Documentation discipline

- Read this file and `STRUCTURE.md` before designing or implementing an API.
- Every code change must add a dated, user-readable entry to `CHANGELOG.md`.
- Update `README.md` whenever capabilities, product behavior, setup, or public API
  surface changes.
- Update this file whenever a database constraint, validation rule, permission,
  lifecycle transition, security rule, or cross-service invariant changes.
- Update `STRUCTURE.md` whenever modules, dependency direction, request flow,
  persistence boundaries, or extension patterns change.
- Documentation updates are part of the same change, not deferred cleanup.

## Identity and organizations

- Organization types are `client`, `agency`, and `riv3r`.
- Verification states are `in_progress`, `approved`, and `rejected`; users and
  organizations default to `in_progress` and cannot have a null state.
- User email and organization company email are individually unique in PostgreSQL.
  Atomic onboarding also prevents case-insensitive email reuse across both tables.
- Organization website, resource portfolio URL, and resource LinkedIn URL are each
  unique in their own columns. Atomic onboarding checks URLs across all three.
- Phone numbers use E.164 syntax at the API boundary. Atomic onboarding checks for
  duplicates, but the database has no global unique phone constraint.
- An organization owner's email domain must match the company email domain.
- Resource users must have `org_id = NULL`. Non-resource users must have an `org_id`.
- Deleting an organization cascades to its non-resource users; deleting a user or
  organization cascades to organization memberships.
- Resource users cannot be inserted into `organization_members`.
- Organization membership is unique by `(organization_id, user_id)` and ownership
  is represented by non-null `is_owner`.
- Each user can have at most one resource profile (`resources.user_id` is unique).
- Organization user directories contain only non-resource, non-deleted users from
  the requested organization and never expose password or deletion fields.
- Client and agency users may view only their own organization directory. RIV3R
  organization users may view another existing organization's directory.

## Onboarding atomicity

- Organization onboarding atomically creates the organization, owner user, owner
  membership, and initial refresh token through `onboard_organization_atomic`.
- Resource onboarding atomically creates the user, resource profile, and initial
  refresh token through `onboard_resource_atomic`.
- Both RPCs are `SECURITY INVOKER`; only `service_role` may execute them.
- Only hashed passwords and hashed refresh tokens are stored. Plaintext secrets must
  never be sent to PostgreSQL.
- Audit logs are deliberately outside onboarding transactions and are best-effort.

## Authentication and sessions

- Access and refresh JWTs require non-empty `id` and `jti` claims plus integer
  `iat`, integer `exp`, and a `type` of `access` or `refresh`; `exp` must exceed
  `iat`.
- Access tokens authorize requests only when signature, type, expiry, user existence,
  and Redis revocation checks pass.
- Access and refresh tokens used together must belong to the same user.
- Refresh tokens are stored as SHA-256 hashes with a non-null expiry. Multiple
  refresh-token rows per user/token are permitted by the final schema.
- Logout blacklists the refresh token in PostgreSQL and revokes the access token in
  Redis. This is cross-store work and is not one ACID transaction.
- Auth cookies are HTTP-only and `SameSite=Lax`; `Secure` is enabled in production.
- Login and onboarding are IP-rate-limited using Redis.

## Projects

- Project states are `draft`, `published`, `closed`, and `cancelled`; the database
  default is `draft`.
- `org_id`, creator, SPOC, title, description, deadline, budget, currency, domain,
  status, and skill tags are required after all migrations.
- Budget must be non-negative. Budget and currency must either both be null or both
  be present; later `NOT NULL` constraints mean both are always present now.
- Currency defaults to `INR`, but both API and database accept any exactly three
  uppercase letters. `FAV`, for example, is structurally valid.
- Domain defaults to `Not Specified`.
- Deadline must be later than `CURRENT_DATE` in PostgreSQL and later than the API
  server's local `date.today()` during request validation.
- A null `published_at` permits only `draft` or `cancelled`. A non-null
  `published_at` permits only `published` or `closed`.
- Creating with `publish_also=false` omits lifecycle fields and relies on database
  defaults. Creating with `publish_also=true` writes `published` and a UTC timestamp.
- Client organizations can create projects only with a SPOC in their organization.
  RIV3R organizations bypass the SPOC membership check for cross-tenant operation.
- A created project's `org_id` is always the current user's organization, including
  when the creator belongs to RIV3R.
- Clients may publish only their own organization's projects. RIV3R may publish
  cross-tenant projects.
- Only non-deleted drafts can be published. Publishing uses a conditional update on
  project ID, draft status, deletion state, and—when applicable—tenant ID, so two
  concurrent publish requests cannot both succeed.
- Successful project creation and publishing attempt best-effort audit writes after
  the project mutation; audit persistence failure does not change the API result.
- Draft projects do not have embeddings. When a project is published, the API makes
  one 1,024-dimensional document-embedding attempt with the configured primary
  Voyage model, then one attempt with the configured lower-tier Voyage fallback.
- Embedding generation is fail-open: a project may still be published with null
  embedding fields if both strategies fail. When a vector is present, its model and
  embedding timestamp are required; all three fields are otherwise null together.
- The primary model is `voyage-4` and the fallback is `voyage-4-lite`; both produce
  compatible 1,024-dimensional Voyage 4-series vectors.
- Existing published projects are not backfilled by the embedding migration.

## Authorization and data access

- `PermissionChecker` implementations are asynchronous and may run concurrently.
- `OrganizationLevelPermissionChecker` rejects resource users and users without a
  valid organization. RIV3R receives cross-tenant permission by default.
- Project creation/publishing currently allows client and RIV3R organizations;
  agencies are denied.
- All application tables have RLS enabled with no browser-client policies. `PUBLIC`,
  `anon`, and `authenticated` have no table access; the backend uses `service_role`.
- Because `service_role` bypasses RLS, every FastAPI query must enforce authorization
  explicitly and must repeat security-critical predicates in mutation queries.
- Organization-directory authorization is completed before its organization-scoped
  Redis cache is read. Cache failures fall back to PostgreSQL, and entries may be
  stale for at most `CACHE_TTL` until user mutation APIs add active invalidation.

## Validation rules

- Passwords require at least eight characters, uppercase, lowercase, a digit, and a
  supported special character.
- Phone numbers must match E.164: `+`, a non-zero country-code digit, then 7–14 more
  digits.
- Resource portfolio and LinkedIn URLs cannot be equal.
- Project title, description, and domain cannot be empty; budget has at most 15
  digits and two decimal places; currency matches `^[A-Z]{3}$`.

## Known schema caveats

- `organization_members_updated_at_trigger` refers to `updated_at`, but the table's
  migrations do not define that column. Updating a membership may fail until fixed.
- `projects.spoc_user_id` is `NOT NULL`, while its foreign key uses `ON DELETE SET
  NULL`. Deleting a referenced SPOC will conflict with the `NOT NULL` constraint.
- `deadline_date > CURRENT_DATE` is checked on inserts/updates; existing rows do not
  automatically become invalid or change state when their deadline passes.
- Cross-table email/URL uniqueness is enforced by onboarding RPC logic and advisory
  locks, not by one global database unique constraint. New write paths must use the
  same protocol or introduce a shared uniqueness registry.
