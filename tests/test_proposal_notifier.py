import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from hecate.proposal_notifier import pending_approval_proposals


def test_pending_approval_proposals_finds_only_telegram_approval(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.proposal_notifier.PROPOSALS_DIR", tmp_path)

    p1 = tmp_path / "housekeep-ask-disk.md"
    p1.write_text("---\nstatus: telegram_approval\n---\nFreigabe erforderlich: delete /tmp/old")

    p2 = tmp_path / "other.md"
    p2.write_text("---\nstatus: vorgeschlagen\n---\nno approval needed")

    found = pending_approval_proposals()
    assert len(found) == 1
    assert found[0][0] == "housekeep-ask-disk"


def test_notify_pending_sends_one_batch_and_logs(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.proposal_notifier.PROPOSALS_DIR", tmp_path)
    monkeypatch.setattr("hecate.proposal_notifier.SENT_LOG", tmp_path / "sent.jsonl")

    for i in range(7):
        p = tmp_path / f"housekeep-ask-test{i}.md"
        p.write_text(
            f"---\nstatus: telegram_approval\n---\n"
            f"Freigabe erforderlich: archive_to_backup auf /root/old{i}\n"
            f"**Kategorie:** deprecated\n"
            f"**Grösse:** {i+1}.5 GB\n"
            f"**Begründung:** older than threshold"
        )

    with patch("hecate.proposal_notifier.send_message") as mock_send:
        from hecate.hermes_adapter import HermesResult
        mock_send.return_value = HermesResult(ok=True, stdout="sent", returncode=0)
        from hecate import proposal_notifier as pn
        ids = pn.notify_pending()

    assert len(ids) == 7
    assert mock_send.call_count == 1
    sent_text = mock_send.call_args[0][1]
    assert "Top" in sent_text
    assert "approve-all" in sent_text
    assert (tmp_path / "sent.jsonl").exists()


def test_notify_pending_respects_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.proposal_notifier.PROPOSALS_DIR", tmp_path)
    sent_log = tmp_path / "sent.jsonl"
    monkeypatch.setattr("hecate.proposal_notifier.SENT_LOG", sent_log)
    sent_log.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "proposal_ids": ["x"], "count": 1}) + "\n")

    p = tmp_path / "housekeep-ask-now.md"
    p.write_text("---\nstatus: telegram_approval\n---\n**Grösse:** 9 GB\n**Kategorie:** deprecated")

    with patch("hecate.proposal_notifier.send_message") as mock_send:
        from hecate import proposal_notifier as pn
        ids = pn.notify_pending()

    assert len(ids) == 0
    assert not mock_send.called
