"""Documentation drift detector.

The repo's state docs make claims about which phase is complete and which is
"safe next". When code lands but the docs are not refreshed, those claims
silently rot. This script enforces a small set of cross-doc invariants that
every CI run must satisfy.

Invariants checked:
1. CONTROL_PLANE_LOCK.md, CURRENT_PROJECT_STATE.md, IMPLEMENTATION_PHASES.md,
   FEATURE_MATRIX.md, and README.md must all agree that Phase 2C is complete,
   production is NOT_LIVE, and Phase 2D is the approval-gated next phase.
2. The `.env.example` key count must match the assertion baked into
   .github/workflows/ci.yml and the count cited in CONTROL_PLANE_LOCK.md.
3. CONTROL_PLANE_LOCK.md, CURRENT_PROJECT_STATE.md, and IMPLEMENTATION_PHASES.md
   must reference the Phase 1D-fixup so its closure is visible.
4. The governance anchor (`docs/ai/agent-state.json.current_commit`) must be
   HEAD itself or no more than ``MAX_ANCHOR_DRIFT_COMMITS`` commits behind
   HEAD on the current branch. This catches the failure mode where feature
   commits land on `main` without a corresponding governance refresh, which
   silently rots every truth doc that quotes the anchor.

Failures are printed with a short hint and the script exits non-zero so CI
fails. Pass `--verbose` for the parsed counts.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CURRENT_COMPLETED_PHASE = "2C"
NEXT_ALLOWED_PHASE = "2D"
CURRENT_STATUS = "PHASE_2C_COMPLETE_NOT_LIVE"
PRODUCTION_STATUS = "NOT_LIVE"
FINAL_AUDIT_RECOMMENDATION = "NOT_GO_LIVE_READY_BUT_HEALTHY"
FINAL_AUDIT_RATING = "7/10"
PHASE_FIXUP_MARKER = "Phase 1D-fixup"
MAX_ANCHOR_DRIFT_COMMITS = 3
AUDIT_BLOCKERS = [
    "production frontend delivery path missing",
    "production Entra/MSAL frontend auth missing",
    "live integrations not proven",
    "backup/restore evidence missing",
    "production hardening evidence missing",
]
STALE_CURRENT_STATE_PATTERNS = [
    r"PHASE_2B_SLICE_\d+_COMPLETE_NOT_LIVE",
    r"Phase 2B is in progress",
    r"Phase 2B Slice 7[^.\n]*safe next",
    r"Safe next phase:\s*Phase 2B\b",
    r"\| 2B [^|]*\| Safe next phase",
    r"Latest full-phase report.*PHASE_2A_REPORT",
    r"Active Phase 2A plan",
    r"Phase 2B Admin Visual Control Plane implementation is not started",
    r"Phase 2A closeout evidence is recorded",
    r"Do not start Phase 2B\b",
    r"Phase 2C implementation\s*\|\s*Not started",
    r"Do not start Phase 2C without explicit user authorization",
    r"requires explicit user authorization before any implementation starts",
    r"PHASE_2C_IN_PROGRESS_NOT_LIVE",
    r"Phase 2C is in progress",
    r"Phase 2C hardening is in progress",
    r"Phase 2C is the current active phase",
    r"Phase 2C Slice 1[^.\n]*in progress",
    r"Closing in Phase 2C Slice 1",
    r"Phase 2C browser test harness[^|\n]*\|[^|\n]*partial",
    r"phase2b_complete_not_live",
]


def _resolve_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd()
    # Prefer the cwd if it looks like the repo root.
    if (cwd / "docs/admin/CONTROL_PLANE_LOCK.md").exists():
        return cwd
    # Fall back to script-relative resolution (works when invoked from anywhere).
    return Path(__file__).resolve().parent.parent


def _doc_paths(root: Path) -> dict[str, Path]:
    return {
        "control_plane": root / "docs/admin/CONTROL_PLANE_LOCK.md",
        "current_state": root / "docs/execution/CURRENT_PROJECT_STATE.md",
        "phases": root / "docs/execution/IMPLEMENTATION_PHASES.md",
        "feature_matrix": root / "docs/admin/FEATURE_MATRIX.md",
        "readme": root / "README.md",
        "shared_context": root / "docs/ai/SHARED_CONTEXT.md",
        "handoff": root / "docs/ai/AGENT_HANDOFF.md",
        "app_readme": root / "apps/edr/README.md",
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _env_key_count(root: Path) -> int:
    keys = [
        line.split("=", 1)[0]
        for line in _read(root / ".env.example").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return len(keys)


def _ci_assertion_count(root: Path) -> int:
    raw = _read(root / ".github/workflows/ci.yml")
    match = re.search(r"len\(env_keys\)\s*==\s*(\d+)", raw)
    if not match:
        raise SystemExit("ci.yml is missing the `len(env_keys) == N` assertion")
    return int(match.group(1))


def _control_plane_count(docs: dict[str, Path]) -> int:
    raw = _read(docs["control_plane"])
    match = re.search(r"\.env\.example.*?has\s+(\d+)\s+keys", raw, re.IGNORECASE)
    if not match:
        raise SystemExit("CONTROL_PLANE_LOCK.md is missing the env-key count claim")
    return int(match.group(1))


def _doc_marks_phase_2c_complete_and_phase_2d_gated(
    docs: dict[str, Path], name: str
) -> bool:
    raw = _read(docs[name])
    flat = re.sub(r"\s+", " ", raw)
    phase_complete = re.search(
        rf"({CURRENT_STATUS}|Phase\s+{CURRENT_COMPLETED_PHASE}\b"
        r"[^.\n]{0,80}\bcomplete|Phases\s+2A-2C\s+are\s+complete)",
        flat,
        flags=re.IGNORECASE,
    )
    production_not_live = PRODUCTION_STATUS in raw
    next_gated = re.search(
        rf"Phase\s+{NEXT_ALLOWED_PHASE}\b[^.\n]{{0,120}}(explicit user approval|approval-gated|blocked)",
        flat,
        flags=re.IGNORECASE,
    )
    return bool(phase_complete and production_not_live and next_gated)


def _doc_records_audit_verdict(docs: dict[str, Path], name: str) -> bool:
    raw = _read(docs[name])
    lower = re.sub(r"\s+", " ", raw).lower()
    return (
        FINAL_AUDIT_RECOMMENDATION in raw
        and FINAL_AUDIT_RATING in raw
        and all(blocker.lower() in lower for blocker in AUDIT_BLOCKERS)
    )


def _doc_marks_fixup_complete(docs: dict[str, Path], name: str) -> bool:
    return PHASE_FIXUP_MARKER in _read(docs[name])


def _stale_current_state_matches(docs: dict[str, Path], name: str) -> list[str]:
    raw = _read(docs[name])
    return [
        pattern
        for pattern in STALE_CURRENT_STATE_PATTERNS
        if re.search(pattern, raw, flags=re.IGNORECASE)
    ]


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


def _anchor_drift(root: Path, anchor_commit: str) -> int | None:
    """Return the number of commits HEAD is ahead of ``anchor_commit``.

    Returns ``None`` if the anchor is not an ancestor of HEAD (i.e. lives on a
    different branch) or if git is not available in this checkout.
    """
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return None
    head_sha = head.stdout.strip()
    if head_sha == anchor_commit:
        return 0

    ancestor = _git(root, "merge-base", "--is-ancestor", anchor_commit, "HEAD")
    if ancestor.returncode != 0:
        return None

    count = _git(root, "rev-list", "--count", f"{anchor_commit}..HEAD")
    if count.returncode != 0:
        return None
    try:
        return int(count.stdout.strip())
    except ValueError:
        return None


def _check_anchor_currency(root: Path) -> str | None:
    """Return a failure message if the governance anchor lags HEAD too far."""
    state_path = root / "docs/ai/agent-state.json"
    if not state_path.exists():
        return None  # check_ai_context.py owns the missing-file failure
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None  # check_ai_context.py owns the malformed-JSON failure
    if not isinstance(state, dict):
        return None
    anchor = state.get("current_commit")
    if not isinstance(anchor, str) or not anchor:
        return None  # check_ai_context.py owns the missing-field failure

    drift = _anchor_drift(root, anchor)
    if drift is None:
        return None  # not an ancestor / unable to compute — leave it to check_ai_context.py
    if drift > MAX_ANCHOR_DRIFT_COMMITS:
        return (
            f"docs/ai/agent-state.json current_commit ({anchor[:7]}) is "
            f"{drift} commits behind HEAD; max allowed is "
            f"{MAX_ANCHOR_DRIFT_COMMITS}. Refresh the governance anchor and "
            "the truth docs before merging more work."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)

    root = _resolve_root(args.repo_root)
    docs = _doc_paths(root)
    failures: list[str] = []

    env_count = _env_key_count(root)
    ci_count = _ci_assertion_count(root)
    cp_count = _control_plane_count(docs)

    if args.verbose:
        print(f"repo root: {root}")
        print(f".env.example keys: {env_count}")
        print(f"ci.yml assertion: {ci_count}")
        print(f"CONTROL_PLANE_LOCK.md claim: {cp_count}")

    if env_count != ci_count:
        failures.append(
            f".env.example has {env_count} keys but ci.yml asserts {ci_count}. "
            "Update the `assert len(env_keys) == N` line."
        )
    if env_count != cp_count:
        failures.append(
            f".env.example has {env_count} keys but CONTROL_PLANE_LOCK.md cites {cp_count}. "
            "Refresh the env baseline section."
        )

    for name in ("control_plane", "current_state", "phases", "feature_matrix", "readme"):
        if not _doc_marks_phase_2c_complete_and_phase_2d_gated(docs, name):
            failures.append(
                f"{docs[name].relative_to(root)} does not consistently mark "
                "Phase 2C complete, production NOT_LIVE, and Phase 2D approval-gated."
            )
        if not _doc_records_audit_verdict(docs, name):
            failures.append(
                f"{docs[name].relative_to(root)} does not record the latest audit "
                f"rating ({FINAL_AUDIT_RATING}), recommendation "
                f"({FINAL_AUDIT_RECOMMENDATION}), and main blockers."
            )

    for name in (
        "control_plane",
        "current_state",
        "feature_matrix",
        "readme",
        "shared_context",
        "handoff",
        "app_readme",
    ):
        stale_matches = _stale_current_state_matches(docs, name)
        if stale_matches:
            failures.append(
                f"{docs[name].relative_to(root)} contains stale current-state marker(s): "
                + ", ".join(stale_matches)
            )

    for name in ("control_plane", "current_state", "phases"):
        if not _doc_marks_fixup_complete(docs, name):
            failures.append(
                f"{docs[name].relative_to(root)} does not reference '{PHASE_FIXUP_MARKER}'."
            )

    anchor_failure = _check_anchor_currency(root)
    if anchor_failure is not None:
        failures.append(anchor_failure)

    if failures:
        for msg in failures:
            print(f"DRIFT: {msg}", file=sys.stderr)
        return 1

    print("Documentation drift check: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
