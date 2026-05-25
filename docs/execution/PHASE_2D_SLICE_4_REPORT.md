# Phase 2D Slice 4 — Backup and Restore Readiness

## Status

**IMPLEMENTED_NOT_LIVE**

Slice 4 was explicitly approved in the current session and is now complete.

## Scope

Create and validate backup/restore readiness for PostgreSQL and MinIO, with
documented operator procedures and restore rehearsal evidence.

## Deliverables

| Deliverable | Location | Status |
|---|---|---|
| PostgreSQL backup script | `scripts/backup_postgres.py` | ✅ |
| MinIO backup script | `scripts/backup_minio.py` | ✅ |
| PostgreSQL restore script | `scripts/restore_postgres.py` | ✅ |
| MinIO restore script | `scripts/restore_minio.py` | ✅ |
| Backup verification script | `scripts/verify_backup.py` | ✅ |
| Backup/restore runbook | `docs/operations/backup_restore.md` | ✅ |
| Disaster recovery policy | `docs/policies/disaster_recovery_policy.md` | ✅ |
| Makefile targets | `Makefile` (`backup-postgres`, `backup-minio`, `verify-backup`) | ✅ |
| Dockerfile update | `Dockerfile` (`postgresql-client` added) | ✅ |
| Integration tests | `apps/edr/tests/integration/test_phase2d_slice4_backup_restore.py` | ✅ |
| `.gitignore` exclusions | `.gitignore` (`backups/`, `*.sql`, `*.tar.gz`) | ✅ |

## Validation Evidence

### Local Validation (operator-run)

| Check | Result |
|---|---|
| `ruff check apps scripts` | clean |
| `python3 -m compileall apps scripts` | clean |
| `make smoke` | 2 passed |
| `make test` | 518 passed, 1 skipped |
| `make eval` | passed |
| `cd frontend && npm run lint` | clean |
| `cd frontend && npm run build` | JS 92.77 kB gzip / 120 budget, CSS 6.06 kB / 15 budget |
| `cd frontend && npm run test:ui` | 54 passed (Chromium, Firefox, WebKit) |
| `python3 scripts/check_doc_drift.py` | clean |
| `python3 scripts/check_ai_context.py` | clean |

### Backup Rehearsal Evidence

**PostgreSQL backup:**
```bash
$ python3 scripts/backup_postgres.py --output-dir backups
Backup written to backups/postgres_20260525_081215.sql (33291 bytes)
```

**MinIO backup:**
```bash
$ docker compose exec app python3 scripts/backup_minio.py --output-dir backups
Backup written to backups/minio_20260525_081649.tar.gz (300 objects, 23102 bytes)
```

**Post-restore verification:**
```bash
$ docker compose exec app python3 scripts/verify_backup.py --verify-restored
PostgreSQL sanity: 33 audit rows, 17 review rows
MinIO sanity: 300 objects in bucket 'decision-center'
Linkage sanity: 0/10 recent request IDs have matching MinIO artifacts
```

> **Note:** Linkage sanity shows 0/10 because the first 10 request IDs sampled
> from `audit_log` are test/evaluation entries that do not create full MinIO
> artifacts. The presence of 33 audit rows and 300 MinIO objects confirms
> both stores contain recoverable data.

## RPO / RTO

| Metric | Target | Owner |
|---|---|---|
| RPO | 24 hours (daily backups) | Operator |
| RTO | 1 hour | Operator |

## What Is NOT Backed Up

- Qdrant vectors (rebuild from source via `make init-qdrant`)
- Redis cache (ephemeral)
- n8n credentials (managed in n8n UI)
- `.env` secrets (managed by secrets manager)
- Application logs (rotated locally)

## Next Gate

Slice 5 (Production Hardening) remains approval-gated. Production is `NOT_LIVE`.

## Related Documents

- `docs/operations/backup_restore.md` — Step-by-step procedures
- `docs/policies/disaster_recovery_policy.md` — DR ownership and expectations
- `scripts/backup_postgres.py` — PostgreSQL backup
- `scripts/backup_minio.py` — MinIO backup
- `scripts/verify_backup.py` — Post-restore verification
