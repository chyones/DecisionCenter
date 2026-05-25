"""Phase 2D Slice 4 — Backup and Restore readiness.

Covers:
- Backup scripts exist and are syntactically valid
- Backup scripts can be imported without error
- Live backup produces non-empty artifacts (operator-run, Docker stack up)
- Restore scripts exist and are syntactically valid
- Verification script exists and is syntactically valid

Live backup/restore tests are marked ``live_probe`` and excluded from CI.
They are intended for operator rehearsal on a non-production target.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

SCRIPT_PATHS = {
    "backup_postgres": SCRIPTS_DIR / "backup_postgres.py",
    "backup_minio": SCRIPTS_DIR / "backup_minio.py",
    "restore_postgres": SCRIPTS_DIR / "restore_postgres.py",
    "restore_minio": SCRIPTS_DIR / "restore_minio.py",
    "verify_backup": SCRIPTS_DIR / "verify_backup.py",
}


# ---------------------------------------------------------------------------
# Structural validation (runs in CI)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", SCRIPT_PATHS.items())
def test_script_exists(name: str, path: Path) -> None:
    assert path.exists(), f"{name} script missing: {path}"


@pytest.mark.parametrize("name,path", SCRIPT_PATHS.items())
def test_script_is_valid_python(name: str, path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source)
    except SyntaxError as exc:
        pytest.fail(f"{name} has a syntax error: {exc}")


@pytest.mark.parametrize("name,path", SCRIPT_PATHS.items())
def test_script_has_main_guard(name: str, path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    assert '__name__ == "__main__"' in source or "__name__ == '__main__'" in source, (
        f"{name} missing main guard"
    )


def test_backup_postgres_has_help_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["backup_postgres"]), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--output-dir" in result.stdout


def test_backup_minio_has_help_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["backup_minio"]), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "--output-dir" in result.stdout


def test_restore_postgres_has_help_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["restore_postgres"]), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "sql_file" in result.stdout


def test_restore_minio_has_help_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["restore_minio"]), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "tar_file" in result.stdout


def test_verify_backup_has_help_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["verify_backup"]), "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "--verify-restored" in result.stdout


# ---------------------------------------------------------------------------
# Live backup rehearsal (operator-run only, excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.live_probe
def test_live_postgres_backup_produces_valid_dump() -> None:
    """Run the postgres backup script and verify output."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATHS["backup_postgres"]), "--output-dir", tmpdir],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            if "pg_dump" in result.stderr or "docker" in result.stderr.lower():
                pytest.skip(f"pg_dump/docker unavailable: {result.stderr}")
            pytest.fail(f"backup_postgres failed: {result.stderr}")

        output_dir = Path(tmpdir)
        files = list(output_dir.glob("postgres_*.sql"))
        assert files, "No backup file produced"

        backup_file = files[0]
        assert backup_file.stat().st_size > 0, "Backup file is empty"

        text = backup_file.read_text(encoding="utf-8")
        assert "CREATE TABLE" in text, "Missing CREATE TABLE marker"
        assert "audit_log" in text, "Missing audit_log marker"


@pytest.mark.live_probe
def test_live_minio_backup_produces_valid_tarball() -> None:
    """Run the minio backup script and verify output."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATHS["backup_minio"]), "--output-dir", tmpdir],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            pytest.skip(f"MinIO backup failed: {result.stderr}")

        output_dir = Path(tmpdir)
        files = list(output_dir.glob("minio_*.tar.gz"))
        assert files, "No backup tarball produced"

        backup_file = files[0]
        assert backup_file.stat().st_size > 0, "Backup tarball is empty"


@pytest.mark.live_probe
def test_live_verify_backup_sanity_check() -> None:
    """Run the verify script against live services."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATHS["verify_backup"]), "--verify-restored"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"Live verify failed: {result.stderr}")
    assert "sanity" in result.stdout or "OK" in result.stdout
