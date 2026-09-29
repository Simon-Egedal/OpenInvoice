# OpenInvoice contributor guide

OpenInvoice is a self-hosted modular monolith. Keep the FastAPI backend in `backend/` and the Next.js App Router UI in `frontend/`.

## Architecture
- API routes live under `backend/app/api/v1`; business rules belong in services, not route handlers.
- SQLAlchemy 2 models and async database access live under `backend/app/models` and `backend/app/db`.
- Organization-owned records always include `organization_id`. Scope every read and write through an authenticated membership before accessing them.
- Integrations implement provider interfaces under `backend/app/providers`; local/mock implementations keep development independent of SaaS credentials.
- Money is `Decimal` in Python and `NUMERIC` in PostgreSQL. Never use floating point for monetary calculations.
- Frontend pages use App Router and TypeScript strict mode. Keep forms and API contracts typed and validate user input.

## Conventions
- Add schema changes as Alembic migrations. Never rely on startup `create_all` outside isolated tests.
- Use Pydantic request/response schemas and dependency-injected async services.
- Store uploaded documents through `StorageProvider`; persist metadata and object keys only.
- Avoid secrets in source control; configuration comes from environment variables documented in `.env.example`.
- Keep UI quiet and practical: neutral surfaces, compact tables, one restrained accent, semantic controls, visible focus states.
- Run backend tests with `pytest`; frontend checks with the scripts in `frontend/package.json`.

