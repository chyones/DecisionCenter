"""LLM client with cost guardrails, prompt-injection protection, and Langfuse tracing.

Spec: Sections 20.1 (LLM tiers), 22 (cost model), 24.1 (prompt injection).

Provider selection (LLM_PROVIDER): "anthropic" (default) or "deepseek".
Anthropic support is kept intact; the switch only changes which provider
serves generation at runtime.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from apps.edr.config import settings

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Locked model IDs from spec Section 20.1
# ---------------------------------------------------------------------------
_LIGHT_MODEL = "claude-haiku-4-5"
_HEAVY_MODEL = "claude-sonnet-4-6"

_TIER_MODELS: dict[str, str] = {
    "light": _LIGHT_MODEL,
    "heavy": _HEAVY_MODEL,
}

# Per-request token caps from spec Section 22.2
# Heavy-tier output raised to accommodate the management_question_answer contract.
_TIER_CAPS: dict[str, dict[str, int]] = {
    "light": {"input": 200_000, "output": 10_000},
    "heavy": {"input": 60_000, "output": 8_000},
}

# Locked DeepSeek model IDs (same locking convention as the Anthropic tiers).
# The DeepSeek API accepts only deepseek-v4-flash and deepseek-v4-pro
# (HTTP 400 observed live 2026-06-12 for any other name, including the
# retired deepseek-chat). Flash serves the light/default tier; pro serves
# the heavy (report) tier.
_DEEPSEEK_LIGHT_MODEL = "deepseek-v4-flash"
_DEEPSEEK_HEAVY_MODEL = "deepseek-v4-pro"
_DEEPSEEK_DEFAULT_MODEL = _DEEPSEEK_LIGHT_MODEL

_DEEPSEEK_TIER_MODELS: dict[str, str] = {
    "light": _DEEPSEEK_LIGHT_MODEL,
    "heavy": _DEEPSEEK_HEAVY_MODEL,
}

# DeepSeek caps: deepseek-chat exposes a 64K context window and 8K max output,
# so both tiers are clamped below the Anthropic figures.
_DEEPSEEK_TIER_CAPS: dict[str, dict[str, int]] = {
    "light": {"input": 56_000, "output": 8_000},
    "heavy": {"input": 56_000, "output": 12_000},
}

# Cost rates (USD per million tokens) — conservative estimates aligned with spec.
_COST_RATES: dict[str, dict[str, float]] = {
    _LIGHT_MODEL: {"input": 0.25, "output": 1.25},
    _HEAVY_MODEL: {"input": 3.00, "output": 15.00},
    _DEEPSEEK_LIGHT_MODEL: {"input": 0.27, "output": 1.10},
    _DEEPSEEK_HEAVY_MODEL: {"input": 0.55, "output": 2.19},
}

_DEEPSEEK_TIMEOUT_SECONDS = 120.0

# Prompt-injection patterns from spec Section 24.1
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions?|commands?|prompts?)",
    r"forget\s+(all\s+)?(previous|prior)\s+(instructions?|commands?|prompts?)",
    r"new\s+(instructions?|commands?|prompts?)\s*:",
    r"you\s+(are|must)\s+now\s+",
    r"^\s*system\s*:",
    r"^\s*assistant\s*:",
    r"^\s*human\s*:",
    r"<\s*/?\s*instruction\s*>",
    r"<\s*/?\s*system\s*>",
    r"<\s*/?\s*prompt\s*>",
    r"disregard\s+(the\s+)?(above|previous|prior)",
    r"override\s+(the\s+)?(previous|above)\s+(instructions?|rules?)",
]

_INJECTION_RE = re.compile("|".join(f"({p})" for p in _INJECTION_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class CostCapExceededError(Exception):
    """Raised when a call would breach the daily or per-request cost cap."""


class TokenCapExceededError(Exception):
    """Raised when a call would breach the per-request token cap."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LLMResult:
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
def active_provider() -> str:
    """Resolve the generation provider from settings ("anthropic" | "deepseek").

    Unknown values fall back to "anthropic" so a typo in LLM_PROVIDER cannot
    silently disable guardrails or route to an unintended endpoint.
    """
    provider = (settings.llm_provider or "anthropic").strip().lower()
    if provider not in ("anthropic", "deepseek"):
        return "anthropic"
    return provider


def _resolve_model_and_caps(provider: str, tier: str) -> tuple[str, dict[str, int]]:
    if provider == "deepseek":
        # Never forward an unknown tier string as the API model name — the
        # DeepSeek API rejects it with HTTP 400 (observed live with
        # tier="standard"). Unknown tiers resolve to the default model.
        model = _DEEPSEEK_TIER_MODELS.get(tier, _DEEPSEEK_DEFAULT_MODEL)
        return model, _DEEPSEEK_TIER_CAPS.get(tier, _DEEPSEEK_TIER_CAPS["heavy"])
    return _TIER_MODELS.get(tier, tier), _TIER_CAPS.get(tier, _TIER_CAPS["heavy"])


