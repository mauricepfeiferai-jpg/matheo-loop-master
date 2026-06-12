from sensors.cron_verify import check_entries, parse_cron_text


def test_crond_missing_user_field_is_krit(tmp_path):
    txt = "0 8 * * * /usr/bin/python3 /root/x.py >> /root/logs/x.log 2>&1\n"
    entries = parse_cron_text(txt, source="/etc/cron.d/broken", needs_user=True)
    fnds = check_entries(entries)
    assert any(f.f_class == "cron.bad-user-field" and f.severity == "krit" for f in fnds)


def test_paused_marker_is_skipped():
    txt = "# [PAUSED 2026-06-09 akut; revert: uncomment] 0 5 * * * root python3 /x.py\n"
    assert parse_cron_text(txt, source="t", needs_user=True) == []


def test_missing_interpreter_script_is_hoch(tmp_path):
    txt = f"0 8 * * * root /usr/bin/python3 {tmp_path}/missing.py >> {tmp_path}/log.log 2>&1\n"
    fnds = check_entries(parse_cron_text(txt, source="t", needs_user=True))
    assert any(f.f_class == "cron.target-missing" and f.severity == "hoch" for f in fnds)


def test_missing_redirect_dir_is_hoch(tmp_path):
    script = tmp_path / "ok.sh"
    script.write_text("#!/bin/sh\n")
    txt = f"0 18 * * * root {script} >> {tmp_path}/nodir/cron.log 2>&1\n"
    fnds = check_entries(parse_cron_text(txt, source="t", needs_user=True))
    assert any(f.f_class == "cron.redirect-dir-missing" for f in fnds)


def test_valid_entry_is_silent(tmp_path):
    script = tmp_path / "ok.sh"
    script.write_text("#!/bin/sh\n")
    log = tmp_path / "log"
    log.mkdir()
    txt = f"*/5 * * * * root {script} >> {log}/o.log 2>&1\n"
    assert check_entries(parse_cron_text(txt, source="t", needs_user=True)) == []
