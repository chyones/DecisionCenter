#!/usr/bin/env python3
"""Runtime verification A/B/C/D against the rebuilt NOT_LIVE stack.

Uses FastAPI TestClient with a dependency override for auth so the live
connectors are exercised without a real Entra token. This is intentionally
NOT a mocked test — it drives the real app and connectors end-to-end.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi.testclient import TestClient

from apps.edr.app import app, _extract_claims
from apps.edr.auth.validator import JWTClaims


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "A — biggest problem management question",
        "query": "what is the biggest problem for this project",
        "project_code": "PRJ-001",
        "expected_title_keyword": "Management Question",
        "checks": {
            "mqa_required": True,
            "project_name_required": True,
        },
    },
    {
        "name": "B — management decision recommendation",
        "query": "what should management decide this week for the project",
        "project_code": "PRJ-001",
        "expected_title_keyword": "Management Question",
        "checks": {
            "mqa_required": True,
            "project_name_required": True,
        },
    },
    {
        "name": "C — weak evidence / out-of-scope question",
        "query": "will the lunar eclipse delay the project",
        "project_code": "PRJ-001",
        "expected_title_keyword": None,
        "checks": {
            "no_fabrication": True,
            "project_name_required": True,
        },
    },
    {
        "name": "D — salary/payroll data report",
        "query": "give me salary report by staff name and file id for this project",
        "project_code": "PRJ-001",
        "expected_title_keyword": "Salary Payroll",
        "checks": {
            "mqa_forbidden": True,
            "no_salary_table": True,
            "timeout_semantics": True,
            "project_name_required": True,
        },
    },
]


@contextmanager
def _auth_override(role: str = "admin") -> Iterator[TestClient]:
    def _claims() -> JWTClaims:
        return JWTClaims(user_id="runtime-verify", role=role)

    app.dependency_overrides[_extract_claims] = _claims
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(_extract_claims, None)


def _markdown_sections(md: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in md.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _check_project_name(title: str, scenario: dict, errors: list[str]) -> None:
    if scenario["project_code"] not in title:
        errors.append(f"project code not in title: {title}")
    if "Civil Defense building" not in title:
        errors.append(f"verified project name not in title: {title}")


def _check_mqa(md: str, required: bool, errors: list[str]) -> None:
    has_mqa = "## Management Question Answer" in md
    if required and not has_mqa:
        errors.append("Management Question Answer section missing")
    if not required and has_mqa:
        errors.append("Management Question Answer section unexpectedly present")


def _check_no_fabrication(md: str, errors: list[str]) -> None:
    sections = _markdown_sections(md)
    # Only check analytical sections; the query line itself contains the phrase.
    analytical = "\n".join(
        "\n".join(sections.get(h, []))
        for h in ("1. Executive Summary", "3. Key Findings", "Management Question Answer")
    ).lower()
    if "lunar eclipse" not in analytical:
        return
    # Accept reports that explicitly state there is no evidence of impact.
    if "no evidence" in analytical or "not pose" in analytical or "not a risk" in analytical:
        return
    errors.append("report fabricates a causal impact for the lunar eclipse")


def _check_no_salary_table(md: str, errors: list[str]) -> None:
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if "|" in line and "Staff Name" in line and "File ID" in line:
            errors.append("possible fabricated staff/file-id/salary table found")
            return


def _check_timeout_semantics(md: str, errors: list[str]) -> None:
    sections = _markdown_sections(md)
    missing = "\n".join(sections.get("Missing Data / Assumptions", [])).lower()
    if "timeout" in missing and ("inconclusive" not in missing and "not confirmed" not in missing):
        errors.append("timeout source described without 'inconclusive'/'not confirmed'")
    if "no data" in missing or "empty" in missing:
        errors.append("timeout source described as 'no data' or 'empty'")


def _poll_status(client: TestClient, request_id: str, max_wait_s: int = 600) -> dict[str, Any]:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        resp = client.get(f"/reports/{request_id}/status", timeout=30)
        if resp.status_code != 200:
            return {"error": f"status HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        state = data.get("state")
        if state in ("final", "staging", "failed", "error") or data.get("is_terminal"):
            return data
        time.sleep(3)
    return {"error": f"polling timed out after {max_wait_s}s"}


def _run_scenario(client: TestClient, scenario: dict) -> dict[str, Any]:
    result: dict[str, Any] = {"name": scenario["name"], "errors": []}
    body = {
        "user_id": "runtime-verify",
        "query": scenario["query"],
        "project_code": scenario["project_code"],
        "output_formats": ["md"],
    }
    resp = client.post("/reports/staging", json=body, timeout=30)
    result["http_status"] = resp.status_code
    if resp.status_code != 200:
        result["errors"].append(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return result

    data = resp.json()
    result["request_id"] = data.get("request_id")
    request_id = data.get("request_id")

    status = _poll_status(client, request_id)
    if "error" in status:
        result["errors"].append(status["error"])
        return result

    result["quality_gate"] = status.get("quality_gate")
    result["status"] = status.get("state")

    content_resp = client.get(f"/reports/{request_id}/content", timeout=30)
    if content_resp.status_code != 200:
        result["errors"].append(
            f"content HTTP {content_resp.status_code}: {content_resp.text[:200]}"
        )
        return result

    content = content_resp.json()
    md = content.get("markdown") or ""
    result["markdown_title"] = md.splitlines()[0] if md else ""

    keyword = scenario["expected_title_keyword"]
    if keyword and keyword not in result["markdown_title"]:
        result["errors"].append(
            f"title keyword '{keyword}' not found in: {result['markdown_title']}"
        )

    checks = scenario["checks"]
    if checks.get("project_name_required"):
        _check_project_name(result["markdown_title"], scenario, result["errors"])
    if "mqa_required" in checks:
        _check_mqa(md, checks["mqa_required"], result["errors"])
    if checks.get("mqa_forbidden"):
        _check_mqa(md, False, result["errors"])
    if checks.get("no_fabrication"):
        _check_no_fabrication(md, result["errors"])
    if checks.get("no_salary_table"):
        _check_no_salary_table(md, result["errors"])
    if checks.get("timeout_semantics"):
        _check_timeout_semantics(md, result["errors"])

    return result


def main() -> int:
    results: list[dict[str, Any]] = []
    with _auth_override("admin") as client:
        for scenario in SCENARIOS:
            results.append(_run_scenario(client, scenario))

    all_ok = all(not r["errors"] for r in results)
    for r in results:
        status = "PASS" if not r["errors"] else "FAIL"
        print(f"[{status}] {r['name']}")
        print(
            f"    http={r.get('http_status')} qg={r.get('quality_gate')} status={r.get('status')}"
        )
        print(f"    request_id={r.get('request_id')} title={r.get('markdown_title')}")
        for err in r["errors"]:
            print(f"    ERROR: {err}")

    print(
        f"\nOverall: {'PASS' if all_ok else 'FAIL'} ({len([r for r in results if not r['errors']])}/{len(results)})"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
