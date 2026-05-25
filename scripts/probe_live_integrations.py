#!/usr/bin/env python3
"""Live Integration Probe — Operator script for Phase 2D Slice 3.

Run this on the target environment after ``make up`` to validate that all
integrations are reachable and behave explicitly (no silent success).

Usage (inside the app container):
    python scripts/probe_live_integrations.py

Exit codes:
    0 — all reachable integrations passed (skipped services do not fail the run)
    1 — at least one integration failed explicitly
"""

from __future__ import annotations

import socket
import sys
from urllib.parse import urlparse

import httpx

from apps.edr.config import settings


def _postgres() -> tuple[bool, str]:
    if not settings.postgres_host:
        return True, "SKIP — POSTGRES_HOST not configured"
    try:
        import asyncpg
        import asyncio

        async def _check() -> str:
            conn = await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
            )
            try:
                result = await conn.fetch("SELECT 1")
                assert result[0][0] == 1
                return "SELECT 1 OK"
            finally:
                await conn.close()

        msg = asyncio.run(_check())
        return True, msg
    except ImportError:
        return False, "FAIL — asyncpg not installed"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _redis() -> tuple[bool, str]:
    if not settings.redis_url:
        return True, "SKIP — REDIS_URL not configured"
    parsed = urlparse(settings.redis_url)
    if parsed.scheme != "redis" or not parsed.hostname:
        return True, "SKIP — REDIS_URL is not a redis:// URL"
    host, port = parsed.hostname, parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            pong = sock.recv(16)
            if not pong.startswith(b"+PONG"):
                return False, f"FAIL — Expected +PONG, got {pong!r}"
        return True, "PONG"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _qdrant() -> tuple[bool, str]:
    if not settings.qdrant_url:
        return True, "SKIP — QDRANT_URL not configured"
    try:
        resp = httpx.get(f"{settings.qdrant_url.rstrip('/')}/collections", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", {})
        count = len(result.get("collections", []))
        return True, f"OK — {count} collection(s)"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _minio() -> tuple[bool, str]:
    if not settings.minio_endpoint:
        return True, "SKIP — MINIO_ENDPOINT not configured"
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    try:
        resp = httpx.get(f"{endpoint.rstrip('/')}/minio/health/ready", timeout=5)
        resp.raise_for_status()
        return True, "OK"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _langfuse() -> tuple[bool, str]:
    if not settings.langfuse_host:
        return True, "SKIP — LANGFUSE_HOST not configured"
    try:
        resp = httpx.get(
            f"{settings.langfuse_host.rstrip('/')}/api/public/health", timeout=10
        )
        if resp.status_code >= 500:
            return False, f"FAIL — server error {resp.status_code}"
        return True, f"REACHABLE — {resp.status_code}"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _n8n() -> tuple[bool, str]:
    if not settings.n8n_base_url:
        return True, "SKIP — N8N_BASE_URL not configured"
    try:
        resp = httpx.get(f"{settings.n8n_base_url.rstrip('/')}/healthz", timeout=5)
        resp.raise_for_status()
        return True, "OK"
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"


def _webhook(name: str, path_setting: str | None) -> tuple[bool, str]:
    if not settings.n8n_base_url:
        return True, "SKIP — N8N_BASE_URL not configured"
    if not path_setting:
        return True, f"SKIP — {name.upper()}_WEBHOOK not configured"
    url = f"{settings.n8n_base_url.rstrip('/')}/{path_setting.lstrip('/')}"
    try:
        resp = httpx.post(url, json={"query": "test"}, timeout=5)
    except Exception as exc:
        return False, f"FAIL — {type(exc).__name__}: {exc}"
    if resp.status_code == 200:
        return False, f"FAIL — returned 200 (possible silent success)"
    return True, f"EXPLICIT_FAILURE — {resp.status_code}"


SERVICES: list[tuple[str, callable]] = [
    ("PostgreSQL", _postgres),
    ("Redis", _redis),
    ("Qdrant", _qdrant),
    ("MinIO", _minio),
    ("Langfuse", _langfuse),
    ("n8n", _n8n),
    ("SharePoint", lambda: _webhook("sharepoint", settings.sharepoint_search_webhook)),
    ("Microsoft Graph (Email)", lambda: _webhook("email", settings.email_search_webhook)),
    ("ownCloud", lambda: _webhook("owncloud", settings.owncloud_list_webhook)),
    ("Odoo", lambda: _webhook("odoo", settings.odoo_read_webhook)),
]


def main() -> int:
    print("Phase 2D Slice 3 — Live Integration Probes")
    print("-" * 60)
    any_fail = False
    for name, probe in SERVICES:
        ok, detail = probe()
        if detail.startswith("SKIP"):
            status = "SKIP"
        elif ok:
            status = "PASS"
        else:
            status = "FAIL"
            any_fail = True
        print(f"{name:28s} {status:6s} {detail}")
    print("-" * 60)
    if any_fail:
        print("Result: FAIL — at least one integration did not pass")
        return 1
    print("Result: PASS — all reachable integrations OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
