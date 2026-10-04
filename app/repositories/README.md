# Repository boundaries

`contracts.py` contains async domain protocols. Services accept these protocols
as constructor arguments; they do not build repositories or use storage clients.
`supabase.py` implements the six database contracts, and `redis.py` implements
access-token revocation. `app/core/dependencies.py` constructs adapters from the
existing application connections and injects services into routes.

To replace a provider, implement its protocol and change the corresponding
dependency provider. To add a domain, add a focused contract and adapter rather
than expanding an existing repository. The interfaces are structural Python
protocols; implementations do not need to inherit them.

Cross-table duplicate checks belong to `DuplicateChecker`, which receives email
and URL existence functions. Register another function in `get_duplicates` to
extend the checked sources without changing the checking algorithm. The checks
remain advisory; they do not add database uniqueness guarantees or transactions.

Onboarding RPCs report duplicate values as `23505` errors whose DETAIL equals
the offending RPC parameter name without the `p_` prefix. The onboarding
repository translates a matching DETAIL into a domain `DuplicateError` using
that key; `onboard_organization` carries an explicit legacy mapping so a
not-yet-migrated database's `phone_number` detail still resolves to
`p_owner_phone_number`. A duplicate code whose resolved key is absent from the
RPC params re-raises the original storage error instead of masking it.

Access-token revocation accepts a raw token and its verified expiration timestamp.
The Redis adapter writes a SHA-256 key until that expiration (rounded up to whole
seconds), and checks both hashed and legacy raw keys using `EXISTS`. Already
expired tokens require no blacklist entry. `cache_ttl` no longer controls token
revocation. Refresh-token hashes remain the auth service's responsibility, and
their database records receive the exact expiration of the signed refresh JWT.
Storage errors propagate; the audit service retains its existing error handling.

Project detail and list reads select only public project fields and always exclude
soft-deleted rows. Client detail/list queries carry an organization predicate;
only an authorized RIV3R service decision may omit it. Exact organization, SPOC,
and status filters use equality, while title, description, and domain use `ILIKE`.

Project lists use versioned Redis keys scoped to an organization or to the RIV3R
global view. The canonical filter/page/sort payload is hashed into the key. Project
creation increments the affected organization and global versions; publication
does the same and removes the detail key. Cache failures are fail-open and bounded
by `CACHE_TTL`.

Tokens carry required `iat`, `exp`, and unique `jti` claims. Lifetimes come from
`jwt_access_token_expire_minutes` and `jwt_refresh_token_expire_days`. Issuance
copies the input record and replaces token metadata when refreshing. Access and
refresh token types are checked at their respective entry points. Refresh can
accept an expired, correctly signed access token belonging to the same user,
but requires an unexpired, non-blacklisted refresh token. Logout permits signed
expired tokens for cleanup. Invalid tokens return HTTP 401.

Deploy this token-format change to all backend instances together. Existing
tokens without the required claims are rejected, so existing sessions must sign
in again. No database migration or signing-key rotation is required; old refresh
rows cannot authenticate without a valid new-format JWT. Rolling back to code
that accepts non-expiring tokens would restore the old behavior.

See `tests/integration/README.md` for live storage and token-lifecycle checks.
