# Verification

Backend unit tests run with `cd backend; python -m pytest -q`. PostgreSQL tests are explicitly skipped unless `TEST_DATABASE_URL` is supplied. CI supplies it and runs the complete suite against PostgreSQL 16 and Python 3.12. Use a dedicated database: test scenarios create organizations, users, invoices, and encrypted outbox entries.

## Local PostgreSQL integration tests (PowerShell)

```powershell
docker run --detach --name openinvoice-verification-db --publish 127.0.0.1:55439:5432 --env POSTGRES_DB=openinvoice_test --env POSTGRES_USER=openinvoice_test --env POSTGRES_PASSWORD=verification-only postgres:16-alpine
docker exec openinvoice-verification-db pg_isready -U openinvoice_test
cd backend
$env:DATABASE_URL = 'postgresql+asyncpg://openinvoice_test:verification-only@127.0.0.1:55439/openinvoice_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
python -m alembic upgrade head
python -m pytest -q
```

If the named test container already exists, reuse it rather than starting a duplicate. These are test credentials only. They must not become deployment defaults.

## Browser workflows

Browser fixtures require a database name ending in `_e2e`; the seed script refuses other database names. Use a separate settings/key directory and storage directory. Do not point browser fixtures at the running app's volumes.

```powershell
docker exec openinvoice-verification-db createdb -U openinvoice_test openinvoice_e2e
# From backend/
$env:DATABASE_URL = 'postgresql+asyncpg://openinvoice_test:verification-only@127.0.0.1:55439/openinvoice_e2e'
$env:APP_CONFIG_PATH = Join-Path $env:TEMP 'openinvoice-e2e/settings.enc'
$env:LOCAL_STORAGE_PATH = Join-Path $env:TEMP 'openinvoice-e2e/files'
$env:FRONTEND_URL = 'http://127.0.0.1:13000'
python -m alembic upgrade head
python tests/seed_e2e.py
cd ../frontend
npm ci
npx playwright install chromium
npm run typecheck
npm run test:e2e
npm run build
```

Playwright starts isolated API/UI processes on ports 18000 and 13000 and stops them afterward. It tests invoice creation, issuance, queued delivery, partial payment, bank reconciliation, PDF download, supplier receipt and original download, rejection/resubmission/approval, CSV import/export, API failure/retry, and decimal calculations. Backend tests validate delivery retries and account links using local test providers. Browser traces are retained on failure in the ignored `frontend/test-results` directory.

For production-like validation, build the Docker images and run the stack against isolated volumes. Configure test SMTP/S3/banking credentials only if exercising those external services. The default automated suite makes no live provider calls. Test bank fixtures do not represent a live bank authorization or financial transaction.
