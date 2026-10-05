# Backup and restore

A complete backup contains PostgreSQL, stored documents, the encrypted application settings, their encryption key, and any deployment `.env` or private provider keys. The `invoice_files` volume includes `/data/openinvoice-settings.enc`, `/data/openinvoice-settings.key`, and local documents. Losing the key makes the settings and queued account emails unreadable. Protect backups as credentials and financial records.

Keep dated backups outside the Docker host. Test restoration into an isolated installation regularly. Do not overwrite a running installation to test a backup.

## Bundled PostgreSQL and local storage (PowerShell)

Run from the project directory. Choose a new backup folder. Stop writers for the duration so database metadata and document files represent the same point in time.

```powershell
$backupDirectory = Join-Path $PWD ("backups/" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDirectory -ErrorAction Stop | Out-Null
docker compose stop api worker frontend
try {
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/openinvoice-backup.dump'
    if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
    $databaseContainer = docker compose ps -q db
    docker cp "${databaseContainer}:/tmp/openinvoice-backup.dump" (Join-Path $backupDirectory 'database.dump')
    if ($LASTEXITCODE -ne 0) { throw 'Database backup copy failed' }
    $apiContainer = docker compose ps -a -q api
    docker cp "${apiContainer}:/data" (Join-Path $backupDirectory 'data')
    if ($LASTEXITCODE -ne 0) { throw 'Document and key backup failed' }
    if (Test-Path -LiteralPath '.env') { Copy-Item -LiteralPath '.env' -Destination $backupDirectory }
    if (Test-Path -LiteralPath 'secrets') { Copy-Item -LiteralPath 'secrets' -Destination $backupDirectory -Recurse }
    Get-FileHash -Algorithm SHA256 (Join-Path $backupDirectory 'database.dump') |
        Format-List | Out-File (Join-Path $backupDirectory 'database.sha256.txt')
    git rev-parse HEAD | Out-File (Join-Path $backupDirectory 'application-revision.txt')
} finally {
    docker compose start api worker frontend
}
```

Use `docker cp` for the binary dump. Redirecting a binary dump with older PowerShell versions can corrupt it. Configure your backup directory outside the repository or ensure it is ignored.

## Restore into a fresh installation

Use the recorded application revision and compatible PostgreSQL major version first. Keep API and worker stopped until both database and storage are restored. These commands target a **fresh empty installation**; they intentionally do not clean or overwrite an existing database.

1. Copy the backed-up `.env` and provider keys into the fresh installation, if present. Review ports and `FRONTEND_URL` for the isolated host.
2. Run `docker compose up -d db` and `docker compose create api worker frontend`. Wait for PostgreSQL health.
3. Copy and restore the dump:

```powershell
$backupDirectory = 'C:/Backups/OpenInvoice/20261005-120000'
$databaseContainer = docker compose ps -q db
docker cp (Join-Path $backupDirectory 'database.dump') "${databaseContainer}:/tmp/openinvoice-backup.dump"
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error /tmp/openinvoice-backup.dump'
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; do not start application services' }
$apiContainer = docker compose ps -a -q api
docker cp (Join-Path $backupDirectory 'data/.') "${apiContainer}:/data"
if ($LASTEXITCODE -ne 0) { throw 'Storage restore failed; do not start application services' }
docker compose up -d api worker frontend
```

4. Check migrations and service logs. Sign in, download an original supplier document and an issued invoice PDF, compare invoice/payment totals, and inspect delivery history. Review interrupted (`uncertain`) deliveries before retrying.
5. Record the rehearsal date and results. Upgrade application revisions only after the restored version works.

## External PostgreSQL or S3

For external PostgreSQL, use that server's backup tooling and credentials instead of the bundled `db` container. Save its connection settings and SSL requirements. For S3 storage, keep an independent copy or versioned snapshot of all objects referenced by invoice documents and issued PDF keys. Back up the `/data` settings/key files even when document storage is S3. Restore the objects before starting API and worker. A database dump alone is incomplete.

## Retention and recovery checks

Maintain multiple dated copies, including one off-host copy. Encrypt backup archives and restrict access to the encryption key. Monitor backup failures and available disk space. Verify a representative PDF, database migration version, organization balances, membership permissions, and SMTP configuration after each restore. Change deployment secrets if an archive is exposed.
