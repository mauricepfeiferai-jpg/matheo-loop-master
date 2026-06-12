import json

from safety.harness import SafeAction, run


def test_success_commits_and_audits(tmp_path):
    flag = tmp_path / "done.txt"
    audit = tmp_path / "audit.jsonl"
    action = SafeAction(
        id="touch-flag",
        do_cmd=f"touch {flag}",
        undo_cmd=f"rm -f {flag}",
        verify_cmd=f"test -f {flag}",
        snapshot_files=[],
        audit_path=str(audit),
    )
    result = run(action)
    assert result.ok is True
    assert result.rolled_back is False
    assert flag.exists()
    entry = json.loads(audit.read_text().strip().splitlines()[-1])
    assert entry["id"] == "touch-flag"
    assert entry["outcome"] == "success"


def test_rollback_restores_snapshot_on_verify_fail(tmp_path):
    target = tmp_path / "config.conf"
    target.write_text("ORIGINAL")
    audit = tmp_path / "audit.jsonl"
    # do_cmd verschlechtert die Datei; verify_cmd schlaegt fehl -> muss zuruckrollen
    action = SafeAction(
        id="bad-edit",
        do_cmd=f"echo BROKEN > {target}",
        undo_cmd="true",
        verify_cmd="false",                      # Health immer schlecht
        snapshot_files=[str(target)],
        audit_path=str(audit),
    )
    result = run(action)
    assert result.ok is False
    assert result.rolled_back is True
    assert target.read_text().strip() == "ORIGINAL"   # Snapshot wiederhergestellt


def test_denied_action_never_runs(tmp_path):
    victim = tmp_path / "keep.txt"
    victim.write_text("SAFE")
    audit = tmp_path / "audit.jsonl"
    action = SafeAction(
        id="evil",
        do_cmd=f"rm -rf {victim}",                # Deny-List muss blocken
        undo_cmd="true",
        verify_cmd="true",
        snapshot_files=[],
        audit_path=str(audit),
    )
    result = run(action)
    assert result.ok is False
    assert result.denied is not None
    assert victim.exists()                         # nie ausgefuehrt
