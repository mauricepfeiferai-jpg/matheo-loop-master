from sensors.restart_loops import detect_loops


def test_active_looper_is_krit():
    prev = {"empire.service": {"ts": 0.0, "nrestarts": 101481}}
    curr = {"empire.service": {"ts": 3600.0, "nrestarts": 102124}}  # 643/h
    fnds = detect_loops(prev, curr, min_rate_per_h=10)
    assert len(fnds) == 1
    assert fnds[0].severity == "krit"
    assert "643" in fnds[0].evidence


def test_high_absolute_but_stable_is_silent():
    prev = {"gpe-synapse-bridge.service": {"ts": 0.0, "nrestarts": 12823}}
    curr = {"gpe-synapse-bridge.service": {"ts": 3600.0, "nrestarts": 12823}}
    assert detect_loops(prev, curr, min_rate_per_h=10) == []


def test_new_unit_without_prev_is_silent():
    assert detect_loops({}, {"new.service": {"ts": 60.0, "nrestarts": 5}}, min_rate_per_h=10) == []


def test_success_looper_is_info_antipattern():
    # tailscale-watchdog-Fall: Restart=always als Timer missbraucht, Exit 0
    prev = {"tailscale-watchdog.service": {"ts": 0.0, "nrestarts": 65210, "result": "success"}}
    curr = {"tailscale-watchdog.service": {"ts": 3600.0, "nrestarts": 65267, "result": "success"}}
    fnds = detect_loops(prev, curr, min_rate_per_h=10)
    assert len(fnds) == 1
    assert fnds[0].severity == "info"
    assert fnds[0].f_class == "restart.timer-antipattern"
