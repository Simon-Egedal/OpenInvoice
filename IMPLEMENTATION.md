# Invoice reliability and workflow implementation

This checklist records the full scope requested after the project review. Completion requires working UI and API behavior, appropriate tests, documentation, and a final Git commit. Existing user changes in `frontend/src/app/administration/page.tsx` must be preserved.

## Requirements

- [x] Enforce write permissions for sending and banking mutations; preserve paid and partial states on resend.
- [x] Enforce currencies, locking, allocation limits, uniqueness, and parent resource ownership in payment/matching operations.
- [x] Correct outstanding balances; separate incoming/outgoing and currencies; calculate overdue and aging from dates.
- [x] Preserve issued party snapshots and PDF documents; download original incoming documents with authentication.
- [x] Use decimal frontend calculations with backend rounding and send decimal strings.
- [x] Automatic outgoing numbers and supplier-specific incoming duplicate detection.
- [x] Seller address, VAT, payment information and terms; robust multipage PDFs.
- [x] Durable email queue, retries, delivery history and idempotency.
- [x] Incoming invoice submission, approval/rejection reasons and decision history.
- [x] Reminder queue, history and aging report UI.
- [x] Invoice/payment exports and validated customer/product CSV imports with UI.
- [x] Expiring invitation links and password reset; disable accounts, change roles, revoke sessions.
- [x] Pagination and visible error/retry states across lists and forms.
- [x] CI, PostgreSQL integration tests, browser workflow tests and documented verification.
- [x] Backup/restore covering database, storage and encryption/signing keys.
- [x] Update README to match implemented banking and workflows.
- [x] Final requirement audit, passing checks and commit all authorized changes.

## Verification baseline

Before changes: backend pytest 49 passed / 4 failed (matching fixture direction); frontend typecheck and production build passed. The project uses Python 3.12 in Docker; the local Python is 3.14. Live SMTP and banking require external credentials.


## Final audit and evidence (2026-10-05)

All requirements above have API, UI where applicable, and documentation coverage. The pre-existing account button spacing change remains intact.

- Backend: 63 tests passed against isolated PostgreSQL 16, including concurrent numbering/allocation, tenant isolation, role checks, parent ownership, original documents, immutable issuance, approval reasons, expiring single-use links, session revocation, atomic CSV imports, retry scheduling and uncertain delivery handling.
- Docker compatibility: backend image built with Python 3.12; the same 63 tests passed inside that image. Financial mutations serialize with organization row locks that permit foreign-key checks without introducing cross-account lock inversion.
- Migrations: upgrades through `0010_line_tenant_scope` succeeded; `alembic check` reports no missing schema changes. Legacy duplicate identities produce actionable migration errors instead of rewriting records.
- Frontend: TypeScript strict checking and optimized Next.js production build passed. Six Playwright tests passed, including exact monetary rounding, full outgoing payment reconciliation, incoming rejection/resubmission/approval, original downloads, CSV import/export and visible API failure/retry.
- Deployment: `docker compose config --quiet` and Git whitespace checks passed. API readiness depends on PostgreSQL; worker starts after migrations and shares the persistent settings/key/document volume.
- Restore rehearsal: dumped the isolated browser database, restored into a fresh database, confirmed migration revision and invoice records, copied settings/key/storage, decrypted settings and verified three referenced PDFs match original bytes. No running user database or application volumes were changed.
- README, verification instructions and backup/restore instructions describe the implemented behavior and upgrade requirements.

Live SMTP, S3 and Enable Banking require deployment credentials and were not exercised. Console/mock providers and controlled delivery failures were exercised. SMTP acceptance cannot guarantee recipient delivery; uncertain sends require review. Existing historical documents cannot acquire original historical party details retroactively. OCR, e-invoicing and general-ledger work remain documented extension points outside this requested scope. CI is configured; remote execution occurs after pushing the commit.
