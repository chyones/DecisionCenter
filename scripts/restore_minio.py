#!/usr/bin/env python3
"""Restore MinIO bucket from a tarball.

Usage:
    PYTHONPATH=. python3 scripts/restore_minio.py backups/minio_20260115_120000.tar.gz

Requires the MinIO Python SDK (already installed as a project dependency).
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import tempfile
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


def restore_minio(tar_file: Path, fallback_host: str | None = None) -> None:
    """Restore objects to the configured MinIO bucket from a tarball."""
    if not tar_file.exists():
        raise FileNotFoundError(f"Backup file not found: {tar_file}")

    client = _minio_client(fallback_host=fallback_host)
    bucket = settings.minio_bucket

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Created bucket: {bucket}")

    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(tar_file, "r:gz") as tar:
            tar.extractall(path=tmpdir)

        # The tarball contains a single directory (e.g. minio_20260115_120000)
        extracted = Path(tmpdir)
        subdirs = [d for d in extracted.iterdir() if d.is_dir()]
        if not subdirs:
            raise RuntimeError("Tarball does not contain a top-level directory")

        root_dir = subdirs[0]
        files = list(root_dir.rglob("*"))
        file_count = 0

        for file_path in files:
            if file_path.is_file():
                object_name = str(file_path.relative_to(root_dir)).replace("\\", "/")
                client.fput_object(bucket, object_name, str(file_path))
                file_count += 1

    print(f"Restored {file_count} objects to bucket '{bucket}' from {tar_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore MinIO bucket")
    parser.add_argument("tar_file", help="Path to the MinIO backup tarball")
    args = parser.parse_args()

    try:
        fallback = None
        endpoint = settings.minio_endpoint
        if endpoint.startswith(("minio:", "minio-")):
            fallback = "127.0.0.1"
        restore_minio(Path(args.tar_file), fallback_host=fallback)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
