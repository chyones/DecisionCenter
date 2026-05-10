"""Initialize the MinIO bucket configured by ``MINIO_BUCKET``.

Idempotent: safe to re-run. Creating the bucket explicitly here keeps the
operational pattern aligned with ``scripts/init_qdrant.py`` and makes the
first Phase 1F write deterministic on a fresh deployment. The runtime
``MinioStore._ensure_bucket()`` covers any missed init, but operators should
prefer running this script once after ``make up``.
"""
from __future__ import annotations

import argparse

from minio import Minio

from apps.edr.config import settings


def _client() -> Minio:
    endpoint = settings.minio_endpoint
    secure = endpoint.startswith("https://")
    host = endpoint.replace("http://", "").replace("https://", "")
    return Minio(
        host,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )


def ensure_bucket(client: Minio, name: str) -> str:
    if client.bucket_exists(name):
        return "exists"
    client.make_bucket(name)
    return "created"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotently create the configured MinIO bucket."
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="Override the bucket name. Defaults to settings.minio_bucket.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bucket = args.bucket or settings.minio_bucket
    if not bucket:
        raise SystemExit(
            "MINIO_BUCKET is not set; pass --bucket or configure the env."
        )
    client = _client()
    status = ensure_bucket(client, bucket)
    print(f"{bucket}: {status}")


if __name__ == "__main__":
    main()
