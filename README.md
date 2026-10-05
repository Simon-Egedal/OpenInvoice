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

Install Docker and Docker Compose, then start the bundled services:

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000) and follow the first-run setup to verify PostgreSQL, configure SMTP and document storage, and choose a banking provider. Provider settings are encrypted on the persistent application volume; an application signing key is generated on first start. If you select an external PostgreSQL server, restart the API when prompted so its migrations run against that database. Then create the first owner account. The API and OpenAPI docs are at [http://localhost:8000](http://localhost:8000) and [http://localhost:8000/docs](http://localhost:8000/docs). The default banking provider is mock; console email is useful for local development.

`.env` is optional for local startup. Use `.env.example` to customize the bundled PostgreSQL credentials, ports, or other deployment defaults before starting the containers. Keep your Docker data volumes: they contain the encrypted settings and their key, as well as local invoice files.

## Configuration

See `.env.example` for optional deployment overrides. PostgreSQL is the only required service. The setup wizard verifies SMTP and S3 access before saving credentials. `STORAGE_PROVIDER=local` stores documents in the persistent `invoice_files` volume. The Enable Banking adapter remains a scaffold; live operations are not implemented yet.

`SECRET_KEY` must be a long random secret in deployments. Set `SESSION_COOKIE_SECURE=true` behind HTTPS. The default CORS origin is `FRONTEND_URL`.

Administrators and the initial owner can open **Administration** to manage the organization profile, infrastructure, and member or administrator accounts. The organization profile includes its name, default currency, country, and logo. New accounts are created by email and role; passwords are generated automatically, stored as hashes, and sent to the recipient through SMTP. Configure SMTP and restart the API when prompted before creating accounts; console email cannot deliver account credentials. Set `FRONTEND_URL` to the address recipients should use to sign in. Existing email addresses are rejected without changing their passwords or memberships.

All signed-in users can update their name and change their password in **Settings**. Changing a password requires the current password and a new password of at least 12 characters.

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
