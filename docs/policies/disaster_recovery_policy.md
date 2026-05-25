# Disaster Recovery Policy

## Scope

Backups must include:

1. **PostgreSQL** — all relational data (audit logs, reviews, mappings, events).
2. **MinIO** — all report artifacts, evidence packs, and uploaded files.
3. **n8n workflows** — exported periodically from the n8n UI (not automated).
4. **Configuration** — `docker-compose.yml`, `Caddyfile`, and project source
   mapping are versioned in git.

Secrets are backed up through the approved secrets manager, **not** through git
or the backup scripts.

## Roles and Ownership

| Role | Responsibility |
|---|---|
| **Operator** | Executes daily backups, monitors backup size/age, runs restore rehearsals quarterly |
| **Infrastructure Lead** | Validates backup retention policy, verifies off-site copy strategy |
| **Project Owner** | Approves DR budget and RPO/RTO targets |

## Recovery Objectives

| Metric | Target | Justification |
|---|---|---|
| **RPO** | 24 hours | Daily automated backup; acceptable data loss for an internal decision-support system |
| **RTO** | 1 hour | Docker Compose rebuild (~10 min) + PostgreSQL restore (~15 min) + MinIO restore (~20 min) + smoke tests (~15 min) |

## Backup Retention

- **Daily** backups retained for **7 days** on the Hetzner host.
- **Weekly** snapshots (operator manually copies one daily backup each week)
  retained for **4 weeks**.
- Off-site copies are the operator's responsibility and are outside the scope
  of automated scripts.

## Restore Rehearsal

A full restore rehearsal must be performed:

- **Quarterly** on a non-production target (separate host or local Docker).
- **After every major release** that changes the persistence schema.
- Evidence (transcript of `scripts/verify_backup.py --verify-restored`) must be
  retained by the operator for compliance.

## Go / No-Go for Production

Production may **not** be declared live until:

1. ✅ At least one successful restore rehearsal has been executed and verified.
2. ✅ Backup scripts are documented and tested (Slice 4 evidence).
3. ✅ An operator is assigned DR ownership.
4. ✅ RPO and RTO are agreed upon by the project owner.

## Current Status

| Criterion | Status |
|---|---|
| Backup scripts implemented | ✅ Complete |
| Restore scripts implemented | ✅ Complete |
| Backup/restore documentation | ✅ Complete |
| Restore rehearsal evidence | 🟡 Operator-run quarterly |
| Off-site backup strategy | 🔴 Operator responsibility |
| DR ownership assigned | 🔴 Pending operator action |

## Related Documents

- `docs/operations/backup_restore.md` — Step-by-step backup and restore procedures
- `docs/operations/runbook.md` — Bring-up and common operational commands
- `scripts/backup_postgres.py` — PostgreSQL backup script
- `scripts/backup_minio.py` — MinIO backup script
- `scripts/verify_backup.py` — Post-restore verification script
