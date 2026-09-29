# OpenInvoice

OpenInvoice is an open-source, self-hostable invoice management foundation for small businesses. It is a modular monolith built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, and Next.js.

## Included

- Email/password registration, login, logout, signed server-side session cookies, organizations, and memberships.
- Organization-scoped customers, suppliers, invoices, and audit events.
- Outgoing invoice creation with line items and `Decimal`/PostgreSQL `NUMERIC` totals.
- Clean invoice PDF generation and a console or SMTP email provider.
- Local filesystem storage and an S3-compatible storage adapter.
- Mock banking accounts and transactions, plus an isolated Enable Banking adapter placeholder.
- Provider interfaces for OCR, invoice extraction, e-invoicing, and accounting export.
- Responsive business UI with invoice, customer, supplier, banking, activity, and settings pages.

## Architecture

The backend is a FastAPI modular monolith. Versioned routes are in `backend/app/api/v1`, business logic in services, SQLAlchemy models in `models`, and optional integrations behind interfaces in `providers`. All tenant records carry an organization ID and APIs scope reads and writes through the caller's organization membership. The frontend uses Next.js App Router and a compact neutral UI.

## Requirements and quick start

Install Docker and Docker Compose. Copy `.env.example` to `.env`, change `POSTGRES_PASSWORD` and `SECRET_KEY`, then run:

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000) and create the first account. The API and OpenAPI docs are at [http://localhost:8000](http://localhost:8000) and [http://localhost:8000/docs](http://localhost:8000/docs). The default banking provider is mock; email is console-only until SMTP is configured.

## Configuration

See `.env.example` for all supported variables. PostgreSQL is the only required service. `STORAGE_PROVIDER=local` stores documents in the persistent `invoice_files` volume. Use `S3_ENDPOINT_URL`, bucket, region, and credentials to configure an S3-compatible backend. Set `EMAIL_PROVIDER=smtp` and the `SMTP_*` variables to send mail. `BANKING_PROVIDER=enable_banking` selects the isolated adapter scaffold; live operations intentionally return a clear not-implemented response pending an implementation against the current official API specification.

`SECRET_KEY` must be a long random secret in deployments. Set `SESSION_COOKIE_SECURE=true` behind HTTPS. The default CORS origin is `FRONTEND_URL`.

## Migrations and development

The API container runs `alembic upgrade head` before starting. For local backend development:

```bash
cd backend
python -m venv .venv
# activate the environment, then:
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Set `DATABASE_URL` to a reachable PostgreSQL instance. Create future migrations with `alembic revision --autogenerate -m "describe change"` and review generated migration operations before applying them.

For frontend development:

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` if the API is not at `http://localhost:8000`.

## Tests

Run backend tests from `backend/` with `pytest`. The first tests cover decimal rounding and the mock banking provider. Frontend scripts include `npm run build`.

## Provider system

Use `BankingProvider`, `EmailProvider`, `StorageProvider`, `OCRProvider`, `InvoiceExtractionProvider`, `AccountingProvider`, or `EInvoiceProvider` for integrations. The mock banking provider runs without credentials. Enable Banking calls are deliberately not guessed or fabricated. Local storage keeps bytes outside PostgreSQL; only object keys and document metadata belong in the database.

## Current scope

This is an initial foundation. Incoming invoice approval, bank synchronization and callback persistence, async email job processing/retries, configurable branding, and mature role-specific permissions are follow-up work. The current receiving flow accepts a supplier, invoice details, and a validated PDF, then stores the file through the configured storage provider.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for project conventions.

## License

MIT. See [LICENSE](LICENSE).
