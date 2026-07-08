"""Node 8 - Odoo Facts Retrieval. Spec: Sections 4.4 and 16.

Retrieves the project record (project.project) and, when the project mapping
declares a verified analytic account, the real posted cost lines
(account.analytic.line). Financial figures are NEVER taken from nonexistent
project.project columns (budget/actual_cost) and are NEVER invented — if no
verified cost evidence exists, that is recorded so the report can state
"financial data not available in verified Odoo evidence".

When extended multi-source retrieval is enabled (``odoo_extended_sources_enabled``
or per-mapping ``odoo.extended_sources``), the node also reads the high-confidence
project sources proven by the 2026-06-16 source-mapping audit (purchase orders,
material requests, stock, vendor bills, payroll/manpower, attachments, …) using
ONLY the proven project-link paths in ``apps/edr/connectors/odoo_sources.py``.
All queries are read-only and ambiguous/denylisted paths can never be issued.
"""

import asyncio
import logging
import time

from apps.edr.config import settings
from apps.edr.connectors.odoo import (
    build_all_source_queries,
    build_cost_query,
    build_project_query,
    read_odoo,
)
from apps.edr.graph import coverage
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore

logger = logging.getLogger(__name__)

# /reports/staging has a 90s route budget. Keep Odoo fail-soft and leave room
# for the later draft/quality/export/persistence stages.
# Inline (mandatory) reads get more time because the live Odoo backend is
# intermittently slow; extended (optional) reads keep a bounded per-source cap
# (settings.odoo_extended_source_timeout_s, still clipped by the node budget).
ODOO_NODE_BUDGET_S = 50.0
ODOO_PROJECT_IDENTITY_TIMEOUT_S = 25.0
ODOO_ACTUAL_COST_TIMEOUT_S = 20.0
ODOO_EXTENDED_SOURCE_TIMEOUT_S = settings.odoo_extended_source_timeout_s
ODOO_RETRY_BACKOFF_S = 0.5
ODOO_MAX_RETRIES = 1


def _enabled(mapping: dict) -> bool:
    return "odoo" in set(mapping.get("enabled_sources", []))


def _extended_enabled(odoo_config: dict) -> bool:
    """Extended retrieval runs when the global flag OR the mapping opts in."""
    return bool(
        settings.odoo_extended_sources_enabled
        or odoo_config.get("extended_sources")
    )


def _remaining_timeout(deadline: float, cap_s: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise asyncio.TimeoutError
    return min(cap_s, remaining)


async def _read_odoo_timed(
    payload: dict,
    *,
    request_id: str,
    label: str,
    timeout_s: float,
) -> list:
    start = time.perf_counter()
    logger.info(
        "odoo_read_start request_id=%s source=%s timeout_s=%.1f",
        request_id,
        label,
        timeout_s,
    )
    try:
        evidence = await asyncio.wait_for(read_odoo(payload), timeout=timeout_s)
    except asyncio.TimeoutError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "odoo_read_timeout request_id=%s source=%s duration_ms=%d",
            request_id,
            label,
            duration_ms,
        )
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "odoo_read_error request_id=%s source=%s duration_ms=%d error_class=%s",
            request_id,
            label,
            duration_ms,
            exc.__class__.__name__,
        )
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "odoo_read_end request_id=%s source=%s duration_ms=%d count=%d",
        request_id,
        label,
        duration_ms,
        len(evidence),
    )
    return evidence


async def _read_odoo_with_retry(
    payload: dict,
    *,
    request_id: str,
    label: str,
    timeout_s: float,
    deadline: float,
) -> list:
    """Read Odoo with one retry on non-timeout failures.

    The live n8n/Odoo webhook intermittently returns 502 during authentication
    or query dispatch. A single short retry absorbs these transient errors
    without masking true failures or exceeding the node budget.
    """
    last_exc: Exception | None = None
    for attempt in range(ODOO_MAX_RETRIES + 1):
        try:
            return await _read_odoo_timed(
                payload,
                request_id=request_id,
                label=label,
                timeout_s=_remaining_timeout(deadline, timeout_s),
            )
        except asyncio.TimeoutError:
            # Timeouts indicate the backend is genuinely slow; do not burn budget
            # retrying slow calls.
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == ODOO_MAX_RETRIES:
                break
            # Only retry if the node budget can fit another attempt plus backoff.
            if deadline - time.monotonic() < timeout_s + ODOO_RETRY_BACKOFF_S + 0.5:
                break
            logger.warning(
                "odoo_read_retry request_id=%s source=%s attempt=%d error_class=%s",
                request_id,
                label,
                attempt + 1,
                exc.__class__.__name__,
            )
            await asyncio.sleep(ODOO_RETRY_BACKOFF_S)
    assert last_exc is not None
    raise last_exc


