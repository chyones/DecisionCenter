"""Odoo Source Map — automatic batched deep-scan engine.

Why this exists
---------------
The old scan ran every Odoo source in a single synchronous request. With 20+
sources, each hitting the n8n → Odoo webhook, that one HTTP request could run
well past the 120 s reverse-proxy timeout and fail wholesale. This engine makes
the scan **safe and complete** by:

* running as a background **scan session** so the POST endpoint returns instantly
  (no request ever holds the proxy open while Odoo is queried);
* scanning **source by source**, each fully isolated — one slow/failing source
  never blocks or aborts the others;
* getting **totals via Odoo ``search_count``** (one cheap call) when the deployed
  workflow supports it, and only paging **small ``search_read`` batches** for a
  bounded sample — never fetching a full large table in one call;
* enforcing **strict per-batch and per-source timeouts**;
* recording a rich per-source result (status / count / total / capped / complete
  / error / duration / last-scanned / pages) so the UI can show live progress and
  partial results, and so a failed/partial source can be **retried or resumed**
  without re-scanning the whole project.

It is GENERIC and read-only. It carries no project ids as logic: project scope
comes only from the selected project's saved mapping (Odoo project id + analytic
account id), resolved by :func:`apps.edr.connectors.odoo.build_source_query`,
which is denylist-safe. PRJ-001 / PRJ-002 are audit samples, not code paths.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from apps.edr.connectors.odoo import build_source_query, count_odoo, read_odoo
from apps.edr.connectors.odoo_sources import ODOO_SOURCES, OdooSource, source_by_key

# ---------------------------------------------------------------------------
# Per-source status vocabulary — also the exact set of states the UI renders.
# ---------------------------------------------------------------------------
PENDING = "pending"          # queued, not started
RUNNING = "running"          # currently scanning
COMPLETED = "completed"      # finished; count known and sample retrieved
PARTIAL = "partial"          # count known but sample retrieval was interrupted
CAPPED = "capped"            # legacy workflow: hit the page cap, exact total unknown
EMPTY = "empty"              # zero rows for this project scope
FAILED = "failed"            # error from the read/count call
TIMEOUT = "timeout"          # per-batch / per-source timeout
UNMAPPED = "unmapped"        # mapping lacks the id this source needs (never queried)
NOT_SCANNED = "not_scanned"  # no scan has touched this source yet

#: Statuses considered a successful terminal result (no retry needed).
TERMINAL_OK = frozenset({COMPLETED, EMPTY})
#: Statuses eligible for "retry failed sources".
RETRYABLE = frozenset({FAILED, TIMEOUT})
#: Statuses eligible for "resume / retry incomplete".
INCOMPLETE = frozenset({FAILED, TIMEOUT, PARTIAL, CAPPED, PENDING, RUNNING})

#: Overall session states.
S_PENDING = "pending"
S_RUNNING = "running"
S_COMPLETED = "completed"   # every source terminal-ok / unmapped
S_PARTIAL = "partial"       # finished, but some sources partial/capped/failed
S_FAILED = "failed"         # finished, and nothing succeeded

ReadFn = Callable[[dict[str, Any]], Awaitable[list[Any]]]
CountFn = Callable[[dict[str, Any]], Awaitable[int | None]]
ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Config — small, injectable so tests can use tiny timeouts/pages.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanConfig:
    page_size: int = 100            # rows per search_read batch (webhook caps at 100)
    sample_target: int = 300        # max sample rows to actually read per source
    max_pages: int = 50             # hard per-source page budget
    batch_timeout_s: float = 20.0   # strict per webhook call
    source_timeout_s: float = 45.0  # soft cap for a source's pagination loop

    @classmethod
    def from_settings(cls, settings: Any) -> "ScanConfig":
        return cls(
            page_size=getattr(settings, "odoo_scan_page_size", 100),
            sample_target=getattr(settings, "odoo_scan_sample_target", 300),
            max_pages=getattr(settings, "odoo_scan_max_pages_per_source", 50),
            batch_timeout_s=float(getattr(settings, "odoo_scan_batch_timeout_s", 20.0)),
            source_timeout_s=float(getattr(settings, "odoo_scan_source_timeout_s", 45.0)),
        )


# ---------------------------------------------------------------------------
# State models
# ---------------------------------------------------------------------------


@dataclass
class SourceScanState:
    key: str
    status: str = PENDING
    count: int | None = None          # authoritative record count (total if known)
    total: int | None = None          # exact total from search_count, when available
    capped: bool = False              # legacy single-page cap (exact total unknown)
    complete: bool = False            # True when the result is final + exhaustive
    error: str | None = None
    duration_ms: int | None = None
    last_scanned_at: str | None = None
    pages_done: int = 0               # search_read batches issued (cumulative)
    next_offset: int = 0              # offset to resume sampling from

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SourceScanState":
        fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in fields})


@dataclass
class ScanSession:
    session_id: str
    project_code: str
    state: str = S_PENDING
    sources: dict[str, SourceScanState] = field(default_factory=dict)
    started_at: str = ""
    updated_at: str = ""
    finished_at: str | None = None
    summary: str = ""
    count_supported: bool | None = None  # discovered on first count call

    # -- progress / snapshot ------------------------------------------------
    def progress(self) -> dict[str, int]:
        buckets = {
            PENDING: 0, RUNNING: 0, COMPLETED: 0, PARTIAL: 0, CAPPED: 0,
            EMPTY: 0, FAILED: 0, TIMEOUT: 0, UNMAPPED: 0,
        }
        for st in self.sources.values():
            buckets[st.status] = buckets.get(st.status, 0) + 1
        done = sum(
            1 for st in self.sources.values()
            if st.status not in (PENDING, RUNNING)
        )
        buckets["total"] = len(self.sources)
        buckets["done"] = done
        return buckets

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_code": self.project_code,
            "state": self.state,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
            "count_supported": self.count_supported,
            "scanned_at": self.updated_at or self.finished_at,
            "progress": self.progress(),
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
        }

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> "ScanSession":
        sess = cls(
            session_id=snap.get("session_id", ""),
            project_code=snap.get("project_code", ""),
            state=snap.get("state", S_PENDING),
            started_at=snap.get("started_at", ""),
            updated_at=snap.get("updated_at", ""),
            finished_at=snap.get("finished_at"),
            summary=snap.get("summary", ""),
            count_supported=snap.get("count_supported"),
        )
        for key, sd in (snap.get("sources") or {}).items():
            sess.sources[key] = SourceScanState.from_dict(sd)
        return sess


# ---------------------------------------------------------------------------
# Scan one source — count first, then bounded paged sample. Fully isolated.
# ---------------------------------------------------------------------------


def _read_payload(
    project_code: str,
    query: tuple[str, str, str, int],
    allowed_odoo_ids: list[str],
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    model, domain, fields, _ = query
    return {
        "project_code": project_code,
        "model": model,
        "domain": domain,        # always the project/analytic-scoped leaf — never broad
        "fields": fields,
        "limit": limit,
        "offset": offset,
        "allowed_odoo_ids": allowed_odoo_ids,
    }


def _count_payload(
    project_code: str,
    query: tuple[str, str, str, int],
    allowed_odoo_ids: list[str],
) -> dict[str, Any]:
    model, domain, _, _ = query
    return {
        "project_code": project_code,
        "model": model,
        "domain": domain,        # same scoped domain; count never widens the filter
        "fields": "[\"id\"]",
        "limit": 1,
        "offset": 0,
        "allowed_odoo_ids": allowed_odoo_ids,
    }


async def scan_one_source(
    source: OdooSource,
    *,
    project_code: str,
    odoo_config: dict[str, Any],
    allowed_odoo_ids: list[str],
    read_fn: ReadFn,
    count_fn: CountFn,
    cfg: ScanConfig,
    prior: SourceScanState | None = None,
) -> SourceScanState:
    """Scan a single Odoo source in safe batches; never raises.

    Strategy:
      1. ``search_count`` for the exact total (one cheap call).
      2. Page a bounded sample with ``search_read`` (``page_size`` per call,
         ``offset`` stepped) up to ``sample_target`` rows — proving reachability
         without ever pulling a whole large table.
      3. Legacy fallback (workflow has no count): one safe first page; mark
         ``capped`` if it fills the page (exact total unknown).
    """
    st = SourceScanState(key=source.key)
    st.status = RUNNING
    t0 = time.monotonic()

    query = build_source_query(source, odoo_config)  # denylist-checked; None if unmapped
    if query is None:
        st.status = UNMAPPED
        st.complete = False
        st.duration_ms = 0
        st.last_scanned_at = _now_iso()
        return st

    # --- 1) totals via search_count -------------------------------------
    total: int | None
    try:
        total = await asyncio.wait_for(
            count_fn(_count_payload(project_code, query, allowed_odoo_ids)),
            timeout=cfg.batch_timeout_s,
        )
    except asyncio.TimeoutError:
        st.status = TIMEOUT
        st.error = f"search_count timed out after {cfg.batch_timeout_s:g}s"
        st.duration_ms = int((time.monotonic() - t0) * 1000)
        st.last_scanned_at = _now_iso()
        return st
    except Exception as exc:  # noqa: BLE001 — isolate this source
        st.status = FAILED
        st.error = f"search_count: {type(exc).__name__}: {exc}"
        st.duration_ms = int((time.monotonic() - t0) * 1000)
        st.last_scanned_at = _now_iso()
        return st

    count_supported = total is not None
    st.total = total

    if total == 0:
        st.count = 0
        st.complete = True
        st.status = EMPTY
        st.duration_ms = int((time.monotonic() - t0) * 1000)
        st.last_scanned_at = _now_iso()
        return st

    # --- legacy fallback: no count → a single safe page, no offset paging --
    if not count_supported:
        try:
            batch = await asyncio.wait_for(
                read_fn(_read_payload(
                    project_code, query, allowed_odoo_ids,
                    limit=cfg.page_size, offset=0,
                )),
                timeout=cfg.batch_timeout_s,
            )
        except asyncio.TimeoutError:
            st.status = TIMEOUT
            st.error = f"search_read timed out after {cfg.batch_timeout_s:g}s"
            st.duration_ms = int((time.monotonic() - t0) * 1000)
            st.last_scanned_at = _now_iso()
            return st
        except Exception as exc:  # noqa: BLE001
            st.status = FAILED
            st.error = f"search_read: {type(exc).__name__}: {exc}"
            st.duration_ms = int((time.monotonic() - t0) * 1000)
            st.last_scanned_at = _now_iso()
            return st
        n = len(batch)
        st.pages_done = 1
        st.next_offset = cfg.page_size
        if n == 0:
            st.count, st.complete, st.status = 0, True, EMPTY
        elif n >= cfg.page_size:
            # Hit the page ceiling and we cannot trust offset paging on the
            # legacy workflow → report a floor count, flagged capped.
            st.count, st.complete, st.capped, st.status = n, False, True, CAPPED
        else:
            st.count, st.complete, st.status = n, True, COMPLETED
        st.duration_ms = int((time.monotonic() - t0) * 1000)
        st.last_scanned_at = _now_iso()
        return st

    # --- 2) bounded paged sample (count is exact + authoritative) ---------
    target = min(total, cfg.sample_target)
    seen = 0
    offset = prior.next_offset if (prior and prior.next_offset) else 0
    pages = 0
    interrupted = False
    deadline = t0 + cfg.source_timeout_s

    while seen < target and pages < cfg.max_pages:
        if time.monotonic() >= deadline:
            interrupted = True
            break
        try:
            batch = await asyncio.wait_for(
                read_fn(_read_payload(
                    project_code, query, allowed_odoo_ids,
                    limit=cfg.page_size, offset=offset,
                )),
                timeout=cfg.batch_timeout_s,
            )
        except asyncio.TimeoutError:
            if pages == 0:
                st.status = TIMEOUT
                st.error = f"search_read timed out after {cfg.batch_timeout_s:g}s"
                st.total = total
                st.count = total
                st.duration_ms = int((time.monotonic() - t0) * 1000)
                st.last_scanned_at = _now_iso()
                return st
            interrupted = True
            break
        except Exception as exc:  # noqa: BLE001
            if pages == 0:
                st.status = FAILED
                st.error = f"search_read: {type(exc).__name__}: {exc}"
                st.total = total
                st.count = total
                st.duration_ms = int((time.monotonic() - t0) * 1000)
                st.last_scanned_at = _now_iso()
                return st
            interrupted = True
            break

        n = len(batch)
        seen += n
        pages += 1
        offset += cfg.page_size
        if n < cfg.page_size:
            break  # source exhausted before the sample target

    st.total = total
    st.count = total                 # totals are authoritative regardless of sample size
    st.pages_done = (prior.pages_done if prior else 0) + pages
    st.next_offset = offset
    st.complete = not interrupted
    st.status = PARTIAL if interrupted else COMPLETED
    st.duration_ms = int((time.monotonic() - t0) * 1000)
    st.last_scanned_at = _now_iso()
    return st


# ---------------------------------------------------------------------------
# Run / resume a whole session
# ---------------------------------------------------------------------------


def _overall_state(session: ScanSession) -> str:
    statuses = [st.status for st in session.sources.values()]
    if any(s in (PENDING, RUNNING) for s in statuses):
        return S_RUNNING
    considered = [s for s in statuses if s != UNMAPPED]
    if not considered:
        return S_COMPLETED
    if all(s in TERMINAL_OK for s in considered):
        return S_COMPLETED
    if all(s in (FAILED, TIMEOUT) for s in considered):
        return S_FAILED
    return S_PARTIAL


def _summary(session: ScanSession) -> str:
    p = session.progress()
    ok = p[COMPLETED] + p[EMPTY]
    bad = p[FAILED] + p[TIMEOUT]
    parts = [f"{ok}/{p['total']} sources complete"]
    if p[PARTIAL] or p[CAPPED]:
        parts.append(f"{p[PARTIAL] + p[CAPPED]} partial/capped")
    if bad:
        parts.append(f"{bad} failed")
    if p[UNMAPPED]:
        parts.append(f"{p[UNMAPPED]} unmapped")
    note = "exact totals (search_count)" if session.count_supported else (
        "counts capped by the deployed Odoo workflow"
        if session.count_supported is False else "no sources scanned"
    )
    return "; ".join(parts) + f" — {note}."


async def _emit(on_progress: ProgressFn | None, session: ScanSession) -> None:
    if on_progress is None:
        return
    try:
        await on_progress(session.snapshot())
    except Exception:  # noqa: BLE001 — persistence must never break the scan
        pass


async def run_scan_session(
    session: ScanSession,
    *,
    odoo_config: dict[str, Any],
    allowed_odoo_ids: list[str],
    sources: list[OdooSource],
    read_fn: ReadFn = read_odoo,
    count_fn: CountFn = count_odoo,
    cfg: ScanConfig | None = None,
    on_progress: ProgressFn | None = None,
) -> ScanSession:
    """Scan ``sources`` sequentially, isolating each. Updates ``session`` in place.

    Sequential + strict per-source timeout means one slow source can never block
    the rest: its budget expires and the scan moves on. ``on_progress`` is invoked
    after every source so the UI can poll live, incremental results.
    """
    cfg = cfg or ScanConfig()
    session.state = S_RUNNING
    session.started_at = session.started_at or _now_iso()
    session.updated_at = _now_iso()
    await _emit(on_progress, session)

    for source in sources:
        prior = session.sources.get(source.key)
        running = SourceScanState(key=source.key, status=RUNNING)
        if prior:
            running.pages_done = prior.pages_done
            running.next_offset = prior.next_offset
        session.sources[source.key] = running
        session.updated_at = _now_iso()
        await _emit(on_progress, session)

        try:
            result = await scan_one_source(
                source,
                project_code=session.project_code,
                odoo_config=odoo_config,
                allowed_odoo_ids=allowed_odoo_ids,
                read_fn=read_fn,
                count_fn=count_fn,
                cfg=cfg,
                prior=prior,
            )
        except Exception as exc:  # noqa: BLE001 — absolute safety net
            result = SourceScanState(key=source.key, status=FAILED)
            result.error = f"engine: {type(exc).__name__}: {exc}"
            result.last_scanned_at = _now_iso()

        if session.count_supported is None and result.total is not None:
            session.count_supported = True
        elif session.count_supported is None and result.status == CAPPED:
            session.count_supported = False

        session.sources[source.key] = result
        session.updated_at = _now_iso()
        await _emit(on_progress, session)

    session.state = _overall_state(session)
    session.finished_at = _now_iso()
    session.updated_at = session.finished_at
    session.summary = _summary(session)
    await _emit(on_progress, session)
    return session


# ---------------------------------------------------------------------------
# Session construction + retry/resume selection
# ---------------------------------------------------------------------------


def new_session_id() -> str:
    return uuid.uuid4().hex


def all_source_keys() -> list[str]:
    return [s.key for s in ODOO_SOURCES]


def sources_for_keys(keys: list[str]) -> list[OdooSource]:
    wanted = set(keys)
    return [s for s in ODOO_SOURCES if s.key in wanted]


def init_full_session(project_code: str, *, session_id: str | None = None) -> ScanSession:
    """A fresh session with every registry source queued as ``pending``."""
    sess = ScanSession(
        session_id=session_id or new_session_id(),
        project_code=project_code,
        state=S_PENDING,
        started_at=_now_iso(),
        updated_at=_now_iso(),
    )
    for s in ODOO_SOURCES:
        sess.sources[s.key] = SourceScanState(key=s.key, status=PENDING)
    return sess


def select_retry_keys(session: ScanSession, *, mode: str = "failed") -> list[str]:
    """Keys to re-scan. ``failed`` → failed/timeout only; ``incomplete`` → also
    partial/capped/pending/running (resume)."""
    pool = RETRYABLE if mode == "failed" else INCOMPLETE
    return [k for k, st in session.sources.items() if st.status in pool]


# ---------------------------------------------------------------------------
# Live in-process registry (single-worker uvicorn). Durable copy lives in PG.
# ---------------------------------------------------------------------------

ACTIVE_SESSIONS: dict[str, ScanSession] = {}


def register(session: ScanSession) -> None:
    ACTIVE_SESSIONS[session.session_id] = session


def get_active(session_id: str) -> ScanSession | None:
    return ACTIVE_SESSIONS.get(session_id)


def active_running_for_project(project_code: str) -> ScanSession | None:
    for sess in ACTIVE_SESSIONS.values():
        if sess.project_code == project_code and sess.state in (S_PENDING, S_RUNNING):
            return sess
    return None


__all__ = [
    "ScanConfig",
    "ScanSession",
    "SourceScanState",
    "run_scan_session",
    "scan_one_source",
    "init_full_session",
    "select_retry_keys",
    "sources_for_keys",
    "all_source_keys",
    "new_session_id",
    "register",
    "get_active",
    "active_running_for_project",
    "ACTIVE_SESSIONS",
    # statuses
    "PENDING", "RUNNING", "COMPLETED", "PARTIAL", "CAPPED", "EMPTY",
    "FAILED", "TIMEOUT", "UNMAPPED", "NOT_SCANNED",
    "S_PENDING", "S_RUNNING", "S_COMPLETED", "S_PARTIAL", "S_FAILED",
    "TERMINAL_OK", "RETRYABLE", "INCOMPLETE",
    "source_by_key",
]
