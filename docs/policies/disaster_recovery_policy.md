# Disaster Recovery Policy

Backups must include Postgres, MinIO report artifacts, n8n workflow exports,
and configuration templates. Secrets are backed up through the approved secrets
manager, not through git.
