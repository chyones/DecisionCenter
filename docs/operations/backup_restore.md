# Backup and Restore

## Scope

Backups cover the two stateful data stores:

1. **PostgreSQL** — audit logs, review decisions, connector events, admin events,
   Entra group mappings, and source mappings.
2. **MinIO** — staging reports, final reports, evidence packs, approval logs,
   quality-gate results, and uploaded files.

n8n workflow exports and project mapping configuration are also listed in the
DR policy but are treated as configuration (versioned in git or exported
separately via the n8n UI).

## Recovery Point Objective (RPO) and Recovery Time Objective (RTO)

| Target | Value | Owner |
|---|---|---|
| RPO | 24 hours (daily backups recommended) | Operator |
| RTO | 1 hour for full stack rebuild + restore | Operator |

## Prerequisites

- Docker Compose stack is running (`make up`)
- `backups/` directory exists (created automatically by scripts)
- `.env` contains correct database and MinIO credentials

## Backup Procedure

### PostgreSQL

```bash
# From the project root (host or app container after image rebuild)
make backup-postgres
# Produces: backups/postgres_YYYYMMDD_HHMMSS.sql
```

Or run the script directly:

```bash
python3 scripts/backup_postgres.py --output-dir backups
```

The script tries ``pg_dump`` directly; if unavailable it falls back to
``docker compose exec -T postgres pg_dump``.

### MinIO

```bash
# From the project root
make backup-minio
# Produces: backups/minio_YYYYMMDD_HHMMSS.tar.gz
```

Or run the script directly:

```bash
PYTHONPATH=. python3 scripts/backup_minio.py --output-dir backups
```

### Combined Daily Backup (operator cron)

```bash
#!/bin/bash
cd /opt/DecisionCenter
make backup-postgres
make backup-minio
# Rotate backups older than 7 days
find backups -name "postgres_*.sql" -mtime +7 -delete
find backups -name "minio_*.tar.gz" -mtime +7 -delete
```

## Restore Procedure

### Before Restoring

1. Confirm the target environment is **non-production** or that you are
   performing a disaster-recovery rehearsal.
2. Verify the backup file with:
   ```bash
   PYTHONPATH=. python3 scripts/verify_backup.py --postgres backups/postgres_YYYYMMDD_HHMMSS.sql --minio backups/minio_YYYYMMDD_HHMMSS.tar.gz
   ```

### PostgreSQL Restore

**WARNING:** This drops and recreates the database.

```bash
python3 scripts/restore_postgres.py backups/postgres_YYYYMMDD_HHMMSS.sql
```

If running inside the app container:

```bash
docker compose exec app python3 scripts/restore_postgres.py backups/postgres_YYYYMMDD_HHMMSS.sql
```

### MinIO Restore

```bash
PYTHONPATH=. python3 scripts/restore_minio.py backups/minio_YYYYMMDD_HHMMSS.tar.gz
```

### Post-Restore Verification

```bash
PYTHONPATH=. python3 scripts/verify_backup.py --verify-restored
```

Expected output includes:
- PostgreSQL sanity: N audit rows, M review rows
- MinIO sanity: K objects in bucket
- Linkage sanity: X/Y recent request IDs have matching MinIO artifacts

## Restore Rehearsal Evidence

Rehearsal must prove that:

1. **Audit/report data is present** after restore (`audit_log` count > 0).
2. **Request ID linkage is intact** — a request ID in `audit_log` maps to
   `final/{request_id}/` objects in MinIO.
3. **Staging and final reports are recoverable** — both `staging/` and `final/`
   prefixes exist in MinIO after restore.

Evidence is captured by running `scripts/verify_backup.py --verify-restored`
and saving the transcript. Transcripts are stored locally, not committed to git.

## Secrets and Credentials

- Database passwords and MinIO keys are read from `.env` (never committed).
- Backup files contain **data only**, no secrets.
- Secrets are managed by the operator through the approved secrets manager,
  not through the backup system.

## What Is NOT Backed Up

| Item | Reason |
|---|---|
| Qdrant vectors | Rebuild from source documents via `make init-qdrant` |
| Redis cache | Ephemeral; rebuilds automatically |
| n8n credentials | Managed in n8n UI; export workflows separately |
| `.env` secrets | Managed by secrets manager |
| Application logs | Rotated locally; not part of DR scope |

## Related Documents

- `docs/policies/disaster_recovery_policy.md` — DR ownership and expectations
- `scripts/backup_postgres.py` — PostgreSQL backup implementation
- `scripts/backup_minio.py` — MinIO backup implementation
- `scripts/restore_postgres.py` — PostgreSQL restore implementation
- `scripts/restore_minio.py` — MinIO restore implementation
- `scripts/verify_backup.py` — Backup integrity and linkage verification
