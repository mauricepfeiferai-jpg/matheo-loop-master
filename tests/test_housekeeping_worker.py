import json
from pathlib import Path
from unittest.mock import patch

from hecate.housekeeping_worker import process_approved_proposals, _set_proposal_status
from hecate.system_housekeeper import Candidate


def test_process_approved_proposals_runs_only_approved(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.housekeeping_worker.PROPOSALS_DIR", tmp_path)
    monkeypatch.setattr("hecate.housekeeping_worker.ARCHIVE_DIR", tmp_path / "archive")

    # Approved proposal
    p1 = tmp_path / "housekeep-safe-old.md"
    p1.write_text(
        "---\nstatus: approved\n---\n"
        "## Aktion\n"
        "archive_to_backup auf /root/projects/loop-master/tests"
    )

    # Pending proposal
    p2 = tmp_path / "housekeep-ask-other.md"
    p2.write_text(
        "---\nstatus: telegram_approval\n---\n"
        "## Aktion\n"
        "delete auf /root/some-big-dir"
    )

    with patch("hecate.housekeeping_worker._candidate_from_proposal") as mock_c:
        mock_c.return_value = Candidate(
            path=str(tmp_path / "dummy"),
            size_bytes=1024,
            age_days=10,
            category="old_backup",
            reason="old",
            risk_class="safe_archive",
            action="archive_to_backup",
            confidence=0.8,
            evidence="safe",
        )
        with patch("hecate.housekeeping_worker.execute_candidate") as mock_exec:
            mock_exec.return_value = {"ok": True, "rid": "x", "note": "archived"}
            with patch("hecate.housekeeping_worker.verify_candidate") as mock_ver:
                mock_ver.return_value = {"ok": True}
                results = process_approved_proposals(dry_run=False)

    assert len(results) == 1
    assert results[0]["proposal"] == "housekeep-safe-old"


def test_set_proposal_status_updates_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.housekeeping_worker.PROPOSALS_DIR", tmp_path)
    p = tmp_path / "test.md"
    p.write_text("---\nstatus: vorgeschlagen\n---\nbody")
    _set_proposal_status("test", "approved")
    assert "status: approved" in p.read_text()
