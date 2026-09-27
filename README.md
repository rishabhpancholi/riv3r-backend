# RIV3R backend

See [database access and RLS deployment](supabase/RLS.md) for the backend-only
Supabase access model, required server credentials, and database verification.

See [integration tests](tests/integration/README.md) for live Supabase/Redis checks.
JWTs now require expiration and unique IDs; existing sessions must sign in again
when deploying this token-format change. Token lifetimes use the existing JWT
settings, and access-token revocation lasts until the token expires.
