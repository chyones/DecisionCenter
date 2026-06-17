"""Tests for the Odoo Source Map batched deep-scan engine.

Covers the behaviours the feature promises:
  * heavy sources are split into small offset batches (never a full table read);
  * exact totals come from search_count;
  * strict per-batch / per-source timeouts;
  * partial results when a source is interrupted;
  * retry failed sources without re-scanning completed ones;
  * every query is project/analytic scoped (no broad unscoped Odoo query);
  * denylisted paths are never queried;
  * no PRJ-001 / PRJ-002 ids are hardcoded.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from apps.edr.admin import odoo_scan_session as e
from apps.edr.connectors import odoo_sources as src

# Arbitrary, non-validation project + ids — proves there is no PRJ-001/002 logic.
ARB_CODE = "ZED-777"
ARB_PROJECT_ID = "99001"
ARB_ANALYTIC_ID = "88002"
SAMPLE_IDS = ("14602", "14601", "21963", "21960")  # audit samples — must never leak


def _cfg(project_id: str | None = ARB_PROJECT_ID, analytic_id: str | None = ARB_ANALYTIC_ID) -> dict:
    return {
        "project_external_id": project_id or "",
        "analytic_account_id": analytic_id or "",
    }


class Recorder:
    def __init__(self) -> None:
        self.read: list[dict] = []
        self.count: list[dict] = []

    @property
    def read_models(self) -> list[str]:
        return [p["model"] for p in self.read]

    @property
    def count_models(self) -> list[str]:
        return [p["model"] for p in self.count]


def _new_workflow(totals: dict[str, int], rec: Recorder):
    """Simulate the enhanced n8n workflow: count supported + offset honoured."""

    async def count_fn(payload: dict) -> int | None:
        rec.count.append(payload)
        return totals.get(payload["model"], 0)

    async def read_fn(payload: dict) -> list:
        rec.read.append(payload)
        total = totals.get(payload["model"], 0)
        offset = int(payload["offset"])
        limit = int(payload["limit"])
        remaining = max(0, total - offset)
        return list(range(min(limit, remaining)))

    return count_fn, read_fn


def _legacy_workflow(page: dict[str, int], rec: Recorder):
    """Simulate the legacy workflow: no count, no offset (always first page)."""

    async def count_fn(payload: dict) -> int | None:
        rec.count.append(payload)
        return None  # count unsupported

    async def read_fn(payload: dict) -> list:
        rec.read.append(payload)
        return list(range(page.get(payload["model"], 0)))

    return count_fn, read_fn


def _po_source() -> src.OdooSource:
    s = e.source_by_key("purchase_orders")  # analytic-scoped
    assert s is not None
    return s


def _mr_source() -> src.OdooSource:
    s = e.source_by_key("material_requests")  # project-scoped
    assert s is not None
    return s


# ---------------------------------------------------------------------------
# Heavy source batching + exact totals
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_large_source_split_into_offset_batches() -> None:
    rec = Recorder()
    count_fn, read_fn = _new_workflow({"purchase.order": 350}, rec)
    cfg = e.ScanConfig(page_size=100, sample_target=300, batch_timeout_s=1.0, source_timeout_s=5.0)

    st = await e.scan_one_source(
        _po_source(),
        project_code=ARB_CODE,
        odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID],
        read_fn=read_fn,
        count_fn=count_fn,
        cfg=cfg,
    )

    assert st.status == e.COMPLETED
    assert st.total == 350           # exact total from search_count
    assert st.count == 350
    assert st.complete is True
    assert st.capped is False
    # one count call, then the sample paged in 100-row batches at 0/100/200
    assert len(rec.count) == 1
    assert [p["offset"] for p in rec.read] == [0, 100, 200]
    # never a full-table read: every batch limit is <= page_size
    assert all(int(p["limit"]) <= 100 for p in rec.read)
    assert st.pages_done == 3


@pytest.mark.anyio
async def test_very_large_source_uses_count_not_full_read() -> None:
    rec = Recorder()
    count_fn, read_fn = _new_workflow({"purchase.order": 10000}, rec)
    cfg = e.ScanConfig(page_size=100, sample_target=300, batch_timeout_s=1.0, source_timeout_s=5.0)

    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=count_fn, cfg=cfg,
    )

    assert st.status == e.COMPLETED
    assert st.count == 10000 and st.total == 10000 and st.complete is True
    # only a bounded sample (<= sample_target) is actually read — never 10k rows
    assert len(rec.read) == 3                       # 300 sampled / 100 per page
    assert 3 * cfg.page_size <= cfg.sample_target


@pytest.mark.anyio
async def test_empty_source_via_count_makes_no_read_calls() -> None:
    rec = Recorder()
    count_fn, read_fn = _new_workflow({"purchase.order": 0}, rec)
    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(),
    )
    assert st.status == e.EMPTY
    assert st.count == 0 and st.complete is True
    assert rec.read == []  # zero total → never reads rows


# ---------------------------------------------------------------------------
# Timeouts (per-batch / per-source)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_per_batch_timeout_on_count_marks_timeout() -> None:
    rec = Recorder()

    async def slow_count(payload: dict) -> int | None:
        rec.count.append(payload)
        await asyncio.sleep(0.5)
        return 10

    async def read_fn(payload: dict) -> list:
        rec.read.append(payload)
        return []

    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=slow_count,
        cfg=e.ScanConfig(batch_timeout_s=0.05),
    )
    assert st.status == e.TIMEOUT
    assert st.error and "timed out" in st.error
    assert rec.read == []  # never got to reading rows


@pytest.mark.anyio
async def test_slow_source_does_not_block_others() -> None:
    """One source's batch timeout is bounded; the session moves on to the rest."""
    sources = [_po_source(), _mr_source()]
    session = e.ScanSession(session_id="s", project_code=ARB_CODE)
    for s in sources:
        session.sources[s.key] = e.SourceScanState(key=s.key, status=e.PENDING)
    rec = Recorder()

    async def count_fn(payload: dict) -> int | None:
        rec.count.append(payload)
        if payload["model"] == "purchase.order":
            await asyncio.sleep(0.5)  # the slow source
            return 1
        return 2

    async def read_fn(payload: dict) -> list:
        rec.read.append(payload)
        return list(range(2))

    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID], sources=sources,
        read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(batch_timeout_s=0.05, page_size=100, sample_target=10),
    )
    # slow source timed out, but the other one still completed
    assert session.sources["purchase_orders"].status == e.TIMEOUT
    assert session.sources["material_requests"].status == e.COMPLETED