async def _retrieve_extended_sources(
    state: DecisionState, odoo_config: dict, deadline: float
) -> int:
    """Read every proven, mappable Odoo source and tag the evidence.

    Returns the number of evidence items added. Each source is isolated: one
    failing/empty source never aborts the others (read-only, graceful). Per
    source results are recorded in ``state.outputs`` for the report/operator.
    """
    specs = build_all_source_queries(
        odoo_config, include_medium=settings.odoo_extended_include_medium
    )
    counts: dict[str, int] = {}
    statuses: dict[str, str] = {}
    added = 0

    for spec in specs:
        key = spec["key"]
        query = spec["query"]
        if query is None:
            statuses[key] = "unmapped"  # project mapping lacks the needed id
            counts[key] = 0
            continue
        model, domain, fields, limit = query
        payload = {
            "project_code": state.project_code,
            "model": model,
            "domain": domain,
            "fields": fields,
            "limit": limit,
            "allowed_odoo_ids": state.allowed_odoo_ids,
        }
        try:
            timeout_s = _remaining_timeout(deadline, ODOO_EXTENDED_SOURCE_TIMEOUT_S)
            evidence = await _read_odoo_timed(
                payload,
                request_id=state.request_id,
                label=key,
                timeout_s=timeout_s,
            )
        except asyncio.TimeoutError:
            statuses[key] = "timeout"
            counts[key] = 0
            if deadline - time.monotonic() <= 0:
                statuses["__budget__"] = f"timeout_after_{ODOO_NODE_BUDGET_S:g}s"
                break
            continue
        except Exception as exc:  # one bad source must not drop the rest
            statuses[key] = f"error: {type(exc).__name__}"
            counts[key] = 0
            continue

        for ev in evidence:
            row = ev.model_dump()
            meta = row.get("metadata") or {}
            meta["odoo_source_key"] = key
            meta["odoo_category"] = spec["category"]
            meta["odoo_confidence"] = spec["confidence"]
            row["metadata"] = meta
            tags = list(row.get("tags") or [])
            if spec["category"] not in tags:
                tags.append(spec["category"])
            row["tags"] = tags
            state.evidence.append(row)

        counts[key] = len(evidence)
        statuses[key] = "ok" if evidence else "empty"
        added += len(evidence)

    state.outputs["odoo_source_counts"] = counts
    state.outputs["odoo_source_status"] = statuses
    state.outputs["odoo_extended_total"] = added
    return added


