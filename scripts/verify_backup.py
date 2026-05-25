#!/usr/bin/env python3
"""Verify backup integrity and optionally verify restored data.

Usage:
    # Verify a PostgreSQL backup file exists and is non-empty
    PYTHONPATH=. python3 scripts/verify_backup.py --postgres backups/postgres_20260115_120000.sql

    # Verify a MinIO backup file exists and is non-empty
    PYTHONPATH=. python3 scripts/verify_backup.py --minio backups/minio_20260115_120000.tar.gz

    # Verify both backups and check restored data links
    PYTHONPATH=. python3 scripts/verify_backup.py \
        --postgres backups/postgres_20260115_120000.sql \
        --minio backups/minio_20260115_120000.tar.gz \
        --verify-restored

The ``--verify-restored`` flag runs a lightweight sanity check against the live
PostgreSQL and MinIO services to confirm that audit/report data is present and
that request IDs in Postgres link to objects in MinIO.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path


def verify_postgres_backup(sql_file: Path) -> None:
    """Check that the SQL dump file exists and contains expected schema markers."""
    if not sql_file.exists():
        raise FileNotFoundError(f"PostgreSQL backup not found: {sql_file}")

    size = sql_file.stat().st_size
    if size == 0:
        raise RuntimeError(f"PostgreSQL backup is empty: {sql_file}")

    text = sql_file.read_text(encoding="utf-8")
    required_markers = [
        "CREATE TABLE",
        "audit_log",
    ]
    missing = [m for m in required_markers if m not in text]
    if missing:
        raise RuntimeError(
            f"PostgreSQL backup missing markers: {missing}"
        )

    print(f"PostgreSQL backup OK: {sql_file} ({size} bytes, markers present)")


def verify_minio_backup(tar_file: Path) -> None:
    """Check that the tarball exists, is readable, and contains objects."""
    if not tar_file.exists():
        raise FileNotFoundError(f"MinIO backup not found: {tar_file}")

    size = tar_file.stat().st_size
    if size == 0:
        raise RuntimeError(f"MinIO backup is empty: {tar_file}")

    with tarfile.open(tar_file, "r:gz") as tar:
        members = tar.getmembers()
        if not members:
            raise RuntimeError(f"MinIO backup tarball is empty: {tar_file}")

        # Look for at least one JSON or MD file (typical artifacts)
        has_artifact = any(
            m.name.endswith((".json", ".md", ".eml")) for m in members
        )
        if not has_artifact:
            print(
                "Warning: no typical artifacts (.json/.md/.eml) found in tarball",
                file=sys.stderr,
            )

    print(
        f"MinIO backup OK: {tar_file} ({size} bytes, {len(members)} members)"
    )


async def _verify_restored_data() -> None:
    """Run a lightweight sanity check against live services."""
    import asyncpg

    from apps.edr.config import settings
    from apps.edr.persistence.minio_store import MinioStore

    # Check PostgreSQL for audit rows
    conn = None
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=5,
        )
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM audit_log"
        )
        audit_count = row["cnt"] if row else 0

        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM review_decisions"
        )
        review_count = row["cnt"] if row else 0
    finally:
        if conn:
            await conn.close()

    print(f"PostgreSQL sanity: {audit_count} audit rows, {review_count} review rows")

    # Check MinIO for objects
    store = MinioStore()
    client = store._client
    bucket = settings.minio_bucket
    if not client.bucket_exists(bucket):
        raise RuntimeError(f"MinIO bucket '{bucket}' does not exist")

    objects = list(client.list_objects(bucket, recursive=True))
    print(f"MinIO sanity: {len(objects)} objects in bucket '{bucket}'")

    # Verify linkage: at least one request ID appears in both Postgres and MinIO
    conn = None
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=5,
        )
        rows = await conn.fetch(
            "SELECT request_id FROM audit_log WHERE request_id IS NOT NULL LIMIT 10"
        )
        request_ids = [r["request_id"] for r in rows]
    finally:
        if conn:
            await conn.close()

    linked = 0
    for req_id in request_ids:
        prefix = f"final/{req_id}/"
        exists = any(
            obj.object_name.startswith(prefix) for obj in objects
        )
        if exists:
            linked += 1

    print(
        f"Linkage sanity: {linked}/{len(request_ids)} recent request IDs "
        f"have matching MinIO artifacts"
    )

    if audit_count == 0 and len(objects) == 0:
        raise RuntimeError(
            "No data found in PostgreSQL or MinIO — restore may have failed"
        )


def verify_restored_data() -> None:
    import asyncio
    asyncio.run(_verify_restored_data())


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify backup integrity")
    parser.add_argument(
        "--postgres",
        type=Path,
        help="Path to a PostgreSQL backup SQL file",
    )
    parser.add_argument(
        "--minio",
        type=Path,
        help="Path to a MinIO backup tarball",
    )
    parser.add_argument(
        "--verify-restored",
        action="store_true",
        help="Also verify live services contain linked audit/report data",
    )
    args = parser.parse_args()

    if not args.postgres and not args.minio and not args.verify_restored:
        parser.error("Specify at least one of --postgres, --minio, --verify-restored")

    try:
        if args.postgres:
            verify_postgres_backup(args.postgres)
        if args.minio:
            verify_minio_backup(args.minio)
        if args.verify_restored:
            verify_restored_data()
        return 0
    except Exception as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
