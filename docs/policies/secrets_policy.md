# Secrets Management Policy

## Scope

This policy governs how credentials, API keys, tokens, and other secrets are
managed for the DecisionCenter application and its infrastructure.

## Principles

1. **Secrets never enter git.**  `.env`, `.env.local`, `.env.production`, and any
   file containing real credentials are excluded from version control.
2. **Production secrets are rotated before go-live.**  Every placeholder value
   in `.env.example` must be replaced with a unique, strong secret before the
   first production deployment.
3. **Secrets are stored in an approved secrets manager.**  The production server
   `.env` is maintained by the operator outside of git.
4. **Default values are obviously unsafe.**  The `.env.example` file uses
   `"change-me"` and empty strings so that a missing production value fails
   loudly rather than silently using a default.

## Secret Inventory

| Secret | Location (runtime) | Rotation Required | Rotation Owner |
|---|---|---|---|
| `POSTGRES_PASSWORD` | `.env` | Yes — before go-live | Operator |
| `MINIO_SECRET_KEY` | `.env` | Yes — before go-live | Operator |
| `ENTRA_CLIENT_SECRET` | `.env` | Yes — before go-live | Operator |
| `ANTHROPIC_API_KEY` | `.env` | Yes — before go-live | Operator |
| `VOYAGE_API_KEY` | `.env` | Yes — before go-live | Operator |
| `COHERE_API_KEY` | `.env` | Yes — before go-live | Operator |
| `N8N_WEBHOOK_TOKEN` | `.env` | Yes — before go-live | Operator |
| `OWNCLOUD_PASSWORD` | n8n container env | Yes — before go-live | Operator |
| `ODOO_API_KEY` | n8n container env | Yes — before go-live | Operator |
| `JWT_SECRET_KEY` (if added later) | `.env` | Yes — before go-live | Operator |
| `LANGFUSE_SECRET_KEY` | `.env` | Recommended on compromise | Operator |

## Rotation Procedure

1. Generate a new secret using a cryptographically secure random generator.
2. Update the production `.env` on the server.
3. Restart the affected service(s) with `docker compose up -d`.
4. Verify the application still functions (`make smoke`).
5. Revoke the old secret at the provider (where applicable — e.g. Entra, MinIO).

## Leak Response

If a secret is accidentally committed to git:

1. **Immediately rotate** the leaked secret at the provider.
2. **Purge** the commit from git history (force-push after `git filter-repo` or
   contact GitHub Support to remove cached data).
3. **Update** the production `.env` with the new secret.
4. **Audit** logs for unauthorized access using the leaked credential.

## n8n Credential Handling

n8n stores its own credentials (ownCloud password, Odoo API key) inside the
n8n SQLite database (`n8n-data`).  These values are passed to the n8n container
via environment variables in `docker-compose.yml`, which reads them from `.env`.
They are **never** sent through webhook request bodies.

## Local Development

Developers may use the `.env.example` defaults or create a local `.env` file.
Local `.env` files must never be committed.

## Verification

Run the automated checker:

```bash
python3 scripts/check_hardening.py
```

This verifies:
- No `.env` files are tracked by git.
- `.env.example` contains no real secrets.
- `.gitignore` excludes sensitive files.

## Related Documents

- `docs/operations/production_hardening_checklist.md` — Full hardening checklist
- `docs/operations/backup_restore.md` — Backup procedures (backup files contain data only, no secrets)
- `docker-compose.yml` — Environment variable injection
