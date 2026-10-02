# Backend-only database access

Application tables in `public`, including the three permission tables, have RLS
enabled and no client policies.
`PUBLIC`, `anon`, and `authenticated` have neither table nor column privileges.
The backend uses `service_role`, which bypasses RLS; FastAPI must continue to
authorize every user and organization operation. RLS does not protect against
an incorrectly authorized service-role query.

`DATABASE_KEY` must be a server-only Supabase service-role JWT key or Supabase
secret key. Never expose it to browser code. `JWT_SECRET_KEY` signs application
cookies and is independent of the Supabase key; application JWTs are not sent
to Supabase. No authentication or public API changes are required.

## Validate before deployment

1. Compare the target database with the protected tables in the migrations. Review
   `pg_policies`, `pg_class.relrowsecurity`, `pg_class.relacl`, and
   `pg_attribute.attacl`, including grants inherited through role membership.
   Inspect exposed views and callable `SECURITY DEFINER` functions that may
   provide alternate access to these tables. Resolve unexpected exposure
   before deploying.
2. Capture a schema-only dump (including grants and policies, without
   `--no-acl`) using the existing database backup tooling. Save it securely
   outside the repository. Record the previous RLS flags as well, and prepare
   a targeted rollback restoring those flags, grants, and policies, without
   recreating tables or restoring data.
3. Confirm the running backend's `DATABASE_KEY` is a server-only privileged
   key without printing or committing its value. An anonymous/publishable
   key will stop working after this migration.
4. Apply migrations to a disposable/staging database using the existing
   migration process. Do not reset a populated database. The new migration
   is transactional and preserves rows and table definitions.
5. Run the SQL checks as `postgres` (or an equivalent test administrator that
   can grant privileges and switch roles):

   ```powershell
   psql $env:TEST_DATABASE_URL -X -v ON_ERROR_STOP=1 -f supabase/tests/database/backend_only_rls.sql
   psql $env:TEST_DATABASE_URL -X -v ON_ERROR_STOP=1 -f supabase/tests/database/permissions.sql
   ```

   The suites insert fixtures through `service_role`, verify backend-only access,
   and validate permission grants, dependency traversal, cycle rejection, and
   resource-user restrictions. All changes are rolled back. A failed assertion
   returns a nonzero exit code; closing the failed connection rolls back.

6. Smoke-test staging through FastAPI: organization and resource onboarding,
   login, token refresh, logout, own-user/resource updates, owner organization
   updates, and audit insertion. Confirm another user's resource update and
   a non-owner organization update are rejected and leave rows unchanged.
   Use two independent users/organizations for the negative checks.
7. Deploy through the existing migration process only after those checks pass.
   Monitor database permission errors and authentication/onboarding failures.
   If rollback is necessary, use the captured targeted restoration; do not
   blindly disable RLS or grant access to every client.

Existing mocked Python API tests are regression checks, not proof of RLS.
No local Supabase configuration is committed, so these instructions use an
explicit test database rather than assuming `supabase start` is configured.

## Known unrelated schema issue

The existing `organization_members_updated_at_trigger` writes `updated_at`,
but the migrations do not define that column on `organization_members`.
The RLS suite exercises service-role inserts and reads for memberships and
uses `resources` for representative updates/deletes. Fixing the membership
update trigger is a separate schema change.
