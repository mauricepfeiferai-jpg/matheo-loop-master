from pathlib import Path
from unittest.mock import patch

from hecate.system_housekeeper import Candidate, classify_candidate


def test_classify_docker_is_safe_delete():
    c = Candidate(path="docker:images", size_bytes=10**9, age_days=0,
                  category="docker", reason="Docker reclaimable 5 GB")
    classified = classify_candidate(None, c)
    assert classified.risk_class == "safe_delete"
    assert classified.action == "docker_prune"


def test_classify_old_backup_is_safe_archive():
    c = Candidate(path="/root/_backups/foo", size_bytes=10**9, age_days=10,
                  category="old_backup", reason="older than 3 days")
    with patch("hecate.system_housekeeper._is_active_project", return_value=False):
        classified = classify_candidate(None, c)
    assert classified.risk_class == "safe_archive"
    assert classified.action == "archive_to_backup"


def test_classify_active_project_requires_approval():
    c = Candidate(path="/root/openclaw", size_bytes=10**9, age_days=90,
                  category="deprecated", reason="old")
    with patch("hecate.system_housekeeper._is_active_project", return_value=True):
        classified = classify_candidate(None, c)
    assert classified.risk_class == "ask_maurice"
    assert classified.action == "ask"


def test_classify_vault_requires_approval():
    c = Candidate(path="/root/vault/brain", size_bytes=10**10, age_days=30,
                  category="large_dir", reason="big dir")
    classified = classify_candidate(None, c)
    assert classified.risk_class == "ask_maurice"
    assert classified.action == "ask"


def test_scan_all_patches_all_scanners(tmp_path, monkeypatch):
    monkeypatch.setattr("hecate.system_housekeeper.REPORT_DIR", tmp_path)
    monkeypatch.setattr("hecate.system_housekeeper.CANDIDATES_PATH", tmp_path / "candidates.jsonl")

    big = tmp_path / "scanme" / "large.bin"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"x" * (1024**2))

    fake = [Candidate(str(big), big.stat().st_size, 0, "large_file", "test")]
    with patch.multiple(
        "hecate.system_housekeeper",
        scan_large_dirs=lambda **kw: fake,
        scan_logs=lambda **kw: [],
        scan_docker_reclaimable=lambda: [],
        scan_old_backups=lambda **kw: [],
        scan_deprecated_dirs=lambda: [],
    ):
        from hecate import system_housekeeper as sh
        items = sh.scan_all()
        assert len(items) == 1
        assert (tmp_path / "candidates.jsonl").exists()
