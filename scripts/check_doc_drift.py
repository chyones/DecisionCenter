"""Documentation drift detector.

The repo's state docs make claims about which phase is complete and which is
"safe next". When code lands but the docs are not refreshed, those claims
silently rot. This script enforces a small set of cross-doc invariants that
every CI run must satisfy.

Invariants checked:
1. CONTROL_PLANE_LOCK.md, CURRENT_PROJECT_STATE.md, IMPLEMENTATION_PHASES.md,
   FEATURE_MATRIX.md, and README.md must all reference the same "safe next
   phase".
2. The `.env.example` key count must match the assertion baked into
   .github/workflows/ci.yml and the count cited in CONTROL_PLANE_LOCK.md.
3. CONTROL_PLANE_LOCK.md, CURRENT_PROJECT_STATE.md, and IMPLEMENTATION_PHASES.md
   must reference the Phase 1D-fixup so its closure is visible.

Failures are printed with a short hint and the script exits non-zero so CI
fails. Pass `--verbose` for the parsed counts.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXPECTED_NEXT_PHASE = "1E"
PHASE_FIXUP_MARKER = "Phase 1D-fixup"


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


def _doc_mentions_next_phase(docs: dict[str, Path], name: str) -> bool:
    raw = _read(docs[name])
    candidates = [
        f"Phase {EXPECTED_NEXT_PHASE} may start",
        f"Phase {EXPECTED_NEXT_PHASE} is the safe next phase",
        f"safe next phase.*Phase {EXPECTED_NEXT_PHASE}",
        f"READY FOR PHASE {EXPECTED_NEXT_PHASE}",
        rf"\| {EXPECTED_NEXT_PHASE} — LLM Nodes \| Safe next phase",
    ]
    return any(re.search(pattern, raw) for pattern in candidates)


def _doc_marks_fixup_complete(docs: dict[str, Path], name: str) -> bool:
    return PHASE_FIXUP_MARKER in _read(docs[name])


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
        if not _doc_mentions_next_phase(docs, name):
            failures.append(
                f"{docs[name].relative_to(root)} does not name '{EXPECTED_NEXT_PHASE}' "
                f"as the safe next phase."
            )

    for name in ("control_plane", "current_state", "phases"):
        if not _doc_marks_fixup_complete(docs, name):
            failures.append(
                f"{docs[name].relative_to(root)} does not reference '{PHASE_FIXUP_MARKER}'."
            )

    if failures:
        for msg in failures:
            print(f"DRIFT: {msg}", file=sys.stderr)
        return 1

    print("Documentation drift check: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
