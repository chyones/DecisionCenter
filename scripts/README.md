# Scripts

This directory contains operational and infrastructure utility scripts. Scripts here must stay
outside product workflow behavior unless a later phase explicitly authorizes that work.

| Script | Purpose |
|---|---|
| `init_qdrant.py` | Idempotently creates per-project Qdrant collections using the configured `QDRANT_URL` |
| `init_minio.py` | Idempotently creates the configured MinIO bucket (`MINIO_BUCKET`) |
| `check_doc_drift.py` | Cross-doc invariants: env-key count, "safe next phase" agreement, Phase 1D-fixup marker |
| `check_ai_context.py` | Validates `docs/ai/agent-state.json` shape, status enum, and that `current_commit` is HEAD or an ancestor |
| `backup_postgres.py` | Backs up the PostgreSQL database to a timestamped SQL dump |
| `backup_minio.py` | Backs up the MinIO bucket to a timestamped tarball |
| `restore_postgres.py` | Restores the PostgreSQL database from a SQL dump |
| `restore_minio.py` | Restores the MinIO bucket from a tarball |
| `verify_backup.py` | Verifies backup file integrity and optionally checks live service linkage |

## Usage

```bash
make init-qdrant
```

Direct invocation inside a configured app environment:

```bash
python3 scripts/init_qdrant.py --mapping docs/config/project_source_mapping.json
python3 scripts/init_minio.py            # uses MINIO_BUCKET from .env
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
```

For app tests and evaluation, use the Docker app container (`make smoke`,
`make test`, `make eval`) or the local `.venv` interpreter. Bare system Python
on the host is not a supported test environment because it may not have the
project dependencies installed.

These scripts create infrastructure structure only. They do not embed content, insert vectors,
perform retrieval, or implement product logic.
