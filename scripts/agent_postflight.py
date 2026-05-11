"""AI agent post-flight check.

Run this script after editing and before committing. It prints changed files
and blocks forbidden patterns. It mutates nothing.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Patterns that must never be committed.
_BLOCKED_PATTERNS = [
    ".env",
    ".env.*",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "staging",
    "final",
    "logs",
]

# File extensions that indicate private keys or secrets.
_BLOCKED_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".der",
}


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


def _is_blocked(path: str) -> str | None:
    lower = path.lower()
    for pattern in _BLOCKED_PATTERNS:
        # Match exact filename or directory component
        parts = Path(path).parts
        if pattern in parts:
            return f"blocked pattern '{pattern}'"
        if lower.endswith(f"/{pattern}") or lower == pattern:
            return f"blocked pattern '{pattern}'"
    ext = Path(path).suffix.lower()
    if ext in _BLOCKED_EXTENSIONS:
        return f"blocked extension '{ext}'"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-no-evidence",
        action="store_true",
        help="Allow zero changed files (dry run or no-op task).",
    )
    args = parser.parse_args()

    root = _repo_root()
    failures: list[str] = []

    status = _git(root, "status", "--short")
    if status.returncode != 0:
        print(f"git status failed: {status.stderr}", file=sys.stderr)
        return 1

    changed = [line for line in status.stdout.strip().splitlines() if line.strip()]

    if not changed:
        if args.allow_no_evidence:
            print("Post-flight: no changes detected (allowed via --allow-no-evidence).")
            return 0
        failures.append("No changed files. If this is a dry run, use --allow-no-evidence.")
    else:
        print("Changed files:")
        for line in changed:
            print(f"  {line}")
            # Extract path from git status short format (first two chars are status)
            path = line[3:].strip()
            reason = _is_blocked(path)
            if reason:
                failures.append(f"{path}: {reason}")

    if failures:
        print("\nPOSTFLIGHT FAILED:", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print("\nPost-flight: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