async def run(state: DecisionState) -> DecisionState:
    try:
        mapping = ProjectMapping.load().get(state.project_code)
    except Exception:
        mapping = {}
    enabled = _enabled(mapping)

    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_odoo_budget:
            state.outputs["odoo_status"] = "rbac_denied"
            coverage.record(state, "odoo", enabled=enabled, attempted=False,
                            status="rbac_denied", evidence_count=0,
                            reason="Role not permitted to access Odoo budget data.")
            return state.mark("node_08_odoo")

    odoo_config = mapping.get("odoo", {})
    added = 0
    financial_available = False
    project_ev: list = []
    cost_ev: list = []
    deadline = time.monotonic() + ODOO_NODE_BUDGET_S
    try:
        # 1) Project record (always)
        domain, fields = build_project_query(odoo_config, state.project_code)
        payload = {
            "project_code": state.project_code,
            "model": odoo_config.get("project_model", "project.project"),
            "domain": domain,
            "fields": fields,
            "allowed_odoo_ids": state.allowed_odoo_ids,
        }
        project_ev = await _read_odoo_with_retry(
            payload,
            request_id=state.request_id,
            label="project_identity",
            timeout_s=ODOO_PROJECT_IDENTITY_TIMEOUT_S,
            deadline=deadline,
        )
        state.evidence.extend([e.model_dump() for e in project_ev])
        added += len(project_ev)

        # 2) Cost lines from the verified analytic account (real posted costs only)
        cost_q = build_cost_query(odoo_config)
        if cost_q is not None:
            cost_model, cost_domain, cost_fields = cost_q
            cost_payload = {
                "project_code": state.project_code,
                "model": cost_model,
                "domain": cost_domain,
                "fields": cost_fields,
                "limit": 100,
                "allowed_odoo_ids": state.allowed_odoo_ids,
            }
            try:
                cost_ev = await _read_odoo_with_retry(
                    cost_payload,
                    request_id=state.request_id,
                    label="actual_cost",
                    timeout_s=ODOO_ACTUAL_COST_TIMEOUT_S,
                    deadline=deadline,
                )
                state.evidence.extend([e.model_dump() for e in cost_ev])
                added += len(cost_ev)
                financial_available = len(cost_ev) > 0
            except asyncio.TimeoutError:
                state.outputs["odoo_cost_status"] = "timeout"
            except Exception as exc:
                state.outputs["odoo_cost_status"] = f"error: {exc}"
        else:
            state.outputs["odoo_cost_status"] = "no_verified_analytic_account"

        # 3) Extended proven sources (purchase/MR/stock/accounting/payroll/docs).
        #    Opt-in; read-only; proven link paths only; never weakens financials.
        if _extended_enabled(odoo_config):
            try:
                added += await _retrieve_extended_sources(state, odoo_config, deadline)
            except Exception as exc:
                state.outputs["odoo_extended_status"] = f"error: {type(exc).__name__}"
            else:
                statuses = state.outputs.get("odoo_source_status", {})
                state.outputs["odoo_extended_status"] = (
                    "timeout"
                    if "__budget__" in statuses or any(v == "timeout" for v in statuses.values())
                    else "ok"
                )
        else:
            state.outputs["odoo_extended_status"] = "disabled"

        has_timeout = (
            state.outputs.get("odoo_cost_status") == "timeout"
            or state.outputs.get("odoo_extended_status") == "timeout"
        )
        state.outputs["odoo_status"] = (
            f"partial_timeout ({added} items)" if has_timeout else f"ok ({added} items)"
        )
        state.outputs["odoo_financial_available"] = financial_available
        if not financial_available:
            state.outputs["odoo_financial_note"] = (
                "financial data not available in verified Odoo evidence"
            )

        if added > 0:
            cov_status, cov_reason = "ok", ""
        else:
            cov_status = "zero_no_match"
            cov_reason = "Odoo returned no records for the mapped project id."
        coverage.record(state, "odoo", enabled=enabled, attempted=True,
                        status=cov_status, evidence_count=added, reason=cov_reason)

        # Embeddings/Qdrant insert is supplementary; failure does not drop evidence.
        try:
            embedder = EmbeddingClient(settings.voyage_api_key)
            store = EvidenceStore()
            store.ensure_collection(state.project_code)
            all_ev = list(project_ev) + list(cost_ev)
            texts = [e.excerpt for e in all_ev]
            vectors = await embedder.embed(texts)
            for ev, vec in zip(all_ev, vectors):
                store.insert(state.project_code, ev.evidence_id, vec, ev.model_dump())
            state.outputs["odoo_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["odoo_qdrant_status"] = f"error: {exc}"
    except asyncio.TimeoutError:
        state.outputs["odoo_status"] = f"timeout_after_{ODOO_NODE_BUDGET_S:g}s ({added} items)"
        state.outputs["odoo_financial_available"] = financial_available
        if not financial_available:
            state.outputs["odoo_financial_note"] = (
                "financial data not available in verified Odoo evidence"
            )
        coverage.record(state, "odoo", enabled=enabled, attempted=True,
                        status="timeout", evidence_count=added,
                        reason=f"Odoo retrieval exceeded {ODOO_NODE_BUDGET_S:g}s budget.")
    except Exception as exc:
        state.outputs["odoo_status"] = f"error: {exc}"
        coverage.record(state, "odoo", enabled=enabled, attempted=True,
                        status="error", evidence_count=added,
                        reason=f"Odoo connector error: {exc}")

    return state.mark("node_08_odoo")