# ---------------------------------------------------------------------------
# Partial results
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_partial_when_sample_interrupted_but_total_known() -> None:
    rec = Recorder()
    calls = {"n": 0}

    async def count_fn(payload: dict) -> int | None:
        rec.count.append(payload)
        return 350

    async def read_fn(payload: dict) -> list:
        rec.read.append(payload)
        calls["n"] += 1
        if calls["n"] == 2:
            await asyncio.sleep(0.5)  # second batch times out
        return list(range(100))

    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(page_size=100, sample_target=300, batch_timeout_s=0.1, source_timeout_s=5.0),
    )
    assert st.status == e.PARTIAL
    assert st.complete is False
    assert st.count == 350          # exact total is still known
    assert st.pages_done == 1       # only the first batch completed


# ---------------------------------------------------------------------------
# Legacy workflow (no count) → capped single page
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_legacy_workflow_caps_full_page() -> None:
    rec = Recorder()
    count_fn, read_fn = _legacy_workflow({"purchase.order": 100}, rec)
    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(page_size=100),
    )
    assert st.status == e.CAPPED
    assert st.capped is True and st.complete is False and st.count == 100
    assert len(rec.read) == 1  # never paginates the legacy workflow (no offset support)


@pytest.mark.anyio
async def test_legacy_workflow_small_page_completes() -> None:
    rec = Recorder()
    count_fn, read_fn = _legacy_workflow({"purchase.order": 7}, rec)
    st = await e.scan_one_source(
        _po_source(), project_code=ARB_CODE, odoo_config=_cfg(),
        allowed_odoo_ids=[ARB_PROJECT_ID], read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(page_size=100),
    )
    assert st.status == e.COMPLETED
    assert st.count == 7 and st.complete is True and st.capped is False


# ---------------------------------------------------------------------------
# Retry failed sources (no full re-scan)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retry_reruns_only_failed_sources() -> None:
    sources = [_po_source(), _mr_source()]
    session = e.ScanSession(session_id="s", project_code=ARB_CODE)
    for s in sources:
        session.sources[s.key] = e.SourceScanState(key=s.key, status=e.PENDING)

    rec1 = Recorder()
    fail = {"purchase.order"}

    async def count_fn(payload: dict) -> int | None:
        rec1.count.append(payload)
        if payload["model"] in fail:
            raise RuntimeError("boom")
        return 3

    async def read_fn(payload: dict) -> list:
        rec1.read.append(payload)
        return list(range(3))

    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID], sources=sources,
        read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(page_size=100, sample_target=10),
    )
    assert session.sources["purchase_orders"].status == e.FAILED
    assert session.sources["material_requests"].status == e.COMPLETED

    # Retry: only the failed source is selected and re-scanned.
    keys = e.select_retry_keys(session, mode="failed")
    assert keys == ["purchase_orders"]

    fail.clear()
    rec2 = Recorder()

    async def count_ok(payload: dict) -> int | None:
        rec2.count.append(payload)
        return 9

    async def read_ok(payload: dict) -> list:
        rec2.read.append(payload)
        return list(range(min(int(payload["limit"]), 9)))

    for k in keys:
        prev = session.sources[k]
        session.sources[k] = e.SourceScanState(
            key=k, status=e.PENDING, pages_done=prev.pages_done, next_offset=prev.next_offset,
        )
    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID],
        sources=e.sources_for_keys(keys), read_fn=read_ok, count_fn=count_ok,
        cfg=e.ScanConfig(page_size=100, sample_target=10),
    )
    assert session.sources["purchase_orders"].status == e.COMPLETED
    assert session.sources["purchase_orders"].count == 9
    # The already-completed source was NOT touched on retry.
    assert "material.purchase.requisition" not in rec2.count_models
    assert "material.purchase.requisition" not in rec2.read_models


