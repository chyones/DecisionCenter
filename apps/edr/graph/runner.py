import asyncio
from collections.abc import Callable, Coroutine
import logging
import time
from typing import Any

from apps.edr.graph import (
    node_00_begin,
    node_01_auth,
    node_02_intent,
    node_03_scope,
    node_04_plan,
    node_05_sharepoint,
    node_06_owncloud,
    node_07_email,
    node_08_odoo,
    node_09_normalize,
    node_10_sufficiency,
    node_11_self_correct,
    node_12_draft_json,
    node_13_quality_gate,
    node_14_compose_md,
    node_15_save_audit,
    node_16_review,
    node_17_publish,
)
from apps.edr.graph.state import DecisionState

Node = Callable[[DecisionState], Coroutine[Any, Any, DecisionState]]
logger = logging.getLogger(__name__)

NODES: tuple[Node, ...] = (
    node_00_begin.run,
    node_01_auth.run,
    node_02_intent.run,
    node_03_scope.run,
    node_04_plan.run,
    node_05_sharepoint.run,
    node_06_owncloud.run,
    node_07_email.run,
    node_08_odoo.run,
    node_09_normalize.run,
    node_10_sufficiency.run,
    node_11_self_correct.run,
    node_12_draft_json.run,
    node_13_quality_gate.run,
    node_14_compose_md.run,
    node_15_save_audit.run,
    node_16_review.run,
    node_17_publish.run,
)

NODE_COUNT = len(NODES)


async def run_workflow(state: DecisionState) -> DecisionState:
    for node in NODES:
        stage = node.__module__.rsplit(".", 1)[-1]
        start = time.perf_counter()
        logger.info(
            "workflow_stage_start request_id=%s stage=%s",
            state.request_id,
            stage,
        )
        try:
            state = await node(state)
        except asyncio.CancelledError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "workflow_stage_error request_id=%s stage=%s duration_ms=%d "
                "error_class=%s",
                state.request_id,
                stage,
                duration_ms,
                exc.__class__.__name__,
            )
            raise
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "workflow_stage_error request_id=%s stage=%s duration_ms=%d "
                "error_class=%s",
                state.request_id,
                stage,
                duration_ms,
                exc.__class__.__name__,
            )
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "workflow_stage_end request_id=%s stage=%s duration_ms=%d status=ok",
            state.request_id,
            stage,
            duration_ms,
        )
    return state
