"""AI agent pre-flight check.

Run this script before editing any file. It verifies git state, agent state,
and documentation consistency. It mutates nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    return Path(__file__).resolve().parent.parent


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_script(root: Path, script: str) -> int:
    result = subprocess.run(
        [sys.executable, str(root / script)],
        check=False,
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def main() -> int:
    root = _repo_root()
    failures: list[str] = []

    # ------------------------------------------------------------------
    # Git checks
    # ------------------------------------------------------------------
    branch = _git(root, "branch", "--show-current")
    current_branch = branch.stdout.strip() if branch.returncode == 0 else "unknown"
    print(f"Branch: {current_branch}")
    if current_branch != "main":
        failures.append(f"Not on main branch: {current_branch}")

    status = _git(root, "status", "--short")
    dirty_files = status.stdout.strip()
    if dirty_files:
        print("Working tree dirty:")
        print(dirty_files)
        failures.append("Working tree is not clean")
    else:
        print("Working tree: clean")

    head = _git(root, "rev-parse", "HEAD")
    head_sha = head.stdout.strip() if head.returncode == 0 else "unknown"
    print(f"HEAD: {head_sha}")

    # ------------------------------------------------------------------
    # Agent state
    # ------------------------------------------------------------------
    state_path = root / "docs/ai/agent-state.json"
    if not state_path.exists():
        failures.append("Missing docs/ai/agent-state.json")
        return 1

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"agent-state.json is invalid JSON: {exc}")
        return 1

    status_val = state.get("status", "UNKNOWN")
    production_status = state.get("production_status", "UNKNOWN")
    current_commit = state.get("current_commit", "UNKNOWN")
    last_completed_phase = state.get("last_completed_phase", "UNKNOWN")
    next_allowed_phase = state.get("next_allowed_phase", "UNKNOWN")

    print(f"Status: {status_val}")
    print(f"Production status: {production_status}")
    print(f"Current commit (anchor): {current_commit}")
    print(f"Last completed phase: {last_completed_phase}")
    print(f"Next allowed phase: {next_allowed_phase}")

    if production_status != "NOT_LIVE":
        failures.append(
            f"production_status is '{production_status}', expected 'NOT_LIVE'. "
            "Stop immediately and ask the user for instructions."
        )

    if current_commit != "UNKNOWN":
        result = _git(root, "merge-base", "--is-ancestor", current_commit, "HEAD")
        if result.returncode != 0:
            failures.append(
                f"current_commit {current_commit} is not an ancestor of HEAD {head_sha}"
            )

    # ------------------------------------------------------------------
    # Doc and AI context checks
    # ------------------------------------------------------------------
    print("\n--- Running check_ai_context.py ---")
    if _run_script(root, "scripts/check_ai_context.py") != 0:
        failures.append("check_ai_context.py failed")

    print("\n--- Running check_doc_drift.py ---")
    if _run_script(root, "scripts/check_doc_drift.py") != 0:
        failures.append("check_doc_drift.py failed")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    if failures:
        print("\nPREFLIGHT FAILED:", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print("\nPreflight: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
