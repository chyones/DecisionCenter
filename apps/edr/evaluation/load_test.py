"""Local-only load test for Decision Center.

Spec: Section 23 (deployment profile: ≤ 5 concurrent).
Uses deterministic fallback (no external LLM APIs).
Does not hit production or external services.

First run establishes a baseline; no permanent p95 thresholds are enforced.
Results are written to a JSON file for trend tracking.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from apps.edr.graph.runner import run_workflow
from apps.edr.graph.state import DecisionState


_CONCURRENCY = 5
_REQUESTS = 10
_WARMUP = 2


async def _run_single(request_id: str, query: str, project_code: str) -> dict[str, Any]:
    state = DecisionState(
        request_id=request_id,
        user_id="load-test-user",
        role="executive",
        project_code=project_code,
        query=query,
    )
    start = time.perf_counter()
    try:
        result = await run_workflow(state)
        duration_ms = (time.perf_counter() - start) * 1000
        return {
            "request_id": request_id,
            "duration_ms": round(duration_ms, 2),
            "visited_nodes": len(result.visited_nodes),
            "rbac_status": result.outputs.get("rbac_status"),
            "quality_gate": result.outputs.get("quality_gate"),
            "error": None,
        }
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        return {
            "request_id": request_id,
            "duration_ms": round(duration_ms, 2),
            "visited_nodes": 0,
            "rbac_status": None,
            "quality_gate": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _warmup() -> None:
    for i in range(_WARMUP):
        await _run_single(f"warmup-{i}", "Project status?", "PRJ-001")


async def _run_load(concurrency: int, total: int) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(idx: int) -> dict[str, Any]:
        async with semaphore:
            return await _run_single(
                f"load-{idx:03d}",
                "What is the budget vs actual for this project?",
                "PRJ-001",
            )

    return await asyncio.gather(*(_bounded(i) for i in range(total)))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    return s[f] + (k - f) * (s[c] - s[f])


def _print_report(results: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    durations = [r["duration_ms"] for r in results if r["error"] is None]
    errors = [r for r in results if r["error"] is not None]

    report: dict[str, Any] = {
        "concurrency": concurrency,
        "total_requests": len(results),
        "successful": len(durations),
        "errors": len(errors),
        "min_ms": round(min(durations), 2) if durations else 0.0,
        "max_ms": round(max(durations), 2) if durations else 0.0,
        "p50_ms": round(_percentile(durations, 0.50), 2) if durations else 0.0,
        "p95_ms": round(_percentile(durations, 0.95), 2) if durations else 0.0,
        "p99_ms": round(_percentile(durations, 0.99), 2) if durations else 0.0,
        "error_details": [{"request_id": e["request_id"], "error": e["error"]} for e in errors],
    }

    print("=" * 60)
    print("Decision Center Local Load Test")
    print("=" * 60)
    print(f"Concurrency    : {report['concurrency']}")
    print(f"Total requests : {report['total_requests']}")
    print(f"Successful     : {report['successful']}")
    print(f"Errors         : {report['errors']}")
    print(f"Min latency    : {report['min_ms']} ms")
    print(f"Max latency    : {report['max_ms']} ms")
    print(f"p50 latency    : {report['p50_ms']} ms")
    print(f"p95 latency    : {report['p95_ms']} ms")
    print(f"p99 latency    : {report['p99_ms']} ms")
    if errors:
        print("-" * 60)
        for e in errors:
            print(f"ERROR {e['request_id']}: {e['error']}")
    print("=" * 60)
    print("\nNote: This is a baseline run. Do not use these values as")
    print("permanent thresholds without multiple runs and trend analysis.")

    return report


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local load test")
    parser.add_argument("--concurrency", type=int, default=_CONCURRENCY)
    parser.add_argument("--requests", type=int, default=_REQUESTS)
    parser.add_argument("--output", default=None, help="JSON results path")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warmup")
    args = parser.parse_args(argv)

    print(f"Load test: concurrency={args.concurrency}, requests={args.requests}")
    if not args.no_warmup:
        print("Warming up...")
        await _warmup()

    print("Running load test...")
    results = await _run_load(args.concurrency, args.requests)
    report = _print_report(results, args.concurrency)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nResults written to {args.output}")

    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
