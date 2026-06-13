import sqlite3

from hecate.discussion_memory import DiscussionMemory, Message


def test_create_and_retrieve(tmp_path):
    db = tmp_path / "disc.db"
    mem = DiscussionMemory(db_path=db)
    disc = mem.get_or_create("prop-001")
    assert disc["proposal_id"] == "prop-001"
    assert disc["status"] == "open"
    assert disc["messages"] == []


def test_add_message_and_context(tmp_path):
    db = tmp_path / "disc.db"
    mem = DiscussionMemory(db_path=db)
    mem.add_message("prop-001", "user", "Sollten wir das machen?")
    mem.add_message("prop-001", "hecate", "Ja, aber mit Rollback.")
    ctx = mem.get_context("prop-001")
    assert "Maurice: Sollten wir das machen?" in ctx
    assert "HECATE: Ja, aber mit Rollback." in ctx


def test_status_lifecycle(tmp_path):
    db = tmp_path / "disc.db"
    mem = DiscussionMemory(db_path=db)
    mem.set_status("prop-001", "plan_only")
    disc = mem.get_or_create("prop-001")
    assert disc["status"] == "plan_only"


def test_list_open(tmp_path):
    db = tmp_path / "disc.db"
    mem = DiscussionMemory(db_path=db)
    mem.add_message("prop-001", "user", "a")
    mem.add_message("prop-002", "user", "b")
    mem.set_status("prop-001", "approved")
    open_ = mem.list_open()
    assert len(open_) == 1
    assert open_[0]["proposal_id"] == "prop-002"


def test_invalid_status_rejected(tmp_path):
    db = tmp_path / "disc.db"
    mem = DiscussionMemory(db_path=db)
    try:
        mem.set_status("prop-001", "invalid")
        assert False, "sollte AssertionError werfen"
    except AssertionError:
        pass
