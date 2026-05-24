"""Validate the shared AI operating context files."""

from __future__ import annotations

import json
import re
import shutil
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
    "PHASE_2A_SLICE_6_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_7_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_8_COMPLETE_NOT_LIVE",
    "PHASE_2A_SLICE_9_COMPLETE_NOT_LIVE",
    "PHASE_2A_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_1_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_2_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_3_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_4_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_5_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_6_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_7_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_8_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_9_COMPLETE_NOT_LIVE",
    "PHASE_2B_SLICE_10_COMPLETE_NOT_LIVE",
    "PHASE_2B_COMPLETE_NOT_LIVE",
    "PHASE_2C_IN_PROGRESS_NOT_LIVE",
    "PHASE_2C_SLICE_1_COMPLETE_NOT_LIVE",
    "PHASE_2C_COMPLETE_NOT_LIVE",
}

REQUIRED_FILES = [
    Path("docs/ai/SHARED_CONTEXT.md"),
    Path("docs/ai/AGENT_HANDOFF.md"),
    Path("docs/ai/agent-state.json"),
]

STALE_TEXT_PATTERNS = [
    r"PHASE_2B_SLICE_\d+_COMPLETE_NOT_LIVE",
    r"Phase 2B is in progress",
    r"Phase 2B Slice 7[^.\n]*safe next",
    r"Safe next phase:\s*Phase 2B\b",
    r"Last completed phase:\s*Phase 2A",
    r"Latest full-phase report:\s*`docs/execution/PHASE_2A_REPORT.md`",
    r"Do not start Phase 2B\b",
    r"PHASE_2C_IN_PROGRESS_NOT_LIVE",
    r"Phase 2C is in progress",
    r"Phase 2C hardening is in progress",
    r"Phase 2C is the current active phase",
]

AUDIT_BLOCKERS = [
    "production frontend delivery path missing",
    "production Entra/MSAL frontend auth missing",
    "live integrations not proven",
    "backup/restore evidence missing",
    "production hardening evidence missing",
]


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    return Path(__file__).resolve().parent.parent


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("git") is None:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _commit_is_in_history(root: Path, commit: str) -> bool:
    # Docker images copy the source tree without .git and may not include the
    # git binary. Keep validating the machine-readable state there, but leave
    # ancestry enforcement to host/CI checkouts that have Git metadata.
    if not (root / ".git").exists():
        return True
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode == 127:
        return True
    if head.returncode != 0:
        return False
    if head.stdout.strip() == commit:
        return True

    result = _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    return result.returncode == 0


