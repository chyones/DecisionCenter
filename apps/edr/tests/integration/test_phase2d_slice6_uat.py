"""Phase 2D Slice 6 — Real UAT Flow readiness.

CI-safe checks (run in CI):
- The UAT runbook exists and documents the full real flow.
- The UAT readiness checker exists, is valid, and passes.
- The operator UAT driver exists, is valid, and uses no mocking library
  (final UAT proof must hit the real backend).
- The driver skips safely when no target/credentials are configured.
- The evidence path is documented with redaction rules.

Live step (operator-run, skipped in CI via ``-m "not live_probe"``):
- The driver runs the real end-to-end flow against a running stack.

The live UAT itself is operator-driven — see docs/operations/uat_runbook.md.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

RUNBOOK_PATH = PROJECT_ROOT / "docs" / "operations" / "uat_runbook.md"
EVIDENCE_README = PROJECT_ROOT / "docs" / "evidence" / "uat" / "README.md"
CHECK_SCRIPT = PROJECT_ROOT / "scripts" / "uat_check.py"
FLOW_SCRIPT = PROJECT_ROOT / "scripts" / "uat_flow.py"

REQUIRED_FLOW_SECTIONS = [
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

FORBIDDEN_MOCK_MARKERS = [
    "unittest.mock",
    "MagicMock",
    "AsyncMock",
    "monkeypatch",
    "page.route",
    "responses.add",
]


# ---------------------------------------------------------------------------
# Runbook
# ---------------------------------------------------------------------------


def test_runbook_exists() -> None:
    assert RUNBOOK_PATH.exists(), f"Missing: {RUNBOOK_PATH}"


def test_runbook_documents_full_flow() -> None:
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_FLOW_SECTIONS if s not in content]
    assert not missing, f"Runbook missing flow sections: {missing}"


def test_runbook_keeps_production_not_live() -> None:
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "NOT_LIVE" in content, "Runbook must state production remains NOT_LIVE"


def test_evidence_readme_documents_redaction() -> None:
    assert EVIDENCE_README.exists(), f"Missing: {EVIDENCE_README}"
    content = EVIDENCE_README.read_text(encoding="utf-8")
    assert "Redaction" in content or "redact" in content.lower()


# ---------------------------------------------------------------------------
# Scripts validity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [CHECK_SCRIPT, FLOW_SCRIPT])
def test_script_exists(path: Path) -> None:
    assert path.exists(), f"Missing: {path}"


@pytest.mark.parametrize("path", [CHECK_SCRIPT, FLOW_SCRIPT])
def test_script_is_valid_python(path: Path) -> None:
    ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", [CHECK_SCRIPT, FLOW_SCRIPT])
def test_script_has_main_guard(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source


@pytest.mark.parametrize("path", [CHECK_SCRIPT, FLOW_SCRIPT])
def test_script_help_works(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(path), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "--json" in result.stdout


# ---------------------------------------------------------------------------
# No mocked backend in the driver
# ---------------------------------------------------------------------------


def test_uat_driver_uses_no_mocking() -> None:
    """Final UAT proof must hit the real backend — the driver must not mock."""
    source = FLOW_SCRIPT.read_text(encoding="utf-8")
    found = [m for m in FORBIDDEN_MOCK_MARKERS if m in source]
    assert not found, f"UAT driver contains mock markers: {found}"


# ---------------------------------------------------------------------------
# Readiness checker passes
# ---------------------------------------------------------------------------


def test_uat_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "FAIL" not in result.stdout, result.stdout


def test_uat_check_json_output() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    import json

    data = json.loads(result.stdout)
    assert data["failed"] == 0, data
    assert len(data["checks"]) > 0


# ---------------------------------------------------------------------------
# Safe handling of missing credentials
# ---------------------------------------------------------------------------


def test_uat_flow_skips_safely_without_target() -> None:
    """With no UAT_BASE_URL the driver must SKIP (exit 0), not fake success."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("UAT_")}
    result = subprocess.run(
        [sys.executable, str(FLOW_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "SKIP" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Live UAT — operator-run only (skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.live_probe
def test_uat_flow_live() -> None:
    """Run the real end-to-end UAT flow against a configured live target."""
    if not os.environ.get("UAT_BASE_URL"):
        pytest.skip("UAT_BASE_URL not configured — live UAT unavailable")
    result = subprocess.run(
        [sys.executable, str(FLOW_SCRIPT), "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    # SKIP (exit 0) is acceptable when credentials are absent; an explicit
    # FAIL (exit 1) means the live flow broke and must be investigated.
    assert result.returncode == 0, f"Live UAT flow failed:\n{result.stdout}\n{result.stderr}"
