#!/usr/bin/env python3
"""Phase 2D Slice 6 — Real UAT readiness checker.

Static, local-only checks that the real-UAT artifacts are present and coherent.
This script does **not** connect to any live service and is safe to run in CI.
It verifies that the UAT runbook documents the full flow, that the operator UAT
driver exists and contains no mocking, and that the evidence path is documented.

The actual live UAT run is operator-driven — see ``scripts/uat_flow.py`` and
``docs/operations/uat_runbook.md``.

Usage:
    python3 scripts/uat_check.py
    python3 scripts/uat_check.py --json

Exit codes:
    0 — all readiness checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Flow stages that the runbook must document for the real, non-mocked UAT.
REQUIRED_RUNBOOK_SECTIONS = [
    "Real Entra Login",
    "Report Submission",
    "Evidence Retrieval",
    "Quality Gate",
    "Approval",
    "Publish",
    "Download",
    "No Mocked Backend",
    "Missing Credentials",
    "Evidence Location",
]

# Tokens that must never appear in the committed UAT driver — they would mean a
# mocked backend was used, which is forbidden as final UAT proof.
FORBIDDEN_MOCK_MARKERS = [
    "unittest.mock",
    "MagicMock",
    "AsyncMock",
    "monkeypatch",
    "page.route",
    "responses.add",
]


class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str) -> None:
        self.name = name
        self.passed = passed
        self.detail = detail


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_runbook_exists() -> CheckResult:
    path = _repo_root() / "docs" / "operations" / "uat_runbook.md"
    if not path.exists():
        return CheckResult("UAT runbook exists", False, f"missing {path}")
    return CheckResult("UAT runbook exists", True, "docs/operations/uat_runbook.md")


def check_runbook_covers_full_flow() -> CheckResult:
    path = _repo_root() / "docs" / "operations" / "uat_runbook.md"
    if not path.exists():
        return CheckResult("UAT runbook covers full flow", False, "runbook missing")
    content = _read(path)
    missing = [s for s in REQUIRED_RUNBOOK_SECTIONS if s not in content]
    if missing:
        return CheckResult("UAT runbook covers full flow", False, f"missing sections: {missing}")
    return CheckResult(
        "UAT runbook covers full flow",
        True,
        f"{len(REQUIRED_RUNBOOK_SECTIONS)} stages documented",
    )


def check_runbook_keeps_not_live() -> CheckResult:
    path = _repo_root() / "docs" / "operations" / "uat_runbook.md"
    if not path.exists():
        return CheckResult("UAT runbook keeps NOT_LIVE", False, "runbook missing")
    content = _read(path)
    if "NOT_LIVE" not in content:
        return CheckResult("UAT runbook keeps NOT_LIVE", False, "no NOT_LIVE statement")
    return CheckResult("UAT runbook keeps NOT_LIVE", True, "production stays NOT_LIVE")


def check_uat_driver_exists() -> CheckResult:
    path = _repo_root() / "scripts" / "uat_flow.py"
    if not path.exists():
        return CheckResult("UAT driver exists", False, f"missing {path}")
    return CheckResult("UAT driver exists", True, "scripts/uat_flow.py")


def check_uat_driver_has_no_mocks() -> CheckResult:
    """The operator UAT driver must exercise the real backend — no mocking."""
    path = _repo_root() / "scripts" / "uat_flow.py"
    if not path.exists():
        return CheckResult("UAT driver has no mocks", False, "driver missing")
    content = _read(path)
    found = [m for m in FORBIDDEN_MOCK_MARKERS if m in content]
    if found:
        return CheckResult("UAT driver has no mocks", False, f"mock markers present: {found}")
    return CheckResult("UAT driver has no mocks", True, "no mocking library used")


def check_evidence_path_documented() -> CheckResult:
    path = _repo_root() / "docs" / "evidence" / "uat" / "README.md"
    if not path.exists():
        return CheckResult("Evidence path documented", False, f"missing {path}")
    content = _read(path)
    if "Redaction" not in content and "redact" not in content.lower():
        return CheckResult("Evidence path documented", False, "no redaction rules")
    return CheckResult("Evidence path documented", True, "docs/evidence/uat/README.md")


CHECKS = [
    check_runbook_exists,
    check_runbook_covers_full_flow,
    check_runbook_keeps_not_live,
    check_uat_driver_exists,
    check_uat_driver_has_no_mocks,
    check_evidence_path_documented,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2D Slice 6 UAT readiness checker")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results: list[CheckResult] = []
    for check_fn in CHECKS:
        try:
            results.append(check_fn())
        except Exception as exc:  # pragma: no cover - defensive
            results.append(CheckResult(check_fn.__name__, False, f"Exception: {exc}"))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "passed": passed,
                    "failed": failed,
                    "checks": [
                        {"name": r.name, "passed": r.passed, "detail": r.detail}
                        for r in results
                    ],
                },
                indent=2,
            )
        )
    else:
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.name}: {r.detail}")
        print(f"\nTotal: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
