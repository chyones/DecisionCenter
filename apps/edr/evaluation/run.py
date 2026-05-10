"""Evaluation runner for Decision Center golden set.

Spec: Section 26 (Evaluation & Testing).

Loads JSONL cases, executes deterministic or workflow test paths,
and emits per-case results plus aggregate metrics.
Exits non-zero on any regression so it can gate CI.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from apps.edr.evaluation.metrics import evidence_precision, refusal_accuracy
from apps.edr.graph.state import DecisionState


# ---------------------------------------------------------------------------
# Case execution
# ---------------------------------------------------------------------------


def _load_cases(suite_dir: Path) -> list[dict[str, Any]]:
    """Load all *.jsonl files from the suite directory."""
    cases: list[dict[str, Any]] = []
    for path in sorted(suite_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                cases.append(json.loads(line))
    return cases


def _build_state(case: dict[str, Any]) -> DecisionState:
    """Construct a DecisionState from the case 'state' block."""
    raw = case.get("state", {})
    # Only pass fields that DecisionState accepts
    known = {
        "request_id",
        "user_id",
        "role",
        "project_code",
        "query",
        "allowed_projects",
        "allowed_mailboxes",
        "allowed_odoo_ids",
        "inputs",
        "evidence",
        "outputs",
        "visited_nodes",
        "output_formats",
        "report_json",
        "cost_accumulated_usd",
        "loop_count",
    }
    kwargs = {k: v for k, v in raw.items() if k in known}
    return DecisionState(**kwargs)


def _resolve(state: DecisionState, key: str) -> Any:
    """Resolve an expectation key against a DecisionState result."""
    if key == "visited_nodes_count":
        return len(state.visited_nodes)
    if key == "evidence_count":
        return len(state.evidence)
    if key == "loop_count":
        return state.loop_count
    # Quality-gate metric aliases (node_13 uses spaced keys)
    if key == "unsupported_count":
        return state.outputs.get("quality_gate unsupported_count")
    if key == "needs_review_count":
        return state.outputs.get("quality_gate needs_review_count")
    if key.startswith("outputs."):
        return state.outputs.get(key[8:])
    if key.startswith("report_json."):
        return (state.report_json or {}).get(key[12:])
    if hasattr(state, key):
        return getattr(state, key)
    return state.outputs.get(key)


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Execute a single case and return the result record."""
    case_id = case["id"]
    category = case.get("category", "uncategorized")
    node = case.get("node", "node_13_quality_gate")
    expect = case.get("expect", {})

    state = _build_state(case)
    start = time.perf_counter()

    expected_error = case.get("expect_error")
    actual_error: str | None = None

    try:
        if node == "workflow":
            from apps.edr.graph.runner import run_workflow

            result = await run_workflow(state)
        else:
            mod = importlib.import_module(f"apps.edr.graph.{node}")
            result = await mod.run(state)
    except Exception as exc:
        actual_error = f"{type(exc).__name__}: {exc}"
        if expected_error is True:
            return {
                "id": case_id,
                "category": category,
                "passed": True,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "error": actual_error,
                "failures": [],
            }
        if isinstance(expected_error, str) and expected_error in actual_error:
            return {
                "id": case_id,
                "category": category,
                "passed": True,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "error": actual_error,
                "failures": [],
            }
        return {
            "id": case_id,
            "category": category,
            "passed": False,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": actual_error,
            "failures": [],
        }

    if expected_error is not None:
        return {
            "id": case_id,
            "category": category,
            "passed": False,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": None,
            "failures": [{"field": "error", "expected": expected_error, "actual": None}],
        }

    failures: list[dict[str, Any]] = []
    for key, expected in expect.items():
        actual = _resolve(result, key)
        if actual != expected:
            failures.append({"field": key, "expected": expected, "actual": actual})

    return {
        "id": case_id,
        "category": category,
        "passed": len(failures) == 0,
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        "error": None,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Metrics & reporting
# ---------------------------------------------------------------------------


def _compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        by_category.setdefault(cat, {"passed": 0, "failed": 0})
        by_category[cat]["passed" if r["passed"] else "failed"] += 1

    # Claim-to-evidence precision among cases that define expect.quality_gate == passed
    supported_claims = 0
    total_claims = 0
    for r in results:
        if r["passed"] and r.get("error") is None:
            supported_claims += 1
        total_claims += 1

    precision = evidence_precision(supported_claims, total_claims)

    # Refusal accuracy: cases with "unauthorized" in category should fail
    correct_refusals = 0
    required_refusals = 0
    for r in results:
        if "unauthorized" in r["category"]:
            required_refusals += 1
            if not r["passed"]:
                correct_refusals += 1
    refusal_acc = refusal_accuracy(correct_refusals, required_refusals)

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "evidence_precision": round(precision, 4),
        "refusal_accuracy": round(refusal_acc, 4),
        "by_category": by_category,
    }


def _print_report(results: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    print("=" * 60)
    print("Decision Center Evaluation Report")
    print("=" * 60)
    print(f"Total cases : {metrics['total']}")
    print(f"Passed      : {metrics['passed']}")
    print(f"Failed      : {metrics['failed']}")
    print(f"Pass rate   : {metrics['pass_rate']:.2%}")
    print(f"Precision   : {metrics['evidence_precision']:.2%}")
    print(f"Refusal acc : {metrics['refusal_accuracy']:.2%}")
    print("-" * 60)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']} ({r['category']}) {r['duration_ms']}ms")
        if r["error"]:
            print(f"       ERROR: {r['error']}")
        for f in r["failures"]:
            print(f"       FIELD {f['field']}: expected {f['expected']!r}, got {f['actual']!r}")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _suite_path(name: str) -> Path:
    root = Path(__file__).resolve().parent
    return root / name


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decision Center evaluation runner")
    parser.add_argument("--suite", default="goldenset", help="Suite subdirectory name")
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    parser.add_argument("--max-failures", type=int, default=0, help="Max allowed failures before non-zero exit")
    args = parser.parse_args(argv)

    suite_dir = _suite_path(args.suite)
    if not suite_dir.exists():
        print(f"Suite directory not found: {suite_dir}", file=sys.stderr)
        return 2

    cases = _load_cases(suite_dir)
    if not cases:
        print(f"No cases found in {suite_dir}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for case in cases:
        result = await _run_case(case)
        results.append(result)

    metrics = _compute_metrics(results)
    _print_report(results, metrics)

    if args.output:
        report = {"metrics": metrics, "results": results}
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")

    failed_count = metrics["failed"]
    if failed_count > args.max_failures:
        print(f"\nREGRESSION: {failed_count} failure(s) > max {args.max_failures}", file=sys.stderr)
        return 1

    print("\nEvaluation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
