from sensors.secret_scan import scan_env_files, scan_file


def test_telegram_token_detected_value_suppressed(tmp_path):
    f = tmp_path / ".env"
    f.write_text("TELEGRAM_BOT_TOKEN=123456789:AAabcdefghijklmnopqrstuvwxyz0123456\n")
    hits = scan_file(f)
    assert hits == [("TELEGRAM_BOT_TOKEN", "telegram")]


def test_value_never_in_finding(tmp_path):
    f = tmp_path / ".env"
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    f.write_text(f"ANTHROPIC_API_KEY={secret}\n")
    fnds = scan_env_files(tmp_path)
    assert len(fnds) == 1
    assert secret not in fnds[0].evidence
    assert "ANTHROPIC_API_KEY" in fnds[0].evidence


def test_example_files_skipped(tmp_path):
    f = tmp_path / ".env.example"
    f.write_text("TELEGRAM_BOT_TOKEN=123456789:AAabcdefghijklmnopqrstuvwxyz0123456\n")
    assert scan_env_files(tmp_path) == []


def test_clean_file_silent(tmp_path):
    f = tmp_path / ".env"
    f.write_text("DEBUG=true\nPORT=8080\n")
    assert scan_env_files(tmp_path) == []
