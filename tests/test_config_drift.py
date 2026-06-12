from sensors.config_drift import find_env_conflicts, parse_unit_env

OLLAMA_CAT = """\
# /etc/systemd/system/ollama.service
[Service]
Environment="OLLAMA_NUM_CTX=4096"

# /etc/systemd/system/ollama.service.d/override-host.conf
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"

# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_NUM_CTX=4096"
Environment="OLLAMA_HOST=127.0.0.1"
"""


def test_parse_collects_sources():
    env = parse_unit_env(OLLAMA_CAT)
    assert len(env["OLLAMA_HOST"]) == 2
    assert env["OLLAMA_HOST"][0] == ("0.0.0.0:11434", "/etc/systemd/system/ollama.service.d/override-host.conf")


def test_conflict_different_values_is_hoch():
    fnds = find_env_conflicts("ollama.service", parse_unit_env(OLLAMA_CAT))
    conflict = [f for f in fnds if f.f_class == "config-drift.env-conflict"]
    assert len(conflict) == 1
    assert conflict[0].severity == "hoch"
    assert "OLLAMA_HOST" in conflict[0].evidence


def test_duplicate_same_value_is_info():
    fnds = find_env_conflicts("ollama.service", parse_unit_env(OLLAMA_CAT))
    dup = [f for f in fnds if f.f_class == "config-drift.env-duplicate"]
    assert len(dup) == 1
    assert dup[0].severity == "info"
    assert "OLLAMA_NUM_CTX" in dup[0].evidence
