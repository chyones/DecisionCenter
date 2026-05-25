#!/usr/bin/env python3
"""Backup MinIO bucket to a timestamped tarball.

Usage:
    PYTHONPATH=. python3 scripts/backup_minio.py --output-dir backups

Requires the MinIO Python SDK (already installed as a project dependency).
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from minio import Minio

from apps.edr.config import settings


def _minio_client(fallback_host: str | None = None) -> Minio:
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    host_port = endpoint.replace("http://", "").replace("https://", "")
    secure = endpoint.startswith("https://")

    try:
        client = Minio(
            host_port,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
        )
        client.bucket_exists(settings.minio_bucket)
        return client
    except Exception:
        if fallback_host:
            # Replace the hostname portion with the fallback
            port = host_port.rsplit(":", 1)[1] if ":" in host_port else "9000"
            fallback_endpoint = f"{fallback_host}:{port}"
            client = Minio(
                fallback_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=secure,
            )
            return client
        raise


def backup_minio(output_dir: Path, fallback_host: str | None = None) -> Path:
    """Download all objects from the configured bucket and create a tarball."""
    output_dir.mkdir(parents=True, exist_ok=True)

    client = _minio_client(fallback_host=fallback_host)
    bucket = settings.minio_bucket

    if not client.bucket_exists(bucket):
        raise RuntimeError(f"Bucket '{bucket}' does not exist")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    staging_dir = output_dir / f"minio_{timestamp}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    objects = list(client.list_objects(bucket, recursive=True))
    if not objects:
        print("Warning: bucket is empty — no objects to back up")

    for obj in objects:
        local_path = staging_dir / obj.object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(bucket, obj.object_name, str(local_path))

    tar_path = output_dir / f"minio_{timestamp}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(staging_dir, arcname=staging_dir.name)

    # Clean up the uncompressed staging directory
    import shutil

    shutil.rmtree(staging_dir)

    size = tar_path.stat().st_size
    print(f"Backup written to {tar_path} ({len(objects)} objects, {size} bytes)")
    return tar_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup MinIO bucket")
    parser.add_argument(
        "--output-dir",
        default="backups",
        help="Output directory (default: backups)",
    )
    args = parser.parse_args()

    try:
        # Auto-detect host fallback: if endpoint is a Docker service name,
        # try localhost when running from the host.
        fallback = None
        endpoint = settings.minio_endpoint
        if endpoint.startswith(("minio:", "minio-")):
            fallback = "127.0.0.1"
        backup_minio(Path(args.output_dir), fallback_host=fallback)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
