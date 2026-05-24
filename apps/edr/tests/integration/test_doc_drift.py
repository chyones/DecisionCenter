"""Verify the documentation drift detector flags real drift.

The drift detector lives in ``scripts/check_doc_drift.py`` and is wired into
CI. These tests pin the contract: clean docs return 0, mutated docs return 1.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "check_doc_drift.py"


def _run(cwd: Path, script: Path | None = None) -> subprocess.CompletedProcess:
    target = script if script is not None else SCRIPT
    return subprocess.run(
        [sys.executable, str(target)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_drift_detector_passes_on_clean_repo() -> None:
    result = _run(ROOT)
    assert result.returncode == 0, result.stderr


def test_drift_detector_fails_when_env_count_diverges(tmp_path: pytest.TempPathFactory) -> None:
    work = Path(str(tmp_path)) / "repo"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", "*.egg-info"))
    env = (work / ".env.example").read_text(encoding="utf-8")
    (work / ".env.example").write_text(env + "EXTRA_KEY=value\n", encoding="utf-8")
    result = _run(work)
    assert result.returncode == 1
    assert "DRIFT" in result.stderr


def test_drift_detector_fails_when_current_phase_renamed(tmp_path: pytest.TempPathFactory) -> None:
    work = Path(str(tmp_path)) / "repo"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", "*.egg-info"))
    script = (work / "scripts" / "check_doc_drift.py").read_text(encoding="utf-8")
    (work / "scripts" / "check_doc_drift.py").write_text(
        script.replace('CURRENT_COMPLETED_PHASE = "2C"', 'CURRENT_COMPLETED_PHASE = "99"'),
        encoding="utf-8",
    )
    result = _run(work, script=work / "scripts" / "check_doc_drift.py")
    assert result.returncode == 1
    assert "phase 2c complete" in result.stderr.lower()
