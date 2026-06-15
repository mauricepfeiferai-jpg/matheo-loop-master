"""Tests for HECATE agent smoke commands.

Verifies that smoke commands produce reports and that Policy Guard evaluates
proposed actions correctly. These are read-only tests.
"""
from __future__ import annotations

from pathlib import Path

from hecate.agent_smoke import (
    evaluate_policy_guard,
    run_builder,
    run_digest,
    run_operator,
    run_policy_guard,
    run_reviewer,
)


def test_operator_produces_report(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.agent_smoke.REPORTS_DIR", tmp_path)
    path = run_operator()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "# HECATE Operator Report" in text
    assert "## Health" in text


def test_digest_produces_report(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.agent_smoke.REPORTS_DIR", tmp_path)
    # Create a fake operator report.
    op = tmp_path / "operator_report_fake.md"
    op.write_text("# HECATE Operator Report\n\n## Risks\n- **P1** | disk: / at 95%\n", encoding="utf-8")
    path = run_digest(op)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "# HECATE Digest" in text
    assert "REQUIRES_MAURICE_GO" in text


def test_policy_guard_denies_destructive_commands():
    verdict = evaluate_policy_guard("rm -rf /root/projects/loop-master")
    assert verdict["verdict"] == "DENY"


def test_policy_guard_requires_go_for_systemctl():
    verdict = evaluate_policy_guard("systemctl restart codex-bridge")
    assert verdict["verdict"] == "REQUIRE_MAURICE_GO"


def test_policy_guard_allows_safe_readonly():
    verdict = evaluate_policy_guard("tmux list-sessions")
    assert verdict["verdict"] == "ALLOW"


def test_policy_guard_produces_verdict_report(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.agent_smoke.REPORTS_DIR", tmp_path)
    digest = tmp_path / "digest_fake.md"
    digest.write_text("# Digest\n\n- **P1** | disk: systemctl restart foo\n", encoding="utf-8")
    path = run_policy_guard(digest)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "# HECATE Policy Guard Verdict" in text


def test_builder_produces_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.agent_smoke.PROPOSALS_DIR", tmp_path)
    path = run_builder("add small test")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Builder Smoke Proposal" in text
    assert "PROPOSAL_ONLY" in text


def test_reviewer_produces_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.agent_smoke.REPORTS_DIR", tmp_path)
    path = run_reviewer(["foo.py"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Reviewer Smoke Verdict" in text
    assert "YELLOW" in text