def _provider_key_available(provider: str) -> bool:
    if provider == "deepseek":
        return bool(settings.deepseek_api_key)
    return bool(settings.anthropic_api_key) and anthropic is not None


# ---------------------------------------------------------------------------
# Prompt-injection sanitizer
# ---------------------------------------------------------------------------
def sanitize_evidence(text: str) -> tuple[str, bool]:
    """Sanitize evidence text before it reaches an LLM prompt.

    Returns (sanitized_text, was_flagged).  Flagged content is neutered but
    preserved so the LLM can still treat it as evidence, not instruction.
    """
    if not text:
        return text, False

    def _replacer(match: re.Match[str]) -> str:  # pragma: no cover
        return "[BLOCKED]"

    sanitized = _INJECTION_RE.sub(_replacer, text)
    flagged = sanitized != text
    return sanitized, flagged


def sanitize_prompt(text: str) -> tuple[str, bool]:
    """Alias for sanitize_evidence; operates on the same rule set."""
    return sanitize_evidence(text)


# ---------------------------------------------------------------------------
# JSON fence stripping
# ---------------------------------------------------------------------------
# Some providers (DeepSeek in particular) wrap JSON answers in markdown code
# fences even when the prompt asks for raw JSON, which breaks json.loads in
# the graph nodes and silently routes reports to the deterministic
# evidence-builder. Strip a single outer fence; unfenced content is untouched.
_CODE_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Remove one outer markdown code fence (```json ... ```), if present."""
    match = _CODE_FENCE_RE.match(text or "")
    return match.group(1) if match else text


# ---------------------------------------------------------------------------
# Cost tracker (module-level singleton)
# ---------------------------------------------------------------------------
class _CostTracker:
    """Simple daily cost accumulator.

    In a multi-worker deployment this should be backed by Redis (Phase 1F).
    For Phase 1E a module-level singleton is sufficient because the app runs
    single-process inside its container.
    """

    def __init__(self) -> None:
        self._daily_cost: float = 0.0
        self._last_reset: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._token_usage: dict[str, dict[str, int]] = {}
        self._model_calls: dict[str, int] = {}
        self._model_costs: dict[str, float] = {}

    def _check_reset(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset:
            self._daily_cost = 0.0
            self._last_reset = today

    def check_budget(self, estimated_cost: float = 0.0) -> None:
        """Raise CostCapExceededError if the call would breach the daily cap."""
        self._check_reset()
        projected = self._daily_cost + estimated_cost
        if projected >= settings.daily_cost_cap_usd:
            raise CostCapExceededError(
                f"Daily cost cap USD {settings.daily_cost_cap_usd:.2f} would be exceeded "
                f"(current: {self._daily_cost:.4f}, estimated add: {estimated_cost:.4f})"
            )

    def record_cost(self, cost: float, model: str | None = None) -> None:
        self._check_reset()
        self._daily_cost += cost
        if model:
            self._model_calls[model] = self._model_calls.get(model, 0) + 1
            self._model_costs[model] = self._model_costs.get(model, 0.0) + cost

    def record_tokens(self, request_id: str, input_tokens: int, output_tokens: int) -> None:
        if request_id not in self._token_usage:
            self._token_usage[request_id] = {"input": 0, "output": 0}
        self._token_usage[request_id]["input"] += input_tokens
        self._token_usage[request_id]["output"] += output_tokens

    def get_tokens(self, request_id: str) -> dict[str, int]:
        return dict(self._token_usage.get(request_id, {"input": 0, "output": 0}))

    @property
    def daily_cost(self) -> float:
        self._check_reset()
        return self._daily_cost

    def get_model_breakdown(self) -> list[dict[str, object]]:
        self._check_reset()
        return [
            {
                "model": model,
                "calls": self._model_calls.get(model, 0),
                "cost_usd": round(self._model_costs.get(model, 0.0), 4),
            }
            for model in sorted(self._model_calls.keys())
        ]


_cost_tracker = _CostTracker()


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_RATES.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def _estimate_tokens_from_text(text: str) -> int:
    """Rough token estimate: ~1.3 tokens per word."""
    return int(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Langfuse helper
# ---------------------------------------------------------------------------
def _langfuse_trace(
    request_id: str,
    node_name: str,
    model: str,
    tier: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    flagged: bool,
    prompt: str,
    response_text: str,
) -> None:
    if Langfuse is None:
        return
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return

    try:
        lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        trace = lf.trace(
            id=request_id,
            name=node_name,
            metadata={
                "tier": tier,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 6),
                "latency_ms": round(latency_ms, 2),
                "prompt_injection_flagged": flagged,
            },
        )
        trace.generation(
            name=f"{node_name}_generation",
            model=model,
            input=prompt,
            output=response_text,
            usage={"input": input_tokens, "output": output_tokens},
        )
    except Exception:
        # Tracing must never break the workflow.
        pass


# ---------------------------------------------------------------------------
# Provider transports
# ---------------------------------------------------------------------------
async def _call_anthropic(
    model: str, prompt: str, max_tokens: int
) -> tuple[str, int, int]:
    """Anthropic Messages API. Returns (content, input_tokens, output_tokens)."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    input_tokens = response.usage.input_tokens if response.usage else 0
    output_tokens = response.usage.output_tokens if response.usage else 0
    content = response.content[0].text if response.content else ""
    return content, input_tokens, output_tokens


