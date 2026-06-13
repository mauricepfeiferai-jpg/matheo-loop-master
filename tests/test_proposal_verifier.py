from pathlib import Path

from hecate.proposal_verifier import (
    check_completeness,
    check_duplicate,
    check_hecate_alignment,
    check_safety,
    verify_proposal,
)


def test_check_safety_finds_rm_rf(tmp_path):
    text = "Implementiere rm -rf /root"
    hits = check_safety(text)
    assert len(hits) > 0


def test_check_completeness_flags_missing_sections(tmp_path):
    text = "# Proposal\n\nNur ein Titel."
    missing = check_completeness(text)
    assert len(missing) > 0
    assert any("Zweck" in m for m in missing)


def test_check_completeness_passes_complete(tmp_path):
    text = "# Proposal\n\n## Zweck\nX\n## Implementierung\nY\n## Rollback\nZ"
    assert check_completeness(text) == []


def test_check_hecate_alignment_flags_missing_keywords():
    text = "Eine tolle Idee ohne HECATE-Begriffe."
    assert len(check_hecate_alignment(text)) > 0


def test_check_hecate_alignment_passes_with_ledger():
    text = "Nutzt Ledger und Harness."
    assert check_hecate_alignment(text) == []


def test_check_duplicate_detects_similar(tmp_path):
    proposals_dir = tmp_path / "proposals"
    proposals_dir.mkdir()
    existing = proposals_dir / "fix-disk-space.md"
    existing.write_text("# Fix disk space\nBody")

    hits = check_duplicate("Fix disk space", proposals_dir)
    assert len(hits) > 0


def test_verify_proposal_passes_clean(tmp_path):
    p = tmp_path / "proposal.md"
    p.write_text("""# Fix

## Zweck
Fix disk.

## Implementierung
Run harness.

## Rollback
Remove.

Ledger: yes. Harness: yes. reversibel.
""")
    verdict = verify_proposal(p)
    assert verdict.ok is True


def test_verify_proposal_fails_on_denylist(tmp_path):
    p = tmp_path / "proposal.md"
    p.write_text("""# Bad

## Zweck
X

## Implementierung
rm -rf /

## Rollback
Y
""")
    verdict = verify_proposal(p)
    assert verdict.ok is False
    assert verdict.severity == "krit"
