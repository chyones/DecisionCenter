"""Shared test fixtures.

Pin runtime feature switches to their *code defaults* so the suite is
deterministic regardless of what the live ``.env`` says. The live ``.env`` on the
deployment host enables some operator opt-ins (e.g. ``LLM_PROVIDER=deepseek``,
``ODOO_EXTENDED_SOURCES_ENABLED=true``); without this isolation those leak into
unit tests and flip behaviour (e.g. node_08's query order), causing spurious
full-suite failures. Tests that exercise an opt-in set the flag explicitly via
monkeypatch, which overrides these autouse defaults.
"""

from __future__ import annotations

import pytest

from apps.edr.config import settings


@pytest.fixture(autouse=True)
def _default_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)


@pytest.fixture(autouse=True)
def _default_runtime_feature_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate Odoo opt-in flags from the host ``.env`` (default: off)."""
    monkeypatch.setattr(settings, "odoo_extended_sources_enabled", False, raising=False)
    monkeypatch.setattr(settings, "odoo_extended_include_medium", True, raising=False)
