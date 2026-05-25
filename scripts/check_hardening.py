#!/usr/bin/env python3
"""Production hardening posture checker.

Runs a set of read-only, local-only checks against the repository to verify
that secrets stay out of git, internal services are not publicly exposed, and
baseline security headers are present.  This script does **not** connect to any
live service and is safe to run in CI.

Usage:
    python3 scripts/check_hardening.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str) -> None:
        self.name = name
        self.passed = passed
        self.detail = detail


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_env_example_has_no_real_secrets() -> CheckResult:
    """.env.example must use placeholder values, not real secrets."""
    root = _repo_root()
    env_example = root / ".env.example"
    if not env_example.exists():
        return CheckResult(".env.example exists", False, ".env.example missing")

    content = _read(env_example)
    # Reject high-entropy hex strings that look like real keys
    suspicious = []
    for line in content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        # Skip empty or obviously placeholder values
        if val in ("", "change-me", "localhost", "local"):
            continue
        # Flag values that look like real API keys (long hex/base64)
        if re.fullmatch(r"[a-f0-9]{32,}", val, re.I):
            suspicious.append(key)
        if re.fullmatch(r"[A-Za-z0-9+/=]{40,}", val):
            suspicious.append(key)

    if suspicious:
        return CheckResult(
            ".env.example placeholders",
            False,
            f"Suspicious high-entropy values: {suspicious}",
        )
    return CheckResult(
        ".env.example placeholders", True, "No real secrets detected"
    )


def check_gitignore_excludes_sensitive_files() -> CheckResult:
    """.gitignore must exclude .env, backups, and local data."""
    root = _repo_root()
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return CheckResult(".gitignore exists", False, ".gitignore missing")

    content = _read(gitignore)
    required = {
        ".env",
        ".env.*",
        "backups/",
    }
    missing = [p for p in required if p not in content]
    if missing:
        return CheckResult(
            ".gitignore coverage", False, f"Missing patterns: {missing}"
        )
    return CheckResult(".gitignore coverage", True, "All required patterns present")


def check_no_env_files_committed() -> CheckResult:
    """Ensure no real .env files are tracked by git (``.env.example`` is allowed)."""
    root = _repo_root()
    git_available = subprocess.run(
        ["which", "git"], capture_output=True
    ).returncode == 0
    if not git_available:
        return CheckResult(
            "No committed .env files",
            True,
            "git not available — skipping (verify manually on host)",
        )
    result = subprocess.run(
        ["git", "ls-files", ".env", ".env.*"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    tracked = [line for line in result.stdout.splitlines() if line and line != ".env.example"]
    if tracked:
        return CheckResult(
            "No committed .env files", False, f"Tracked: {tracked}"
        )
    return CheckResult(
        "No committed .env files", True, "No .env files in git index"
    )


def check_docker_compose_internal_services_not_public() -> CheckResult:
    """Internal services must not bind to 0.0.0.0 or public host ports."""
    root = _repo_root()
    compose = root / "docker-compose.yml"
    if not compose.exists():
        return CheckResult("docker-compose.yml exists", False, "File missing")

    content = _read(compose)
    # Find port mappings in the compose file
    public_bindings = []
    in_service = False
    current_service = ""
    for line in content.splitlines():
        stripped = line.strip()
        # Detect service names (top-level keys under services:)
        if stripped.endswith(":") and not stripped.startswith("-"):
            if in_service and line.startswith("  ") and not line.startswith("    "):
                current_service = stripped.rstrip(":")
                continue
        if stripped == "services:":
            in_service = True
            continue

        # Look for port lines
        if "ports:" in stripped:
            continue
        if stripped.startswith("- \"") and ":" in stripped:
            port_mapping = stripped.strip("- \"")
            # Check for 0.0.0.0 or bare host ports (no 127.0.0.1 prefix)
            if "0.0.0.0" in port_mapping:
                public_bindings.append(f"{current_service}: {port_mapping}")
            # Bare number like "8000:8000" is public
            elif re.match(r'^\d+:\d+', port_mapping):
                public_bindings.append(f"{current_service}: {port_mapping}")

    # Whitelist known public-facing services
    allowed_public = {"caddy"}
    violations = [
        b for b in public_bindings
        if not any(a in b for a in allowed_public)
    ]

    if violations:
        return CheckResult(
            "Internal service exposure",
            False,
            f"Public port bindings found: {violations}",
        )
    return CheckResult(
        "Internal service exposure", True, "Only Caddy is publicly bound"
    )


def check_caddyfile_security_headers() -> CheckResult:
    """Caddyfile must include baseline security headers."""
    root = _repo_root()
    caddyfile = root / "Caddyfile"
    if not caddyfile.exists():
        return CheckResult("Caddyfile exists", False, "Caddyfile missing")

    content = _read(caddyfile)
    required_headers = {
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
    }
    missing = [h for h in required_headers if h not in content]
    if missing:
        return CheckResult(
            "Caddyfile security headers", False, f"Missing: {missing}"
        )
    return CheckResult(
        "Caddyfile security headers", True, "Baseline headers present"
    )


def check_dockerfile_does_not_embed_secrets() -> CheckResult:
    """Dockerfile must not contain hardcoded secrets."""
    root = _repo_root()
    dockerfile = root / "Dockerfile"
    if not dockerfile.exists():
        return CheckResult("Dockerfile exists", False, "Dockerfile missing")

    content = _read(dockerfile)
    # Look for ENV lines with suspicious values
    suspicious = []
    for line in content.splitlines():
        if line.strip().startswith("ENV "):
            key_val = line.strip()[4:]
            if "=" in key_val:
                key, val = key_val.split("=", 1)
                if re.fullmatch(r"[a-f0-9]{32,}", val.strip(), re.I):
                    suspicious.append(key)
                if re.fullmatch(r"[A-Za-z0-9+/=]{40,}", val.strip()):
                    suspicious.append(key)

    if suspicious:
        return CheckResult(
            "Dockerfile secrets", False, f"Suspicious ENV values: {suspicious}"
        )
    return CheckResult("Dockerfile secrets", True, "No hardcoded secrets")


def check_ci_workflow_no_secrets() -> CheckResult:
    """CI workflow must not contain hardcoded secrets."""
    root = _repo_root()
    ci = root / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return CheckResult("CI workflow exists", False, "ci.yml missing")

    content = _read(ci)
    # Look for anything that looks like a real API key or token
    suspicious = []
    for line in content.splitlines():
        if re.search(r'[a-f0-9]{32,}', line, re.I) and "actions/" not in line:
            suspicious.append(line.strip()[:60])
        if re.search(r'Bearer\s+[a-zA-Z0-9]{20,}', line):
            suspicious.append(line.strip()[:60])

    if suspicious:
        return CheckResult(
            "CI workflow secrets", False, f"Suspicious lines: {suspicious[:3]}"
        )
    return CheckResult("CI workflow secrets", True, "No hardcoded secrets")


CHECKS = [
    check_env_example_has_no_real_secrets,
    check_gitignore_excludes_sensitive_files,
    check_no_env_files_committed,
    check_docker_compose_internal_services_not_public,
    check_caddyfile_security_headers,
    check_dockerfile_does_not_embed_secrets,
    check_ci_workflow_no_secrets,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Production hardening checker")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    results: list[CheckResult] = []
    for check_fn in CHECKS:
        try:
            results.append(check_fn())
        except Exception as exc:
            results.append(
                CheckResult(check_fn.__name__, False, f"Exception: {exc}")
            )

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    if args.json:
        import json

        output = {
            "passed": passed,
            "failed": failed,
            "checks": [
                {"name": r.name, "passed": r.passed, "detail": r.detail}
                for r in results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.name}: {r.detail}")
        print(f"\nTotal: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
