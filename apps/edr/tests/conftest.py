"""Shared test fixtures.

Pin the generation-provider switch to its default so the suite is
deterministic regardless of what LLM_PROVIDER says in the live ``.env``.
The pre-switch tests assert provider states against the anthropic default;
provider-switch tests opt in to deepseek explicitly via monkeypatch.
"""

from __future__ import annotations

import pytest

from apps.edr.config import settings


@pytest.fixture(autouse=True)
def _default_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
