"""ReportRequest.upload_ids — completes the Phase 2A upload wiring.

The Query Composer uploads files via POST /upload and attaches the returned
``upload_id`` values to POST /reports/staging. These tests pin the request
model contract: the field exists, defaults to empty, and flows into the
payload recorded as workflow inputs.
"""

from apps.edr.app import ReportRequest


def test_report_request_accepts_upload_ids() -> None:
    req = ReportRequest(user_id="u", query="q", upload_ids=["id-1", "id-2"])
    assert req.upload_ids == ["id-1", "id-2"]


def test_report_request_upload_ids_default_empty() -> None:
    req = ReportRequest(user_id="u", query="q")
    assert req.upload_ids == []


def test_upload_ids_present_in_workflow_inputs_dump() -> None:
    """stage_report records request.model_dump(exclude_none=True) as inputs."""
    req = ReportRequest(user_id="u", query="q", upload_ids=["id-1"])
    dumped = req.model_dump(exclude_none=True)
    assert dumped["upload_ids"] == ["id-1"]
