"""Phase 2D Slice 5 — Production Hardening.

Covers:
- Hardening checker script exists and is syntactically valid
- Hardening checker passes all checks in the current repo
- Production hardening checklist exists
- Secrets policy exists
- docker-compose.yml does not expose internal services publicly
- Caddyfile contains baseline security headers
- .env.example has no real secrets
- .gitignore excludes sensitive files
- No .env files are committed

These tests are read-only and safe to run in CI.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_hardening.py"
CHECKLIST_PATH = PROJECT_ROOT / "docs" / "operations" / "production_hardening_checklist.md"
SECRETS_POLICY_PATH = PROJECT_ROOT / "docs" / "policies" / "secrets_policy.md"
DOCKER_COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"
CADDYFILE_PATH = PROJECT_ROOT / "Caddyfile"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_hardening_script_exists() -> None:
    assert SCRIPT_PATH.exists(), f"Missing: {SCRIPT_PATH}"


def test_hardening_checklist_exists() -> None:
    assert CHECKLIST_PATH.exists(), f"Missing: {CHECKLIST_PATH}"


def test_secrets_policy_exists() -> None:
    assert SECRETS_POLICY_PATH.exists(), f"Missing: {SECRETS_POLICY_PATH}"


# ---------------------------------------------------------------------------
# Script validity
# ---------------------------------------------------------------------------


def test_hardening_script_is_valid_python() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    ast.parse(source)


def test_hardening_script_has_main_guard() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source or "__name__ == '__main__'" in source


def test_hardening_script_help_works() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "--json" in result.stdout


# ---------------------------------------------------------------------------
# Automated checks (run the script)
# ---------------------------------------------------------------------------


def test_hardening_checks_pass() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"Hardening checks failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "FAIL" not in result.stdout, result.stdout


def test_hardening_json_output_is_valid() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    import json

    data = json.loads(result.stdout)
    assert data["failed"] == 0, f"Failed checks: {data}"
    assert len(data["checks"]) > 0


# ---------------------------------------------------------------------------
# docker-compose.yml exposure review
# ---------------------------------------------------------------------------


def test_docker_compose_no_bare_public_ports() -> None:
    """Internal services must not bind to bare host ports (e.g. '8000:8000')."""
    content = DOCKER_COMPOSE_PATH.read_text(encoding="utf-8")
    suspicious = []
    current_service = ""
    in_services = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "services:":
            in_services = True
            continue
        if not in_services:
            continue
        # Top-level service names are indented 2 spaces
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_service = stripped.rstrip(":")
            continue
        if stripped.startswith("- \"") and ":" in stripped:
            mapping = stripped.strip("- \"")
            # Allow Caddy public ports and 127.0.0.1 bindings
            if current_service == "caddy":
                continue
            if mapping.startswith("127.0.0.1") or mapping.startswith("${"):
                continue
            if re.match(r"^\d+:\d+", mapping) or "0.0.0.0" in mapping:
                suspicious.append(f"{current_service}: {mapping}")
    assert not suspicious, f"Unexpected public port bindings: {suspicious}"


# ---------------------------------------------------------------------------
# Caddyfile security headers
# ---------------------------------------------------------------------------


def test_caddyfile_has_hsts() -> None:
    content = CADDYFILE_PATH.read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in content, "Missing HSTS header"


def test_caddyfile_has_x_frame_options() -> None:
    content = CADDYFILE_PATH.read_text(encoding="utf-8")
    assert "X-Frame-Options" in content, "Missing X-Frame-Options header"


def test_caddyfile_has_x_content_type_options() -> None:
    content = CADDYFILE_PATH.read_text(encoding="utf-8")
    assert "X-Content-Type-Options" in content, "Missing X-Content-Type-Options header"


# ---------------------------------------------------------------------------
# .env.example secrets check
# ---------------------------------------------------------------------------


def test_env_example_no_high_entropy_values() -> None:
    import re

    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    suspicious = []
    for line in content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        if val in ("", "change-me", "localhost", "local"):
            continue
        if re.fullmatch(r"[a-f0-9]{32,}", val, re.I):
            suspicious.append(key)
        if re.fullmatch(r"[A-Za-z0-9+/=]{40,}", val):
            suspicious.append(key)
    assert not suspicious, f"Suspicious values in .env.example: {suspicious}"


# ---------------------------------------------------------------------------
# .gitignore coverage
# ---------------------------------------------------------------------------


def test_gitignore_excludes_env_files() -> None:
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert ".env" in content, ".gitignore missing .env"


def test_gitignore_excludes_backup_files() -> None:
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "backups/" in content, ".gitignore missing backups/"


# ---------------------------------------------------------------------------
# No committed .env files
# ---------------------------------------------------------------------------


def test_no_env_files_tracked_by_git() -> None:
    git_available = subprocess.run(
        ["which", "git"], capture_output=True
    ).returncode == 0
    if not git_available:
        pytest.skip("git not available in container — verify on host")
    result = subprocess.run(
        ["git", "ls-files", ".env", ".env.*"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    tracked = [line for line in result.stdout.splitlines() if line and line != ".env.example"]
    assert not tracked, f"Tracked .env files found: {tracked}"


# ---------------------------------------------------------------------------
# Checklist content validation
# ---------------------------------------------------------------------------


def test_hardening_checklist_has_go_no_go_section() -> None:
    content = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "Go / No-Go" in content, "Missing Go/No-Go section"


def test_hardening_checklist_has_ssh_section() -> None:
    content = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "SSH" in content, "Missing SSH section"


def test_hardening_checklist_has_firewall_section() -> None:
    content = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "Firewall" in content, "Missing Firewall section"


def test_secrets_policy_has_rotation_procedure() -> None:
    content = SECRETS_POLICY_PATH.read_text(encoding="utf-8")
    assert "Rotation Procedure" in content, "Missing rotation procedure"


def test_secrets_policy_has_leak_response() -> None:
    content = SECRETS_POLICY_PATH.read_text(encoding="utf-8")
    assert "Leak Response" in content, "Missing leak response section"
