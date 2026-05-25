#!/usr/bin/env python3
"""Backup PostgreSQL database to a timestamped SQL dump.

Usage (host, with Docker Compose):
    python3 scripts/backup_postgres.py --output-dir backups

Usage (inside app container, after image rebuild with postgresql-client):
    python3 scripts/backup_postgres.py --output-dir backups

The script tries ``pg_dump`` directly first; if unavailable it falls back to
``docker compose exec -T postgres pg_dump``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _pg_dump_cmd() -> list[str]:
    """Return the pg_dump command prefix (list of strings)."""
    db = _get_env("POSTGRES_DB", "decision_center")
    user = _get_env("POSTGRES_USER", "decision_center")
    host = _get_env("POSTGRES_HOST", "postgres")

    docker_available = subprocess.run(
        ["docker", "compose", "version"], capture_output=True
    ).returncode == 0

    # Prefer docker compose exec when the host looks like a Docker service name
    # (common names or when direct resolution fails).
    if docker_available and host in ("postgres", "db", "localhost"):
        return [
            "docker", "compose", "exec", "-T", "postgres",
            "pg_dump",
            "-U", user,
            "-d", db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ]

    direct = subprocess.run(
        ["which", "pg_dump"], capture_output=True, text=True
    )
    if direct.returncode == 0:
        port = _get_env("POSTGRES_PORT", "5432")
        return [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ]

    raise RuntimeError(
        "pg_dump not found and docker compose is unavailable. "
        "Install postgresql-client or ensure Docker Compose is running."
    )


def backup_postgres(output_dir: Path) -> Path:
    """Create a timestamped SQL dump and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"postgres_{timestamp}.sql"

    cmd = _pg_dump_cmd()
    env = os.environ.copy()
    if "PGPASSWORD" not in env:
        env["PGPASSWORD"] = _get_env("POSTGRES_PASSWORD", "change-me")

    with open(output_file, "w", encoding="utf-8") as fh:
        result = subprocess.run(
            cmd,
            stdout=fh,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    if result.returncode != 0:
        output_file.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed: {result.stderr.strip()}")

    size = output_file.stat().st_size
    if size == 0:
        output_file.unlink(missing_ok=True)
        raise RuntimeError("pg_dump produced an empty file")

    print(f"Backup written to {output_file} ({size} bytes)")
    return output_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup PostgreSQL database")
    parser.add_argument(
        "--output-dir",
        default="backups",
        help="Output directory (default: backups)",
    )
    args = parser.parse_args()

    try:
        backup_postgres(Path(args.output_dir))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