# ---------------------------------------------------------------------------
# Scope safety: no broad query, denylist, no hardcoded sample ids
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_broad_unscoped_query_and_no_denylisted_paths() -> None:
    rec = Recorder()
    totals = {s.model: 2 for s in src.ODOO_SOURCES}
    count_fn, read_fn = _new_workflow(totals, rec)

    session = e.init_full_session(ARB_CODE)
    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID],
        sources=e.sources_for_keys(e.all_source_keys()),
        read_fn=read_fn, count_fn=count_fn,
        cfg=e.ScanConfig(page_size=100, sample_target=2),
    )

    denylist = {(m, p) for (m, p) in src.DENYLISTED_PATHS}
    scoped_values = {int(ARB_PROJECT_ID), int(ARB_ANALYTIC_ID)}
    payloads = rec.read + rec.count
    assert payloads, "the scan must issue scoped queries"
    for p in payloads:
        domain = json.loads(p["domain"])
        assert isinstance(domain, list) and len(domain) >= 1  # never an empty (broad) domain
        leaf = domain[0]
        assert leaf[1] == "="  # equality filter only
        assert leaf[2] in scoped_values  # scoped to THIS project's runtime id
        assert (p["model"], leaf[0]) not in denylist  # denylisted path never queried


@pytest.mark.anyio
async def test_unmapped_sources_never_queried() -> None:
    rec = Recorder()
    totals = {s.model: 2 for s in src.ODOO_SOURCES}
    count_fn, read_fn = _new_workflow(totals, rec)

    session = e.init_full_session(ARB_CODE)
    await e.run_scan_session(
        session, odoo_config=_cfg(analytic_id=None),  # no analytic id
        allowed_odoo_ids=[ARB_PROJECT_ID],
        sources=e.sources_for_keys(e.all_source_keys()),
        read_fn=read_fn, count_fn=count_fn, cfg=e.ScanConfig(page_size=100, sample_target=2),
    )
    # analytic-scoped sources are unmapped and must never hit the network
    assert session.sources["purchase_orders"].status == e.UNMAPPED
    assert "purchase.order" not in rec.count_models
    assert "purchase.order" not in rec.read_models
    # project-scoped sources still run
    assert session.sources["material_requests"].status in (e.COMPLETED, e.EMPTY)
    assert "material.purchase.requisition" in rec.count_models


@pytest.mark.anyio
async def test_no_prj_sample_ids_anywhere() -> None:
    rec = Recorder()
    totals = {s.model: 1 for s in src.ODOO_SOURCES}
    count_fn, read_fn = _new_workflow(totals, rec)

    session = e.init_full_session(ARB_CODE)
    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID],
        sources=e.sources_for_keys(e.all_source_keys()),
        read_fn=read_fn, count_fn=count_fn, cfg=e.ScanConfig(page_size=100, sample_target=1),
    )
    blob = json.dumps([*(rec.read), *(rec.count), session.snapshot()])
    for sample in SAMPLE_IDS:
        assert sample not in blob


# ---------------------------------------------------------------------------
# Session lifecycle / snapshot round-trip (resume)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_overall_state_and_snapshot_roundtrip() -> None:
    sources = [_po_source(), _mr_source()]
    session = e.ScanSession(session_id="s", project_code=ARB_CODE)
    for s in sources:
        session.sources[s.key] = e.SourceScanState(key=s.key, status=e.PENDING)
    rec = Recorder()
    count_fn, read_fn = _new_workflow({"purchase.order": 5, "material.purchase.requisition": 0}, rec)

    await e.run_scan_session(
        session, odoo_config=_cfg(), allowed_odoo_ids=[ARB_PROJECT_ID], sources=sources,
        read_fn=read_fn, count_fn=count_fn, cfg=e.ScanConfig(page_size=100, sample_target=5),
    )
    assert session.state == e.S_COMPLETED  # completed + empty are both terminal-ok
    assert session.count_supported is True
    snap = session.snapshot()
    assert snap["progress"]["total"] == 2
    assert snap["progress"]["done"] == 2

    revived = e.ScanSession.from_snapshot(snap)
    assert revived.session_id == "s"
    assert revived.project_code == ARB_CODE
    assert revived.sources["purchase_orders"].count == 5
    assert revived.sources["material_requests"].status == e.EMPTY


def test_select_retry_modes() -> None:
    session = e.ScanSession(session_id="s", project_code=ARB_CODE)
    session.sources["a"] = e.SourceScanState(key="a", status=e.COMPLETED)
    session.sources["b"] = e.SourceScanState(key="b", status=e.FAILED)
    session.sources["c"] = e.SourceScanState(key="c", status=e.TIMEOUT)
    session.sources["d"] = e.SourceScanState(key="d", status=e.PARTIAL)
    session.sources["ee"] = e.SourceScanState(key="ee", status=e.EMPTY)

    assert set(e.select_retry_keys(session, mode="failed")) == {"b", "c"}
    assert set(e.select_retry_keys(session, mode="incomplete")) == {"b", "c", "d"}
