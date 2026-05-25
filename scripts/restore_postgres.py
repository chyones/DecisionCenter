#!/usr/bin/env python3
"""Restore PostgreSQL database from a SQL dump.

Usage (host, with Docker Compose):
    python3 scripts/restore_postgres.py backups/postgres_20260115_120000.sql

Usage (inside app container, after image rebuild with postgresql-client):
    python3 scripts/restore_postgres.py backups/postgres_20260115_120000.sql

WARNING: This drops and recreates the target database. Run only after
confirming the backup file is valid and the target is the correct environment.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _psql_cmd() -> list[str]:
    """Return the psql command prefix (list of strings)."""
    user = _get_env("POSTGRES_USER", "decision_center")
    host = _get_env("POSTGRES_HOST", "postgres")

    docker_available = subprocess.run(
        ["docker", "compose", "version"], capture_output=True
    ).returncode == 0

    if docker_available and host in ("postgres", "db", "localhost"):
        return [
            "docker", "compose", "exec", "-T", "postgres",
            "psql",
            "-U", user,
            "-v", "ON_ERROR_STOP=1",
        ]

    direct = subprocess.run(
        ["which", "psql"], capture_output=True, text=True
    )
    if direct.returncode == 0:
        port = _get_env("POSTGRES_PORT", "5432")
        return [
            "psql",
            "-h", host,
            "-p", port,
            "-U", user,
            "-v", "ON_ERROR_STOP=1",
        ]

    raise RuntimeError(
        "psql not found and docker compose is unavailable. "
        "Install postgresql-client or ensure Docker Compose is running."
    )


def restore_postgres(sql_file: Path) -> None:
    """Restore the database from a SQL dump file."""
    if not sql_file.exists():
        raise FileNotFoundError(f"Backup file not found: {sql_file}")

    cmd = _psql_cmd()
    env = os.environ.copy()
    if "PGPASSWORD" not in env:
        env["PGPASSWORD"] = _get_env("POSTGRES_PASSWORD", "change-me")

    with open(sql_file, "r", encoding="utf-8") as fh:
        result = subprocess.run(
            cmd,
            stdin=fh,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    if result.returncode != 0:
        raise RuntimeError(f"psql restore failed: {result.stderr.strip()}")

    print(f"Database restored from {sql_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore PostgreSQL database")
    parser.add_argument("sql_file", help="Path to the SQL dump file")
    args = parser.parse_args()

    try:
        restore_postgres(Path(args.sql_file))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
