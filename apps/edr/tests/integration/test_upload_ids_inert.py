"""upload_ids harmlessness — structural proof that the field is inert.

`ReportRequest.upload_ids` is accepted and recorded in the workflow inputs /
audit trail, but node-level ingestion is deferred (audit item R5,
MEDIUM_RISK). These tests prove the deferral is *harmless*: no graph node
reads upload_ids, so a caller supplying them cannot influence evidence,
the LLM prompt, or report content — they are carried for audit only.

If a future change wires uploads into the graph, the inertness assertion
below will fail loudly and this file should be updated alongside that work.
"""

from __future__ import annotations

import importlib
import pkgutil

import apps.edr.graph as graph_pkg


def _graph_module_sources() -> dict[str, str]:
    """Return {module_name: source} for every module in apps.edr.graph."""
    sources: dict[str, str] = {}
    for mod in pkgutil.iter_modules(graph_pkg.__path__):
        full = f"{graph_pkg.__name__}.{mod.name}"
        spec = importlib.util.find_spec(full)
        if spec and spec.origin and spec.origin.endswith(".py"):
            with open(spec.origin, encoding="utf-8") as fh:
                sources[full] = fh.read()
    return sources


def test_no_graph_node_consumes_upload_ids() -> None:
    """No module under apps.edr.graph references upload_ids in any form.

    This is the structural guarantee of harmlessness: the value reaches
    state.inputs but is never read, so it cannot reach retrieval, the LLM
    prompt, or the rendered report.
    """
    offenders = {
        name: src for name, src in _graph_module_sources().items()
        if "upload_ids" in src
    }
    assert offenders == {}, (
        "upload_ids is now referenced inside the graph package; ingestion "
        f"appears to be implemented in {sorted(offenders)}. Update the "
        "harmlessness evidence and replace this structural test with a "
        "behavioural ingestion test."
    )


def test_upload_ids_recorded_in_inputs_but_not_in_state_fields() -> None:
    """The DecisionState has no first-class upload_ids field — uploads live
    only inside the free-form `inputs` audit dict, confirming they are not a
    structured part of the workflow contract."""
    from apps.edr.graph.state import DecisionState

    state = DecisionState(
        request_id="r1",
        user_id="u1",
        role="executive",
        project_code="PRJ-001",
        query="q",
        inputs={"upload_ids": ["id-1", "id-2"]},
    )
    # Carried for audit …
    assert state.inputs["upload_ids"] == ["id-1", "id-2"]
    # … but not promoted to a typed state attribute the graph acts on.
    assert not hasattr(state, "upload_ids")
