"""LLM provider runtime switch (LLM_PROVIDER) integration tests.

Covers:
- provider resolution, with fallback to anthropic for unknown values
- DeepSeek active with a key: the real HTTP chat-completions path is used
  (mock transport observes the request) — NOT the deterministic fallback
- DeepSeek active without a key: deterministic fallback preserved
- connector truth: the inactive generation provider is DISABLED and never
  blocks go-live; report-generation status follows the active provider;
  Voyage and Cohere are unaffected by the switch
- markdown code-fence stripping for expect_json calls (DeepSeek wraps JSON
  answers in ```json fences, which broke json.loads in the graph nodes)
"""

from __future__ import annotations

import json

import httpx
import pytest

import apps.edr.admin.connector_status as cs
from apps.edr import llm
from apps.edr.config import settings


@pytest.fixture()
def deepseek_active(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(settings, "llm_provider", "deepseek", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", None, raising=False)
    return monkeypatch


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------


def test_active_provider_defaults_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    assert llm.active_provider() == "anthropic"


def test_active_provider_unknown_value_falls_back_to_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_provider", "not-a-provider", raising=False)
    assert llm.active_provider() == "anthropic"


def test_active_provider_deepseek(deepseek_active: pytest.MonkeyPatch) -> None:
    assert llm.active_provider() == "deepseek"


# ---------------------------------------------------------------------------
# call_llm routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_without_key_uses_deterministic_fallback(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    llm.reset_daily_cost()
    result = await llm.call_llm(
        prompt="Query: budget vs actual",
        tier="light",
        request_id="r-ds-fallback",
        node_name="node_02_intent",
        expect_json=True,
    )
    assert result.model == llm._DEEPSEEK_LIGHT_MODEL
    assert json.loads(result.content) == {"intents": ["budget_actual"]}


@pytest.mark.asyncio
async def test_deepseek_with_key_calls_http_api_not_fallback(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    llm.reset_daily_cost()
    deepseek_active.setattr(settings, "deepseek_api_key", "test-key-not-real", raising=False)

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth_present"] = bool(request.headers.get("authorization"))
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {"message": {"role": "assistant", "content": '{"intents": ["delay"]}'}}
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 7},
            },
        )

    real_async_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    deepseek_active.setattr(llm.httpx, "AsyncClient", client_with_mock_transport)

    result = await llm.call_llm(
        prompt="Query: why is the project late?",
        tier="light",
        request_id="r-ds-live",
        node_name="node_02_intent",
        expect_json=True,
    )

    assert seen["path"] == "/chat/completions"
    assert seen["auth_present"] is True
    assert seen["payload"]["model"] == llm._DEEPSEEK_LIGHT_MODEL
    # The HTTP response body is returned verbatim — proof the deterministic
    # fallback was NOT used (the fallback would classify this as "delay" via
    # keywords, but could never echo the exact usage figures below).
    assert json.loads(result.content) == {"intents": ["delay"]}
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    assert result.model == llm._DEEPSEEK_LIGHT_MODEL
    assert result.cost_usd > 0


@pytest.mark.asyncio
async def test_anthropic_default_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    # No anthropic key → deterministic fallback with the locked Anthropic
    # model id, exactly as before the switch existed.
    llm.reset_daily_cost()
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)
    result = await llm.call_llm(
        prompt="Query: budget",
        tier="light",
        request_id="r-ant-fallback",
        node_name="node_02_intent",
        expect_json=True,
    )
    assert result.model == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Connector truth under the switch
# ---------------------------------------------------------------------------


def test_inactive_anthropic_is_disabled_and_never_blocks(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["anthropic"], run_probe=False)
    assert truth.state is cs.ConnectorState.DISABLED
    assert truth.blocks_go_live is False
    assert "switch selects deepseek" in truth.evidence


def test_inactive_deepseek_is_disabled_under_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["deepseek"], run_probe=False)
    assert truth.state is cs.ConnectorState.DISABLED
    assert truth.blocks_go_live is False


