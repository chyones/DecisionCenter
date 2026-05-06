# Runbook

## Bring Up

```bash
cp .env.example .env
make up
make smoke
```

## Common Commands

```bash
make ps
make logs
make down
```

## First Production Checklist

- Fill `.env` with real credentials.
- Implement, import, and activate n8n workflows; current repo workflow JSON files are placeholders.
- Confirm RBAC project mappings.
- Run the smoke tests and golden set.