async def _call_deepseek(
    model: str, prompt: str, max_tokens: int
) -> tuple[str, int, int]:
    """DeepSeek chat-completions API (OpenAI-compatible).

    Returns (content, input_tokens, output_tokens).
    """
    async with httpx.AsyncClient(
        base_url=settings.deepseek_base_url,
        timeout=_DEEPSEEK_TIMEOUT_SECONDS,
    ) as client:
        response = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    content = message.get("content") or ""
    usage = data.get("usage") or {}
    return content, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


# ---------------------------------------------------------------------------
# Main LLM call
# ---------------------------------------------------------------------------
async def call_llm(
    prompt: str,
    tier: str,
    request_id: str,
    node_name: str,
    expect_json: bool = False,
    max_tokens: int | None = None,
) -> LLMResult:
    """Call the active generation provider with all Phase-1E guardrails.

    The provider is selected at runtime via ``LLM_PROVIDER`` ("anthropic" by
    default, "deepseek" to route generation to DeepSeek). Falls back to
    deterministic heuristics when the active provider's API key is not
    configured (local dev / CI).
    """
    provider = active_provider()
    model, caps = _resolve_model_and_caps(provider, tier)

    # 1. Prompt-injection protection on the prompt itself
    sanitized_prompt, flagged = sanitize_prompt(prompt)

    # 2. Cost guardrail (pre-call estimate)
    est_input_tokens = _estimate_tokens_from_text(sanitized_prompt)
    est_output_tokens = max_tokens or caps["output"]
    est_cost = _estimate_cost(model, est_input_tokens, est_output_tokens)
    _cost_tracker.check_budget(est_cost)

    # 3. Token cap guardrail (pre-call estimate)
    if est_input_tokens > caps["input"]:
        raise TokenCapExceededError(
            f"Input token cap exceeded for {tier}: {est_input_tokens} > {caps['input']}"
        )

    # 4. Fallback mode when the active provider's API key is missing
    if not _provider_key_available(provider):
        return _fallback_result(
            sanitized_prompt=sanitized_prompt,
            tier=tier,
            model=model,
            expect_json=expect_json,
            node_name=node_name,
            request_id=request_id,
        )

    # 5. Real provider call
    start = datetime.now(timezone.utc)

    if provider == "deepseek":
        content, input_tokens, output_tokens = await _call_deepseek(
            model, sanitized_prompt, max_tokens or caps["output"]
        )
    else:
        content, input_tokens, output_tokens = await _call_anthropic(
            model, sanitized_prompt, max_tokens or caps["output"]
        )

    if expect_json:
        content = strip_code_fences(content)

    latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    cost = _estimate_cost(model, input_tokens, output_tokens)

    # Record actual cost and tokens
    _cost_tracker.record_cost(cost, model=model)
    _cost_tracker.record_tokens(request_id, input_tokens, output_tokens)

    # 6. Langfuse tracing
    _langfuse_trace(
        request_id=request_id,
        node_name=node_name,
        model=model,
        tier=tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        flagged=flagged,
        prompt=sanitized_prompt,
        response_text=content,
    )

    return LLMResult(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        model=model,
    )


def _fallback_result(
    sanitized_prompt: str,
    tier: str,
    model: str,
    expect_json: bool,
    node_name: str,
    request_id: str,
) -> LLMResult:
    """Deterministic fallback when no API key is available.

    Produces syntactically valid output so the workflow can continue in CI.
    """
    content = _deterministic_output(sanitized_prompt, tier, expect_json, node_name)
    input_tokens = _estimate_tokens_from_text(sanitized_prompt)
    output_tokens = _estimate_tokens_from_text(content)
    cost = _estimate_cost(model, input_tokens, output_tokens)
    _cost_tracker.record_cost(cost, model=model)
    _cost_tracker.record_tokens(request_id, input_tokens, output_tokens)
    return LLMResult(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        model=model,
    )


