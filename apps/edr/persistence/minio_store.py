"""MinIO artifact store for staging reports."""
from __future__ import annotations

import json
from typing import Any

from minio import Minio
from minio.error import S3Error

from apps.edr.config import settings


class MinioStore:
    """Idempotent MinIO bucket and artifact operations."""

    def __init__(self) -> None:
        endpoint = settings.minio_endpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        self._client = Minio(
            endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=endpoint.startswith("https://"),
        )
        self._bucket: str = settings.minio_bucket

    def _ensure_bucket(self) -> None:
        """Create bucket if it does not exist (idempotent)."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def _object_name(self, request_id: str, filename: str) -> str:
        return f"staging/{request_id}/{filename}"

    def put_json(self, request_id: str, filename: str, data: dict[str, Any]) -> str:
        """Store a JSON artifact and return its object key."""
        self._ensure_bucket()
        object_name = self._object_name(request_id, filename)
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        from io import BytesIO

        self._client.put_object(
            self._bucket,
            object_name,
            data=BytesIO(body),
            length=len(body),
            content_type="application/json",
        )
        return object_name

    def put_bytes(
        self, request_id: str, filename: str, data: bytes, content_type: str
    ) -> str:
        """Store a binary artifact and return its object key."""
        self._ensure_bucket()
        object_name = self._object_name(request_id, filename)
        from io import BytesIO

        self._client.put_object(
            self._bucket,
            object_name,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def get_object(self, request_id: str, filename: str) -> bytes:
        """Retrieve an artifact by request_id and filename."""
        object_name = self._object_name(request_id, filename)
        response = self._client.get_object(self._bucket, object_name)
        return response.read()

    def object_exists(self, request_id: str, filename: str) -> bool:
        """Check whether an artifact exists."""
        object_name = self._object_name(request_id, filename)
        try:
            self._client.stat_object(self._bucket, object_name)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise


_minio_store: MinioStore | None = None


def get_minio_store() -> MinioStore:
    global _minio_store
    if _minio_store is None:
        _minio_store = MinioStore()
    return _minio_store
