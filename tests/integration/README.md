# Integration tests

This folder tests real Supabase and Redis adapters and the FastAPI authentication
flow. `tests/api` retains HTTP tests using injected fakes, and `tests/unit` tests
isolated behavior. These integration tests are skipped unless explicitly enabled.

Use a dedicated test Supabase project with all repository migrations applied
and a dedicated Redis test database. The Supabase key must be a server-only
service-role or secret key. Tests create uniquely named users, refresh records,
audit logs and Redis keys, then remove their own data in fixture cleanup.
They never reset tables or flush Redis. Interrupted test processes may leave
their uniquely identified fixtures behind.

Configure these environment variables in your shell or test runner (they are
never loaded from the application's database/cache settings):

```powershell
$env:RUN_INTEGRATION_TESTS = "1"
$env:TEST_SUPABASE_URL = "https://your-test-project.supabase.co"
$env:TEST_SUPABASE_KEY = "your-test-server-only-key"
$env:TEST_REDIS_URL = "redis://localhost:6379/15"
uv run pytest tests/integration -v
```

The application's JWT configuration must also be available, as for the normal
test suite. No Supabase or Redis integration credentials fall back to `.env`.
When enabled, missing test settings or connection failures fail the tests rather
than silently skipping them. Only `TEST_REDIS_URL` is needed when running
`tests/integration/test_redis_revocations.py` alone.

Coverage includes login/refresh/logout through real storage, replay rejection,
refresh after access expiration, stored refresh expiry matching JWT expiry,
Redis TTL matching remaining access lifetime, automatic blacklist expiration,
legacy-key reads, and persisted audit records.

Run isolated tests without external services:

```powershell
uv run pytest tests/unit tests/api -q
```

After deploying the required-expiration JWT format, existing users must sign in
again. The ordinary suite tests legacy-token rejection, wrong token types,
invalid signatures, and expiration errors without needing external services.
