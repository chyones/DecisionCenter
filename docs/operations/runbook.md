# Runbook

## Bring Up

```bash
cp .env.example .env
# Edit .env with real credentials and PUBLIC_HOSTNAME
make up
python3 scripts/init_qdrant.py --mapping docs/config/project_source_mapping.json
python3 scripts/init_minio.py
make smoke
```

## Common Commands

```bash
make ps
make logs
make down
```

## First Production Checklist

- Fill `.env` with real credentials and set `PUBLIC_HOSTNAME` to a real DNS
  name so Caddy can issue a TLS cert via ACME.
- Import the four workflow files in `n8n/` into the n8n instance and activate
  them. The JSON files contain real 4–5 node pipelines, declare
  `authentication=headerAuth`, and read service-account credentials from
  `$env.OWNCLOUD_*` and `$env.ODOO_*`. Configure the matching n8n credential
  for the Header Auth so `N8N_WEBHOOK_TOKEN` in `.env` matches.
- Confirm RBAC project mappings in `docs/config/project_source_mapping.json`.
- Initialize the Qdrant collections and MinIO bucket (commands above).
- Run `make smoke` and `make test`. The golden-set `make eval` step is
  Phase 1H scope and currently a stub.
