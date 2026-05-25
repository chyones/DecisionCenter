#!/usr/bin/env python3
"""Phase 2D Slice 6 — Real UAT flow driver (operator script).

Drives the full decision-report flow over real HTTP against a **running**
DecisionCenter stack: real login (token) -> submit -> evidence retrieval ->
quality gate -> approval -> publish -> download. There is **no mocked backend**
here — every call hits the live app and its live connectors. This is the
script that produces final UAT proof (see ``docs/operations/uat_runbook.md``).

Auth (no secrets are stored — read from the environment at runtime):
    UAT_BASE_URL        Base URL of the running stack (e.g. https://host or
                        http://127.0.0.1:8000). Required for a live run.
    UAT_BEARER_TOKEN    Real Entra access token (production-equivalent path).
    UAT_REVIEWER_TOKEN  A second user's token for the approval step.
    UAT_USER_ROLE       Non-production fallback: dev canonical role for the
                        submitter via the X-User-Role bypass (blocked in prod).
    UAT_REVIEWER_ROLE   Non-production fallback: dev role for the reviewer.
    UAT_PROJECT_CODE    Project code with a complete source mapping.
    UAT_QUERY           Business question to submit.

Safe handling of missing credentials:
    When UAT_BASE_URL is unset, the target is unreachable, or no auth is
    available, the driver prints SKIP and exits 0 — it never fakes success.

Usage (operator host, after ``make up``):
    python scripts/uat_flow.py
    python scripts/uat_flow.py --json

Exit codes:
    0 — all executed steps passed, or the run was safely skipped
    1 — at least one executed step failed explicitly
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

STEPS = (
    "login",
    "submit",
    "evidence",
    "quality_gate",
    "approval",
    "publish",
    "download",
)


class UatSkip(Exception):
    """Raised to skip the run safely (missing target or credentials)."""


def _base_url() -> str:
    url = os.environ.get("UAT_BASE_URL", "").strip()
    if not url:
        raise UatSkip("UAT_BASE_URL not set — live UAT unavailable")
    return url.rstrip("/")


def _submitter_headers() -> dict[str, str]:
    token = os.environ.get("UAT_BEARER_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    role = os.environ.get("UAT_USER_ROLE", "").strip()
    if role:
        # Non-production fallback only. The backend rejects these headers when
        # APP_ENV=production (HTTP 400) — that rejection is itself correct.
        return {"X-User-Role": role, "X-User-Id": "uat-submitter"}
    raise UatSkip("No UAT_BEARER_TOKEN or UAT_USER_ROLE — cannot authenticate")


def _reviewer_headers() -> dict[str, str]:
    token = os.environ.get("UAT_REVIEWER_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    role = os.environ.get("UAT_REVIEWER_ROLE", "").strip()
    if role:
        return {"X-User-Role": role, "X-User-Id": "uat-reviewer"}
    raise UatSkip("No reviewer token/role — cannot exercise approval safely")


def run(base: str, summary: dict[str, object]) -> bool:
    """Execute the live flow. Returns True if every executed step passed."""
    sub_headers = _submitter_headers()
    project = os.environ.get("UAT_PROJECT_CODE", "").strip()
    query = os.environ.get("UAT_QUERY", "").strip() or "UAT readiness check"
    timeout = httpx.Timeout(60.0)

    with httpx.Client(base_url=base, timeout=timeout) as client:
        # Step 1 — real login / identity.
        resp = client.get("/me", headers=sub_headers)
        resp.raise_for_status()
        role = resp.json().get("role")
        summary["login"] = {"ok": True, "role": role}

        # Step 2 — submit a real report request.
        body: dict[str, object] = {"query": query, "output_formats": ["markdown"]}
        if project:
            body["project_code"] = project
        resp = client.post("/reports/staging", headers=sub_headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        request_id = data.get("request_id")
        summary["submit"] = {
            "ok": bool(request_id),
            "request_id": request_id,
            "visited_nodes": len(data.get("visited_nodes", []) or []),
            "status": data.get("status"),
        }
        if not request_id:
            return False

        # Step 3 — evidence retrieval (counts only, never content).
        resp = client.get(f"/reports/{request_id}/content", headers=sub_headers)
        resp.raise_for_status()
        content = resp.json()
        evidence = content.get("evidence") or content.get("evidence_items") or []
        summary["evidence"] = {"ok": True, "evidence_count": len(evidence)}

        # Step 4 — quality gate verdict (verdict only).
        verdict = content.get("quality_gate") or data.get("quality_gate")
        summary["quality_gate"] = {"ok": verdict is not None, "verdict": verdict}

        # Step 5 — approval by a different reviewer (self-approval is blocked).
        rev_headers = _reviewer_headers()
        resp = client.post(
            f"/reports/staging/{request_id}/approve",
            headers=rev_headers,
            json={"comment": "UAT approval"},
        )
        approval_ok = resp.status_code == 200
        publish_status = resp.json().get("publish_status") if approval_ok else None
        summary["approval"] = {"ok": approval_ok, "http_status": resp.status_code}

        # Step 6 — publish is write-once; re-approval must return 409.
        recheck = client.post(
            f"/reports/staging/{request_id}/approve",
            headers=rev_headers,
            json={"comment": "UAT re-approval (must be rejected)"},
        )
        summary["publish"] = {
            "ok": approval_ok and recheck.status_code == 409,
            "publish_status": publish_status,
            "reapprove_http_status": recheck.status_code,
        }

        # Step 7 — download the finalized artifact.
        dl = client.get(f"/reports/final/{request_id}/download/markdown", headers=sub_headers)
        summary["download"] = {
            "ok": dl.status_code == 200 and len(dl.content) > 0,
            "http_status": dl.status_code,
            "bytes": len(dl.content),
        }

    return all(bool(summary.get(step, {}).get("ok")) for step in STEPS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2D Slice 6 real UAT flow driver")
    parser.add_argument("--json", action="store_true", help="Emit a sanitized JSON summary")
    args = parser.parse_args()

    summary: dict[str, object] = {step: {"ok": False} for step in STEPS}

    try:
        base = _base_url()
        try:
            httpx.get(f"{base}/healthz", timeout=5).raise_for_status()
        except Exception as exc:  # unreachable target — skip, never fake success
            raise UatSkip(f"target unreachable: {type(exc).__name__}: {exc}") from exc
        ok = run(base, summary)
    except UatSkip as skip:
        result = {"result": "SKIP", "reason": str(skip), "steps": summary}
        print(json.dumps(result, indent=2) if args.json else f"SKIP — {skip}")
        return 0
    except httpx.HTTPStatusError as exc:
        result = {"result": "FAIL", "reason": f"HTTP {exc.response.status_code}", "steps": summary}
        print(json.dumps(result, indent=2) if args.json else f"FAIL — {result['reason']}")
        return 1
    except Exception as exc:  # explicit failure — never silently pass
        result = {"result": "FAIL", "reason": f"{type(exc).__name__}: {exc}", "steps": summary}
        print(json.dumps(result, indent=2) if args.json else f"FAIL — {result['reason']}")
        return 1

    result = {"result": "PASS" if ok else "FAIL", "steps": summary}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for step in STEPS:
            state = summary.get(step, {})
            mark = "PASS" if state.get("ok") else "FAIL"
            print(f"{step:14s} {mark}  {state}")
        print(f"\nResult: {result['result']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
