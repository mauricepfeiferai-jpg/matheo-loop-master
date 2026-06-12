from safety.denylist import is_denied


def test_rm_rf_outside_trash_is_denied():
    assert is_denied("rm -rf /var/log/old") is not None


def test_rm_rf_inside_trash_is_allowed():
    assert is_denied("rm -rf /root/_trash/junk") is None


def test_git_force_push_denied():
    assert is_denied("git push --force origin main") is not None


def test_git_reset_hard_denied():
    assert is_denied("git reset --hard HEAD~3") is not None


def test_apt_denied():
    assert is_denied("apt-get remove python3") is not None


def test_legal_path_move_denied():
    assert is_denied("mv /root/vault/brain/legal/akte.md /tmp/") is not None


def test_harmless_restart_allowed():
    assert is_denied("systemctl restart ollama") is None
