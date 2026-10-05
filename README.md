# OpenInvoice

OpenInvoice is an open-source, self-hostable invoice management foundation for small businesses. It is a modular monolith built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, and Next.js.

## Included

- Email/password registration, login, logout, signed session cookies with server-checked revocation, organizations, and memberships.
- Organization-scoped customers, suppliers, invoices, and audit events.
- Outgoing invoice drafts, automatic organization-specific numbers, issuance, preserved party details and PDF files, and `Decimal`/PostgreSQL `NUMERIC` totals.
- Wrapped, multipage invoice PDFs with seller address, VAT number, payment information, and terms.
- Durable PostgreSQL email outbox with console or SMTP providers, retry scheduling, delivery history, and explicit review of uncertain sends.
- Local filesystem storage and an S3-compatible storage adapter.
- Mock banking accounts and transactions, plus an Enable Banking adapter for authorization, callbacks, accounts, balances, and transaction synchronization.
- Partial/manual payments and bank allocation with currency checks, transaction locking, and remaining-balance limits.
- Incoming PDF downloads, supplier duplicate detection, approval decisions with reasons and actor history.
- Currency-separated receivables/payables, aging reports, and payment reminders.
- CSV exports for invoices, manual payments and bank allocations; atomic customer/product imports.
- Expiring invitation and password recovery links, membership controls, and session revocation.
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

See `.env.example` for optional deployment overrides. PostgreSQL is the only required external service. The bundled worker processes the email outbox. The setup wizard verifies SMTP and S3 access before saving credentials. `STORAGE_PROVIDER=local` stores documents in the persistent `invoice_files` volume. Enable Banking requires a valid application ID and private key; mock banking keeps development independent of provider credentials. Live banking and SMTP access must be validated with your own credentials.

`SECRET_KEY` must be a long random secret in deployments. Set `SESSION_COOKIE_SECURE=true` behind HTTPS. The default CORS origin is `FRONTEND_URL`.

Administrators and the initial owner can open **Administration** to manage the organization profile, infrastructure, and accounts. The profile includes seller address, VAT number, payment information, payment terms, numbering prefix, currency, country, and logo. Invite accounts by email and role. Recipients choose a password through a one-time link that expires after 48 hours. Invitation tokens are hashed, and queued messages are encrypted. Configure SMTP and restart both API and worker when prompted; console email does not deliver account links. Set `FRONTEND_URL` to the address recipients should use. Existing email addresses are rejected without changing their passwords or memberships. Pending invitations can be renewed; the previous links become invalid.

All signed-in users can update their name and change their password in **Settings**. Changing a password requires the current password and a new password of at least 12 characters. Other sessions are revoked. **Forgot password?** sends a one-time link that expires after one hour. Settings also provides **Sign out all sessions**. Administrators can change non-owner roles, disable memberships, and revoke sessions. Approvers decide incoming invoices; viewers have read access. Only owners and administrators access administration and activity logs.

## Invoice workflow

Create an outgoing draft; leave its number blank for automatic allocation. **Issue invoice** preserves issuer/recipient details and stores the PDF. The invoice becomes `issued`. **Send invoice** queues email; SMTP acceptance changes `issued` to `sent`. Sending again preserves paid or partial payment states. The email table shows queue status, errors, retries, and reminder history. An idempotency key prevents a repeated delivery request from creating another job. The web UI retains the key when a request fails.

Receive a supplier PDF, then submit it for approval. Owners, administrators, and approvers can approve or reject pending invoices. Rejection requires a reason. Only approved incoming invoices can receive payments or transaction allocations. Original files remain available under **Original documents**. Incoming number uniqueness is scoped to supplier and organization; outgoing numbers are unique within the organization.

Record partial/manual payments or allocate bank transactions. Currency and credit/debit direction must agree, and allocations cannot exceed either the transaction's remaining amount or the invoice's unpaid balance. Financial operations are serialized per organization. The overview groups balances by direction and currency and derives aging from due dates. Overdue outgoing invoices expose **Send payment reminder**. Reminders are requested explicitly; paid invoices are not chased by jobs queued earlier.

Email retries use increasing delays for definite connection/recipient/authentication failures, up to five failed attempts. Interrupted or potentially accepted sends become `uncertain` and are not retried automatically. Verify receipt before using **Retry delivery**. In local development, run `python -m app.worker` alongside the API. Restart both after infrastructure configuration changes.

**Import / export** provides CSV templates and financial exports. Imports require UTF-8 CSV, accept up to 1,000 records / 2 MB, and reject unsupported columns, invalid values, and duplicate names. An invalid import saves no records. Exports escape user-entered spreadsheet formulas. List APIs support bounded `limit` and `offset`; invoices also support search, status, direction, currency, and unpaid filters.

## Upgrading and backups

Back up database, documents, encryption/signing keys, and deployment credentials before upgrading. See [backup and restore instructions](docs/backup-and-restore.md) for PowerShell commands and an isolated restore rehearsal. Run `docker compose up --build -d` to apply migrations and start API, worker, and UI. Migration 0006 intentionally refuses duplicate invoice identities or transaction matches; reconcile such legacy duplicates before upgrading. Historical invoices without a previously stored snapshot can only be preserved using the details available at upgrade time when first issued/sent again.

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

Run backend tests from `backend/` with `pytest`. Set `TEST_DATABASE_URL` to a dedicated PostgreSQL database and run `alembic upgrade head` against the same `DATABASE_URL` to enable integration tests. Never use production data. Tests cover concurrency, isolation, document preservation, approvals, invitation expiration, session revocation, CSV imports, and outbox behavior. Frontend checks are `npm run typecheck`, `npm run build`, and `npm run test:e2e`. See [verification instructions](docs/testing.md) for isolated browser fixtures. GitHub Actions runs migrations, backend tests, frontend checks, and Chromium workflow tests.

## Provider system

Use `BankingProvider`, `EmailProvider`, `StorageProvider`, `OCRProvider`, `InvoiceExtractionProvider`, `AccountingProvider`, or `EInvoiceProvider` for integrations. The mock banking provider runs without credentials. Enable Banking authorization uses an expiring state tied to the authenticated organization. Local storage keeps bytes outside PostgreSQL; only object keys and document metadata belong in the database.

## Current scope

The implemented workflows cover invoice management, approval, delivery, payment tracking, reconciliation, and CSV exchange. OCR/extraction and e-invoicing interfaces remain extension points. This is not a general ledger or a tax filing system. Live provider behavior requires deployment-specific validation. SMTP cannot guarantee exactly-once delivery across process or network failures; uncertain delivery states require review.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for project conventions.

## License

MIT. See [LICENSE](LICENSE).