def _deterministic_output(
    prompt: str, tier: str, expect_json: bool, node_name: str
) -> str:
    """Return a deterministic placeholder based on the node name."""
    if node_name == "node_02_intent":
        return json.dumps({"intents": [_infer_intent_from_query(prompt)]})

    if node_name == "node_03_scope":
        return json.dumps({
            "project_code": _extract_field(prompt, "project_code"),
            "contract_no": _extract_field(prompt, "contract_no"),
            "vendor": _extract_field(prompt, "vendor"),
            "date_range": _extract_field(prompt, "date_range"),
            "document_type": _extract_field(prompt, "document_type"),
            "mailbox_scope": _extract_field(prompt, "mailbox_scope"),
            "missing": [],
        })

    if node_name == "node_04_plan":
        return json.dumps({
            "sources": ["sharepoint", "odoo"],
            "reason": "Fallback plan: query project documents and financial data.",
        })

    if node_name == "node_11_self_correct":
        return json.dumps({
            "action": "retry_with_narrowed_query",
            "new_query": _extract_field(prompt, "query") or "",
            "target_sources": ["sharepoint", "odoo"],
        })

    if node_name == "node_12_draft_json":
        # Return a minimal valid report shell
        return json.dumps({
            "request_id": _extract_field(prompt, "request_id") or "",
            "project_code": _extract_field(prompt, "project_code") or None,
            "query": _extract_field(prompt, "query") or "",
            "language": "en",
            "executive_summary": [],
            "financial_snapshot": {
                "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
            },
            "key_findings": [],
            "root_causes": [],
            "delay_analysis": [],
            "contractual_implications": [],
            "recommended_actions": [],
            "management_question_answer": {
                "executive_answer": "",
                "why_biggest_problem": [],
                "evidence_used": [],
                "business_impact": {
                    "schedule_impact": "",
                    "cost_commercial_impact": "",
                    "operational_client_impact": "",
                },
                "decision_required": "",
                "recommended_action": {
                    "specific_action": "",
                    "owner_role": "",
                    "timeframe": "",
                },
                "risks_if_no_action": "",
                "confidence": "low",
                "missing_evidence_or_assumptions": "Fallback mode — no LLM synthesis.",
            },
            "missing_data": ["No evidence available in fallback mode."],
            "conflicts": [],
            "sources": [],
            "quality_gate_status": "not_run",
        })

    if node_name == "node_14_compose_md":
        return "# Executive Decision Report\n\n_Fallback mode — no LLM available._\n"

    # Generic fallback
    if expect_json:
        return json.dumps({"fallback": True, "node": node_name})
    return f"<!-- fallback output for {node_name} -->"


# ---------------------------------------------------------------------------
# Deterministic helpers for fallback mode
# ---------------------------------------------------------------------------
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "budget_actual": ["budget", "actual cost", "cost vs budget", "financial status"],
    "delay": ["delay", "late", "extension of time", "eot", "schedule"],
    "contract_risk": ["contract", "risk", "breach", "terms"],
    "claim": ["claim", "dispute", "penalty"],
    "procurement": ["procurement", "purchase order", "po", "vendor selection"],
    "document_control": ["document", "submittal", "rfi", "drawing"],
    "payment": ["payment", "invoice", "certification"],
    "variation": ["variation", "change order", "scope change"],
}


def _infer_intent_from_query(prompt: str) -> str:
    # Extract only the Query line to avoid matching category names in the prompt template
    query_line = ""
    for line in prompt.splitlines():
        if line.lower().startswith("query:"):
            query_line = line.split(":", 1)[1].strip().lower()
            break
    if not query_line:
        query_line = prompt.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in query_line for kw in keywords):
            return intent
    return "general_project_status"


def _extract_field(prompt: str, field: str) -> str | None:
    """Crude extraction for fallback mode: look for 'field: value' lines."""
    for line in prompt.splitlines():
        lower = line.lower()
        # Handle fields with spaces like "Request ID"
        if lower.startswith(f"{field}:"):
            return line.split(":", 1)[1].strip()
        # Also try spaced variants
        spaced = field.replace("_", " ")
        if lower.startswith(f"{spaced}:"):
            return line.split(":", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_daily_cost() -> float:
    return _cost_tracker.daily_cost


def get_token_usage(request_id: str) -> dict[str, int]:
    return _cost_tracker.get_tokens(request_id)


def reset_daily_cost() -> None:
    """Test helper."""
    _cost_tracker._daily_cost = 0.0  # noqa: SLF001


def reset_token_usage(request_id: str) -> None:
    """Test helper."""
    _cost_tracker._token_usage.pop(request_id, None)  # noqa: SLF001
