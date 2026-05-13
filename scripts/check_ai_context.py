"""Validate the shared AI operating context files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {
    "READY_FOR_PHASE_1E_NOT_LIVE",
    "READY_FOR_PHASE_1E_AND_LIVE",
    "NOT_READY_FOR_PHASE_1E",
    "PHASE_1E_IN_PROGRESS_NOT_LIVE",
    "PHASE_1E_COMPLETE_NOT_LIVE",
    "PHASE_1F_IN_PROGRESS_NOT_LIVE",
    "PHASE_1F_COMPLETE_NOT_LIVE",
    "PHASE_1G_IN_PROGRESS_NOT_LIVE",
    "PHASE_1G_COMPLETE_NOT_LIVE",
    "PHASE_1H_IN_PROGRESS_NOT_LIVE",
    "PHASE_1H_COMPLETE_NOT_LIVE",
    "PHASE_1I_IN_PROGRESS_NOT_LIVE",
    "PHASE_1I_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_1_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_2_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_3_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_4_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_5_COMPLETE_NOT_LIVE",
}

REQUIRED_FILES = [
    Path("docs/ai/SHARED_CONTEXT.md"),
    Path("docs/ai/AGENT_HANDOFF.md"),
    Path("docs/ai/agent-state.json"),
]


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
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _load_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(state, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return state


def _commit_is_in_history(root: Path, commit: str) -> bool:
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return False
    if head.stdout.strip() == commit:
        return True

    result = _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    return result.returncode == 0


def main() -> int:
    root = _repo_root()
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).exists():
            failures.append(f"missing required file: {relative_path}")

    state_path = root / "docs/ai/agent-state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = _load_state(state_path)
        except ValueError as exc:
            failures.append(str(exc))

    if state:
        commit = state.get("current_commit")
        if not isinstance(commit, str) or not commit:
            failures.append("agent-state.json current_commit must be a non-empty string")
        elif not _commit_is_in_history(root, commit):
            failures.append(
                "agent-state.json current_commit must match HEAD or be an ancestor of HEAD"
            )

        latest_report = state.get("latest_report")
        if not isinstance(latest_report, str) or not latest_report:
            failures.append("agent-state.json latest_report must be a non-empty string")
        elif not (root / latest_report).exists():
            failures.append(f"latest_report does not exist: {latest_report}")

        status = state.get("status")
        if status not in ALLOWED_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_STATUSES))
            failures.append(f"status must be one of: {allowed}")

        phase_1e_may_start = state.get("phase_1e_may_start")
        if status == "PHASE_1E_IN_PROGRESS_NOT_LIVE":
            if phase_1e_may_start is not True:
                failures.append(
                    "phase_1e_may_start must be true when status is PHASE_1E_IN_PROGRESS_NOT_LIVE"
                )
        elif status in ("PHASE_1E_COMPLETE_NOT_LIVE", "PHASE_1F_IN_PROGRESS_NOT_LIVE", "PHASE_1F_COMPLETE_NOT_LIVE"):
            # Phase 1E+ gates: explicit authorization required for next phase
            pass
        else:
            if phase_1e_may_start is not False:
                failures.append(
                    "phase_1e_may_start must remain false until explicit user authorization"
                )

    if failures:
        for failure in failures:
            print(f"AI_CONTEXT: {failure}", file=sys.stderr)
        return 1

    print("AI context check: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