def test_active_deepseek_without_key_blocks_report_generation(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    report = cs.build_report(run_probes=False)
    assert report.report_generation == "BLOCKED"
    assert "DEEPSEEK_API_KEY" in report.report_generation_reason
    truths = {t.name: t for t in report.ai_providers}
    assert truths["deepseek"].state is cs.ConnectorState.NOT_CONFIGURED
    assert truths["deepseek"].blocks_go_live is True
    assert truths["anthropic"].state is cs.ConnectorState.DISABLED
    assert truths["anthropic"].blocks_go_live is False


def test_active_deepseek_with_key_is_ready_without_anthropic_key(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    deepseek_active.setattr(settings, "deepseek_api_key", "test-key-not-real", raising=False)
    deepseek_active.setattr(settings, "anthropic_api_key", None, raising=False)
    deepseek_active.setattr(settings, "voyage_api_key", "test-voyage-key", raising=False)
    deepseek_active.setattr(settings, "cohere_api_key", "test-cohere-key", raising=False)
    report = cs.build_report(run_probes=False)
    assert report.report_generation == "READY"
    truths = {t.name: t for t in report.ai_providers}
    # Key presence alone never claims liveness — capped at CONFIGURED_NOT_TESTED.
    assert truths["deepseek"].state is cs.ConnectorState.CONFIGURED_NOT_TESTED


def test_voyage_and_cohere_unaffected_by_provider_switch(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    for name in ("voyage", "cohere"):
        truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME[name], run_probe=False)
        assert truth.state is not cs.ConnectorState.DISABLED


# ---------------------------------------------------------------------------
# Markdown code-fence stripping (live DeepSeek wraps JSON in ```json fences)
# ---------------------------------------------------------------------------


def test_strip_code_fences_variants() -> None:
    assert llm.strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert llm.strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'
    assert llm.strip_code_fences('  ```json\n{"a": 1}\n```  \n') == '{"a": 1}'
    # Unfenced and empty content pass through untouched.
    assert llm.strip_code_fences('{"a": 1}') == '{"a": 1}'
    assert llm.strip_code_fences("") == ""
    # Inner fences inside prose are NOT stripped — only one outer fence is.
    prose = 'see ```json\n{"a": 1}\n``` above'
    assert llm.strip_code_fences(prose) == prose


def _fenced_response_handler(seen: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '```json\n{"intents": ["delay"]}\n```',
                        }
                    }
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 7},
            },
        )

    return handler


@pytest.mark.asyncio
async def test_expect_json_strips_deepseek_markdown_fences(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    # Live DeepSeek wraps JSON answers in markdown fences even when asked for
    # raw JSON; without stripping, json.loads fails in every graph node and
    # reports silently fall back to the deterministic evidence-builder
    # (observed live on 2026-06-12).
    llm.reset_daily_cost()
    deepseek_active.setattr(settings, "deepseek_api_key", "test-key-not-real", raising=False)

    seen: dict = {}
    real_async_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_fenced_response_handler(seen))
        return real_async_client(*args, **kwargs)

    deepseek_active.setattr(llm.httpx, "AsyncClient", client_with_mock_transport)

    result = await llm.call_llm(
        prompt="Query: why is the project late?",
        tier="light",
        request_id="r-ds-fenced",
        node_name="node_02_intent",
        expect_json=True,
    )

    assert json.loads(result.content) == {"intents": ["delay"]}
    assert result.input_tokens == 42
    assert result.output_tokens == 7


@pytest.mark.asyncio
async def test_expect_json_false_leaves_fences_untouched(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    # Markdown output (e.g. node_14_compose_md) must keep code fences intact.
    llm.reset_daily_cost()
    deepseek_active.setattr(settings, "deepseek_api_key", "test-key-not-real", raising=False)

    seen: dict = {}
    real_async_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_fenced_response_handler(seen))
        return real_async_client(*args, **kwargs)

    deepseek_active.setattr(llm.httpx, "AsyncClient", client_with_mock_transport)

    result = await llm.call_llm(
        prompt="Compose the markdown report.",
        tier="light",
        request_id="r-ds-md",
        node_name="node_14_compose_md",
        expect_json=False,
    )

    assert result.content == '```json\n{"intents": ["delay"]}\n```'


# ---------------------------------------------------------------------------
# DeepSeek model-name resolution (live HTTP 400: tier string sent as model)
# ---------------------------------------------------------------------------


def test_deepseek_tiers_resolve_to_valid_api_models() -> None:
    assert llm._resolve_model_and_caps("deepseek", "light")[0] == "deepseek-v4-flash"
    assert llm._resolve_model_and_caps("deepseek", "heavy")[0] == "deepseek-v4-pro"


def test_deepseek_unknown_tier_never_forwarded_as_model_name() -> None:
    # A deployed call with tier="standard" was rejected by the live API with
    # HTTP 400 because the tier string itself was sent as the model name.
    for tier in ("standard", "advanced", "report", "", "not-a-tier"):
        model, caps = llm._resolve_model_and_caps("deepseek", tier)
        assert model == "deepseek-v4-flash", tier
        assert model != tier
        assert caps == llm._DEEPSEEK_TIER_CAPS["heavy"]


@pytest.mark.asyncio
async def test_deepseek_standard_tier_sends_default_model_over_http(
    deepseek_active: pytest.MonkeyPatch,
) -> None:
    llm.reset_daily_cost()
    deepseek_active.setattr(settings, "deepseek_api_key", "test-key-not-real", raising=False)

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {"message": {"role": "assistant", "content": '{"ok": true}'}}
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )

    real_async_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    deepseek_active.setattr(llm.httpx, "AsyncClient", client_with_mock_transport)

    result = await llm.call_llm(
        prompt="Query: status",
        tier="standard",
        request_id="r-ds-standard",
        node_name="uat_standard_tier",
        expect_json=True,
    )

    assert seen["payload"]["model"] == "deepseek-v4-flash"
    assert result.model == "deepseek-v4-flash"
    assert result.input_tokens == 11
    assert result.output_tokens == 3
