# Contributing

Thanks for helping improve OpenInvoice. Keep changes focused and suitable for a self-hosted modular monolith.

1. Read `AGENTS.md` and the architecture notes in `README.md`.
2. Keep request parsing in API routes, business rules in services, and vendor-specific code behind provider interfaces.
3. Scope every organization resource query to the authenticated membership. Add migrations for schema changes.
4. Use `Decimal`/`NUMERIC` for money. Never commit secrets or real financial data.
5. Add focused tests for behavior and run the relevant checks before opening a pull request.
6. Describe the change, migration impact, and any provider configuration required.

## Development

Start PostgreSQL with Docker Compose or use a local PostgreSQL instance. Configure `.env` from `.env.example`, install backend requirements, and run `uvicorn app.main:app --reload` from `backend/`. Run `pytest` from that directory. The UI runs from `frontend/` with `npm install && npm run dev`.