def _load_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(state, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return state


def main() -> int:
    root = _repo_root()
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).exists():
            failures.append(f"missing required file: {relative_path}")
        elif relative_path.suffix == ".md":
            raw = (root / relative_path).read_text(encoding="utf-8")
            for pattern in STALE_TEXT_PATTERNS:
                if re.search(pattern, raw, flags=re.IGNORECASE):
                    failures.append(
                        f"{relative_path} contains stale current-state marker: {pattern}"
                    )

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
        elif status == "PHASE_2B_COMPLETE_NOT_LIVE":
            if state.get("last_completed_phase") != "Phase 2B":
                failures.append(
                    "last_completed_phase must be Phase 2B when status is "
                    "PHASE_2B_COMPLETE_NOT_LIVE"
                )
            if state.get("active_phase") != "Phase 2C":
                failures.append(
                    "active_phase must be Phase 2C when status is "
                    "PHASE_2B_COMPLETE_NOT_LIVE"
                )
            next_allowed = state.get("next_allowed_phase")
            if not isinstance(next_allowed, str) or "Phase 2C" not in next_allowed:
                failures.append(
                    "next_allowed_phase must name Phase 2C when status is "
                    "PHASE_2B_COMPLETE_NOT_LIVE"
                )
            if latest_report != "docs/execution/PHASE_2B_REPORT.md":
                failures.append(
                    "latest_report must be docs/execution/PHASE_2B_REPORT.md when "
                    "status is PHASE_2B_COMPLETE_NOT_LIVE"
                )
            if state.get("requires_explicit_user_approval_for_phase_2c") is not True:
                failures.append("Phase 2C must require explicit user approval")
        elif status == "PHASE_2C_COMPLETE_NOT_LIVE":
            if state.get("last_completed_phase") != "Phase 2C":
                failures.append(
                    "last_completed_phase must be Phase 2C when status is "
                    "PHASE_2C_COMPLETE_NOT_LIVE"
                )
            active_phase = state.get("active_phase")
            if not isinstance(active_phase, str) or "Phase 2D" not in active_phase:
                failures.append(
                    "active_phase must show no active implementation and the "
                    "Phase 2D approval gate when Phase 2C is complete"
                )
            next_allowed = state.get("next_allowed_phase")
            if (
                not isinstance(next_allowed, str)
                or "Phase 2D" not in next_allowed
                or "explicit user approval" not in next_allowed
            ):
                failures.append(
                    "next_allowed_phase must name Phase 2D and require explicit "
                    "user approval when Phase 2C is complete"
                )
            if latest_report != "docs/execution/PHASE_2C_REPORT.md":
                failures.append(
                    "latest_report must be docs/execution/PHASE_2C_REPORT.md when "
                    "Phase 2C is complete"
                )
            if state.get("requires_explicit_user_approval_for_phase_2c") is not False:
                failures.append(
                    "requires_explicit_user_approval_for_phase_2c must be false after "
                    "explicit Phase 2C authorization"
                )
            if state.get("requires_explicit_user_approval_for_phase_2d") is not True:
                failures.append("Phase 2D must require explicit user approval")

            audit = state.get("latest_read_only_audit")
            if not isinstance(audit, dict):
                failures.append("latest_read_only_audit must record the latest audit result")
            else:
                if audit.get("overall_rating") != "7/10":
                    failures.append("latest_read_only_audit overall_rating must be 7/10")
                if audit.get("final_recommendation") != "NOT_GO_LIVE_READY_BUT_HEALTHY":
                    failures.append(
                        "latest_read_only_audit final_recommendation must be "
                        "NOT_GO_LIVE_READY_BUT_HEALTHY"
                    )
                if audit.get("go_live_ready") is not False:
                    failures.append("latest_read_only_audit go_live_ready must be false")
                blockers = audit.get("main_blockers")
                if not isinstance(blockers, list) or not all(
                    blocker in blockers for blocker in AUDIT_BLOCKERS
                ):
                    failures.append(
                        "latest_read_only_audit main_blockers must include the five "
                        "go-live blockers from the latest audit"
                    )
        elif isinstance(status, str) and status.startswith("PHASE_2C_"):
            if state.get("last_completed_phase") != "Phase 2B":
                failures.append(
                    "last_completed_phase must remain Phase 2B while Phase 2C is active"
                )
            if state.get("active_phase") != "Phase 2C":
                failures.append(
                    "active_phase must be Phase 2C for active Phase 2C statuses"
                )
            next_allowed = state.get("next_allowed_phase")
            if not isinstance(next_allowed, str) or "Phase 2C" not in next_allowed:
                failures.append(
                    "next_allowed_phase must name Phase 2C for active Phase 2C statuses"
                )
            if latest_report != "docs/execution/PHASE_2C_PLAN.md":
                failures.append(
                    "latest_report must be docs/execution/PHASE_2C_PLAN.md while "
                    "Phase 2C is active"
                )
            if state.get("requires_explicit_user_approval_for_phase_2c") is not False:
                failures.append(
                    "requires_explicit_user_approval_for_phase_2c must be false after "
                    "explicit Phase 2C authorization"
                )

        phase_1e_may_start = state.get("phase_1e_may_start")
        if status == "PHASE_1E_IN_PROGRESS_NOT_LIVE":
            if phase_1e_may_start is not True:
                failures.append(
                    "phase_1e_may_start must be true when status is PHASE_1E_IN_PROGRESS_NOT_LIVE"
                )
        elif status in (
            "PHASE_1E_COMPLETE_NOT_LIVE",
            "PHASE_1F_IN_PROGRESS_NOT_LIVE",
            "PHASE_1F_COMPLETE_NOT_LIVE",
        ):
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
