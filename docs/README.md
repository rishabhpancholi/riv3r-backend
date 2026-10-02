# RIV3R Backend

RIV3R is the API behind an organization-and-talent delivery platform: companies
onboard teams, independent resources build professional profiles, and authorized
organizations create and publish projects with a designated point of contact.

The backend is built with FastAPI, Supabase/PostgreSQL, Redis, Anthropic, and
Voyage AI. It favors a small service/repository architecture, explicit permission
checks, provider-neutral AI clients, and database transactions for workflows that
must succeed or fail as one unit.

## What is here

- Organization and independent-resource onboarding
- Atomic onboarding through PostgreSQL RPC functions
- Cookie-based access and refresh JWT authentication
- Login, refresh, logout, Redis-backed access-token revocation, and audit logs
- Organization-aware permissions with cross-tenant access for RIV3R users
- Draft project creation and race-safe project publishing with best-effort audits
- Backend-only Supabase tables protected from `anon` and `authenticated` roles
- Unit, API, database-policy, and opt-in live integration tests

## API at a glance

| Area | Endpoints |
| --- | --- |
| Health | `GET /api/health` |
| Onboarding | `POST /api/onboarding/organization`, `POST /api/onboarding/resource` |
| Authentication | `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Projects | `POST /api/projects`, `POST /api/projects/{project_id}/publish` |

Interactive OpenAPI documentation is available at `/docs` outside production.

## Architecture

Each API package owns its routes, schemas, response views, and feature-specific
dependencies. Services hold business rules, repository contracts isolate storage,
and Supabase adapters execute PostgREST queries or RPCs. Shared authentication,
connections, exceptions, and permission primitives live under `app/core`.

Organization and resource onboarding use one PostgreSQL function per workflow,
so related users, organizations, memberships, profiles, and initial refresh tokens
commit or roll back together. Project publishing uses a conditional update on the
`draft` state, preventing two concurrent publish requests from both succeeding.

See [TRUTH.md](TRUTH.md) for the current business and database invariants, and
[STRUCTURE.md](STRUCTURE.md) for the low-level design. The dated development
history is maintained in [CHANGELOG.md](CHANGELOG.md).

## Local setup

Requirements:

- Python 3.12+
- `uv`
- A Supabase project with the repository migrations applied
- Redis

Install dependencies:

```powershell
uv sync
```

Configure `.env` with at least:

```dotenv
DATABASE_URL=https://your-project.supabase.co
DATABASE_KEY=your-server-only-service-role-or-secret-key
CACHE_HOST=localhost
CACHE_PORT=6379
CACHE_USERNAME=default
CACHE_PASSWORD=your-redis-password
LLM_API_KEY=your-anthropic-api-key
LLM_MODEL=claude-haiku-4-5-20251001
EMBEDDINGS_API_KEY=your-voyage-api-key
EMBEDDINGS_MODEL=voyage-4
JWT_SECRET_KEY=use-a-strong-private-secret
CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
```

Optional settings include `APP_MODE`, JWT lifetimes, cache TTL, and login rate
limits. Never expose `DATABASE_KEY` or `JWT_SECRET_KEY` to a browser client.
The AI API keys and model names are also required at startup and must remain
server-side.

Application code should request the shared provider-neutral clients with the
`get_llm` and `get_embeddings` FastAPI dependencies. Callers use application-owned
chat messages and query/document embedding methods; they do not select Anthropic
or Voyage models directly.
limits. `CORS_ALLOWED_ORIGINS` is a JSON list of browser origins permitted to call
the API with credentials. Never expose `DATABASE_KEY` or `JWT_SECRET_KEY` to a
browser client.

Apply migrations using the configured Supabase workflow, then start the API:

```powershell
uv run uvicorn app.main:app --reload
```

## Testing

Run the isolated suite:

```powershell
uv run pytest tests/unit tests/api -q
```

Live Supabase and Redis tests are opt-in. See
[tests/integration/README.md](tests/integration/README.md) for their isolated
credentials and commands. Database access and RLS deployment checks are documented
in [supabase/RLS.md](supabase/RLS.md).

## Security notes

- Application JWTs are verified by FastAPI and are not Supabase Auth tokens.
- Authentication cookies are HTTP-only, `SameSite=Lax`, and secure in production.
- Supabase access requires a backend-only service-role or secret key.
- Audit persistence is best-effort and intentionally does not roll back domain work.
- Existing sessions must sign in again after incompatible JWT claim changes.
