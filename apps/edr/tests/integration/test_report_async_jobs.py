from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apps.edr import app as appmod
from apps.edr.auth.validator import JWTClaims


class _FakeReportJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.audits: dict[str, dict] = {}

    async def init_schema(self) -> None:
        return None

    async def list_source_mappings(self) -> list[dict]:
        return []

    async def insert_report_job(self, **kwargs) -> None:
        self.jobs[kwargs["job_id"]] = {
            **kwargs,
            "status": "queued",
            "current_node": 0,
            "current_stage": "queued",
            "stage_status": "queued",
            "updated_at": datetime.now(timezone.utc),
            "quality_gate_status": None,
            "error_class": None,
            "error_message": None,
        }

    async def get_report_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    async def get_audit(self, request_id: str) -> dict | None:
        return self.audits.get(request_id)

    async def mark_report_job_running(
        self,
        *,
        job_id: str,
        current_stage: str,
        current_node: int,
    ) -> None:
        self.jobs[job_id].update(
            {
                "status": "running",
                "current_stage": current_stage,
                "current_node": current_node,
                "stage_status": "running",
                "updated_at": datetime.now(timezone.utc),
            }
        )

    async def mark_report_job_stage_complete(
        self,
        *,
        job_id: str,
        current_stage: str,
        current_node: int,
    ) -> None:
        self.jobs[job_id].update(
            {
                "current_stage": current_stage,
                "current_node": current_node,
                "stage_status": "completed",
                "updated_at": datetime.now(timezone.utc),
            }
        )

    async def complete_report_job(
        self,
        *,
        job_id: str,
        result_status: str,
        quality_gate_status: str | None,
        exported_formats: list[str],
    ) -> None:
        self.jobs[job_id].update(
            {
                "status": "completed",
                "current_node": self.jobs[job_id]["total_nodes"],
                "current_stage": "completed",
                "stage_status": "completed",
                "result_status": result_status,
                "quality_gate_status": quality_gate_status,
                "exported_formats": exported_formats,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    async def fail_report_job(
        self,
        *,
        job_id: str,
        status: str,
        current_stage: str | None,
        error_class: str,
        error_message: str,
    ) -> None:
        self.jobs[job_id].update(
            {
                "status": status,
                "current_stage": current_stage,
                "stage_status": status,
                "error_class": error_class,
                "error_message": error_message,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    async def recover_report_jobs_after_restart(self) -> dict[str, int]:
        completed = 0
        failed = 0
        for job in self.jobs.values():
            if job["status"] not in {"queued", "running"}:
                continue
            audit = self.audits.get(job["request_id"])
            if audit is not None:
                job.update(
                    {
                        "status": "completed",
                        "current_node": job["total_nodes"],
                        "current_stage": "completed",
                        "stage_status": "completed",
                        "result_status": "staging",
                        "quality_gate_status": audit.get("quality_gate_status"),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                completed += 1
                continue
            job.update(
                {
                    "status": "failed",
                    "current_stage": job.get("current_stage")
                    or "app_restart_or_worker_lost",
                    "stage_status": "failed",
                    "error_class": "WorkerLost",
                    "error_message": (
                        "Report generation failed: app_restart_or_worker_lost."
                    ),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            failed += 1
        return {"completed": completed, "failed": failed}


@pytest.mark.anyio
async def test_stage_report_creates_background_job_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeReportJobStore()
    scheduled: list[tuple[str, str]] = []

    monkeypatch.setattr(appmod, "get_postgres_store", lambda: store)
    monkeypatch.setattr(
        appmod,
        "_schedule_report_job",
        lambda job_id, state: scheduled.append((job_id, state.request_id)),
    )

    req = appmod.ReportRequest(
        user_id="u-1",
        query="give me one big problem",
        project_code=None,
        output_formats=["md"],
    )
    claims = JWTClaims(user_id="u-1", role="executive")

    resp = await appmod.stage_report(req, claims)

    assert resp["status"] == "queued"
    assert resp["job_id"] == resp["request_id"]
    assert resp["polling_url"] == f"/reports/{resp['request_id']}/status"
    assert scheduled == [(resp["job_id"], resp["request_id"])]
    assert store.jobs[resp["job_id"]]["status"] == "queued"


@pytest.mark.anyio
async def test_report_status_reads_queued_job_before_audit_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeReportJobStore()
    job_id = "job-1"
    await store.insert_report_job(
        job_id=job_id,
        request_id=job_id,
        user_id_hash=appmod.hash_user_id("u-1"),
        project_code="PRJ-001",
        query="q",
        total_nodes=18,
    )

    monkeypatch.setattr(appmod, "get_postgres_store", lambda: store)

    claims = JWTClaims(user_id="u-1", role="executive")
    resp = await appmod.get_report_status(job_id, claims)

    assert resp.request_id == job_id
    assert resp.state == "queued"
    assert resp.current_node == 0
    assert resp.is_terminal is False
    assert resp.current_stage == "queued"


@pytest.mark.anyio
async def test_report_job_runner_records_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeReportJobStore()
    job_id = "job-2"
    await store.insert_report_job(
        job_id=job_id,
        request_id=job_id,
        user_id_hash=appmod.hash_user_id("u-1"),
        project_code="PRJ-001",
        query="q",
        total_nodes=18,
    )

    async def fake_run_workflow(state, on_stage_event=None):
        if on_stage_event is not None:
            await on_stage_event("start", "node_00_begin", 0, state, None, None)
            await on_stage_event("end", "node_00_begin", 0, state, 12, None)
        state.outputs["quality_gate"] = "passed"
        state.outputs["markdown_report_status"] = "generated"
        state.outputs["exported_reports"] = {"md": "s3://example/report.md"}
        store.audits[state.request_id] = {
            "request_id": state.request_id,
            "quality_gate_status": "passed",
            "updated_at": datetime.now(timezone.utc),
        }
        return state

    monkeypatch.setattr(appmod, "get_postgres_store", lambda: store)
    monkeypatch.setattr(appmod, "run_workflow", fake_run_workflow)

    state = appmod.DecisionState(
        request_id=job_id,
        user_id="u-1",
        role="executive",
        project_code="PRJ-001",
        query="q",
        inputs={"query": "q"},
        output_formats=["md"],
    )

    await appmod._run_report_job(job_id, state)

    job = store.jobs[job_id]
    assert job["status"] == "completed"
    assert job["current_node"] == 18
    assert job["current_stage"] == "completed"
    assert job["result_status"] == "ready"
    assert job["quality_gate_status"] == "passed"
    assert job["exported_formats"] == ["md"]


@pytest.mark.anyio
async def test_startup_recovery_fails_orphaned_running_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeReportJobStore()
    job_id = "job-orphaned"
    await store.insert_report_job(
        job_id=job_id,
        request_id=job_id,
        user_id_hash=appmod.hash_user_id("u-1"),
        project_code="PRJ-001",
        query="q",
        total_nodes=18,
    )
    await store.mark_report_job_running(
        job_id=job_id,
        current_stage="node_12_draft_json",
        current_node=13,
    )

    monkeypatch.setattr(appmod, "get_postgres_store", lambda: store)

    await appmod._recover_stale_report_jobs_after_startup()

    job = store.jobs[job_id]
    assert job["status"] == "failed"
    assert job["current_stage"] == "node_12_draft_json"
    assert job["error_class"] == "WorkerLost"
    assert job["error_message"] == "Report generation failed: app_restart_or_worker_lost."


@pytest.mark.anyio
async def test_startup_recovery_completes_job_when_audit_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeReportJobStore()
    job_id = "job-audited"
    await store.insert_report_job(
        job_id=job_id,
        request_id=job_id,
        user_id_hash=appmod.hash_user_id("u-1"),
        project_code="PRJ-001",
        query="q",
        total_nodes=18,
    )
    await store.mark_report_job_running(
        job_id=job_id,
        current_stage="node_15_save_audit",
        current_node=16,
    )
    store.audits[job_id] = {
        "request_id": job_id,
        "quality_gate_status": "passed",
        "updated_at": datetime.now(timezone.utc),
    }

    monkeypatch.setattr(appmod, "get_postgres_store", lambda: store)

    await appmod._recover_stale_report_jobs_after_startup()

    job = store.jobs[job_id]
    assert job["status"] == "completed"
    assert job["current_node"] == 18
    assert job["current_stage"] == "completed"
    assert job["quality_gate_status"] == "passed"
