"""Tests for HECATE model routing policy.

Ensures local-first routing, no-cloud zones, and cloud fallback rules.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

GOVERNANCE_DIR = Path(__file__).parent.parent / "governance"
ROUTING_PATH = GOVERNANCE_DIR / "local_model_routing.yaml"
FALLBACK_PATH = GOVERNANCE_DIR / "cloud_fallback_policy.yaml"


@pytest.fixture
def routing():
    return yaml.safe_load(ROUTING_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def fallback():
    return yaml.safe_load(FALLBACK_PATH.read_text(encoding="utf-8"))


def test_routing_file_exists():
    assert ROUTING_PATH.exists()


def test_default_chain_starts_local(routing):
    assert routing["default"][0] == "rules_first"
    assert "local_small" in routing["default"] or "local_medium" in routing["default"]


def test_classify_route_is_no_cloud(routing):
    route = routing["routes"]["classify"]
    assert route["no_cloud"] is True
    assert "rules_first" in route["backends"]


def test_safety_check_is_no_cloud(routing):
    route = routing["routes"]["safety_check"]
    assert route["no_cloud"] is True


def test_embed_route_is_no_cloud(routing):
    route = routing["routes"]["embed"]
    assert route["no_cloud"] is True
    assert len(route["backends"]) == 1


def test_claude_chatgpt_requires_approval(routing):
    claude = routing["backends"]["claude_chatgpt"]
    assert claude["requires_approval"] == "maurice_go"


def test_codex_bridge_requires_approval(routing):
    codex = routing["backends"]["codex_bridge"]
    assert codex["requires_approval"] == "maurice_go"


def test_fallback_policy_exists():
    assert FALLBACK_PATH.exists()


def test_cloud_models_require_explicit_go(fallback):
    assert fallback["enabled"]["codex_bridge"] is False
    assert fallback["enabled"]["claude_chatgpt"] is False


def test_no_cloud_zones_include_secrets_and_legal(fallback):
    zones = fallback["no_cloud_zones"]
    for required in [
        "secrets",
        "api_keys",
        "tokens",
        "raw_legal_evidence",
        "live_trading_credentials_or_instructions",
        "ssh_keys",
        "/root/.secrets",
        "/root/.ssh",
    ]:
        assert required in zones, f"Missing no-cloud zone: {required}"


def test_forbidden_patterns_cover_common_secrets(fallback):
    patterns = fallback["forbidden_patterns"]
    text = "\n".join(patterns)
    assert "api" in text.lower() or "key" in text.lower()
    assert "sk-" in text
    assert "BEGIN" in text


def test_cloud_use_is_audited(fallback):
    assert fallback["audit"]["log_all_cloud_use"] is True
    assert fallback["audit"]["log_reason"] is True
