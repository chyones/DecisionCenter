#!/usr/bin/env python3
"""Deterministic local Phase 2A E2E validation harness.

The harness replaces external connector calls with a fixed local evidence
fixture, then drives the public API through the normal staging, approval,
publish, and final download path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.edr.app import app
from apps.edr.config import settings
from apps.edr.schemas.evidence import EvidenceObject


REQUESTER = "project-prj-001@example.com"
REVIEWER = "phase2a-reviewer@example.com"
PROJECT_CODE = "PRJ-001"


class _FixtureEmbeddingClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * 8 for _ in texts]


class _FixtureEvidenceStore:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def ensure_collection(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def upsert_evidence(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def _fixture_evidence() -> EvidenceObject:
    excerpt = (
        "PRJ-001 validated project status: foundations are complete, "
        "steel procurement is approved, and commissioning readiness is "
        "tracked through document control."
    )
    return EvidenceObject(
        evidence_id="ev_phase2a_local_sharepoint_001",
        source_type="sharepoint",
        source_uri="fixture://phase2a/prj-001/status-report.md",
        title="PRJ-001 Controlled Status Report",
        project_code=PROJECT_CODE,
        contract_no="CON-PRJ-001",
        revision="R1",
        timestamp="2026-05-14T08:00:00Z",
        excerpt=excerpt,
        hash_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        confidence="high",
        tags=["phase2a", "local-validation", "status"],
        metadata={"fixture": True, "validation_scope": "phase2a_e2e"},
    )


async def _search_sharepoint_fixture(_payload: dict[str, Any]) -> list[EvidenceObject]:
    return [_fixture_evidence()]


async def _empty_connector_fixture(_payload: dict[str, Any]) -> list[EvidenceObject]:
    return []


@contextmanager
def _local_validation_fixture() -> Iterator[None]:
    connector_patches = [
        patch(
            "apps.edr.graph.node_05_sharepoint.search_sharepoint",
            _search_sharepoint_fixture,
        ),
        patch("apps.edr.graph.node_06_owncloud.list_owncloud", _empty_connector_fixture),
        patch("apps.edr.graph.node_07_email.search_email", _empty_connector_fixture),
        patch("apps.edr.graph.node_08_odoo.read_odoo", _empty_connector_fixture),
    ]
    storage_patches = []
    for module in (
        "apps.edr.graph.node_05_sharepoint",
        "apps.edr.graph.node_06_owncloud",
        "apps.edr.graph.node_07_email",
        "apps.edr.graph.node_08_odoo",
    ):
        storage_patches.extend(
            [
                patch(f"{module}.EmbeddingClient", _FixtureEmbeddingClient),
                patch(f"{module}.EvidenceStore", _FixtureEvidenceStore),
            ]
        )

    with ExitStack() as stack:
        for patcher in connector_patches + storage_patches:
            stack.enter_context(patcher)
        yield


def _headers(user_id: str) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-User-Role": "executive",
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if settings.app_env == "production":
        raise RuntimeError("Phase 2A local E2E validation is blocked in production.")

    with _local_validation_fixture(), TestClient(app) as client:
        staging_response = client.post(
            "/reports/staging",
            headers=_headers(REQUESTER),
            json={
                "user_id": REQUESTER,
                "query": (
                    "Summarize the current PRJ-001 project status from "
                    "validated records."
                ),
                "project_code": PROJECT_CODE,
                "output_formats": ["md"],
            },
        )
        _require(
            staging_response.status_code == 200,
            f"submit failed: {staging_response.status_code} {staging_response.text}",
        )
        staging = staging_response.json()
        request_id = staging["request_id"]
        visited_nodes = staging["visited_nodes"]

        _require(staging["quality_gate"] == "passed", "quality_gate did not pass")
        _require(staging["status"] == "ready", "staging report was not ready")
        _require(len(visited_nodes) == 18, "workflow did not visit all 18 nodes")

        status_response = client.get(
            f"/reports/{request_id}/status",
            headers=_headers(REQUESTER),
        )
        _require(status_response.status_code == 200, "status lookup failed")
        pre_approval_status = status_response.json()
        _require(pre_approval_status["state"] == "staging", "report skipped staging")
        _require(
            pre_approval_status["quality_gate"] == "passed",
            "status did not preserve passed quality gate",
        )

        blocked_download = client.get(
            f"/reports/staging/{request_id}/download/md",
            headers=_headers(REQUESTER),
        )
        _require(
            blocked_download.status_code == 403,
            "staging download was allowed before approval",
        )

        approval_response = client.post(
            f"/reports/staging/{request_id}/approve",
            headers=_headers(REVIEWER),
            json={"comment": "Phase 2A deterministic local E2E approval."},
        )
        _require(
            approval_response.status_code == 200,
            f"approval failed: {approval_response.status_code} {approval_response.text}",
        )
        approval = approval_response.json()
        _require(approval["new_state"] == "approved", "approval was not recorded")
        _require(approval["publish_status"] == "published", "final publish failed")

        final_status_response = client.get(
            f"/reports/{request_id}/status",
            headers=_headers(REVIEWER),
        )
        _require(final_status_response.status_code == 200, "final status lookup failed")
        final_status = final_status_response.json()
        _require(final_status["state"] == "final", "report did not reach final state")

        download_response = client.get(
            f"/reports/final/{request_id}/download/md",
            headers=_headers(REVIEWER),
        )
        _require(
            download_response.status_code == 200,
            f"final markdown download failed: {download_response.status_code}",
        )
        markdown = download_response.text
        _require("# Executive Decision Report" in markdown, "markdown title missing")
        _require("Quality Gate | passed" in markdown, "quality gate marker missing")
        _require(
            "PRJ-001 Controlled Status Report" in markdown,
            "fixture evidence title missing from markdown",
        )

    print(
        json.dumps(
            {
                "result": "PASS",
                "request_id": request_id,
                "workflow_nodes_visited": len(visited_nodes),
                "quality_gate": staging["quality_gate"],
                "pre_approval_download_status": blocked_download.status_code,
                "approval_state": approval["new_state"],
                "publish_status": approval["publish_status"],
                "final_state": final_status["state"],
                "final_markdown_bytes": len(download_response.content),
                "fixture_evidence_id": _fixture_evidence().evidence_id,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
