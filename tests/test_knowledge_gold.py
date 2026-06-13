import json
import sqlite3
from pathlib import Path

import pytest

from hecate import knowledge_gold as kg


def _make_blackhole_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT,
            subtype TEXT,
            source TEXT,
            content TEXT,
            gold_score REAL,
            business_relevance REAL,
            reusability REAL,
            created TEXT,
            metadata TEXT,
            name TEXT,
            leverage REAL,
            novelty REAL,
            legal_weight REAL,
            updated TEXT
        )
    """)


def _insert_item(conn: sqlite3.Connection, **kwargs) -> None:
    defaults = {
        "id": "i1",
        "type": "capability",
        "subtype": None,
        "source": "/tmp/file.md",
        "content": "Inhalt",
        "gold_score": 0.8,
        "business_relevance": 0.5,
        "reusability": 0.5,
        "name": "Titel",
        "leverage": 0.5,
        "novelty": 0.5,
        "legal_weight": 0.0,
    }
    defaults.update(kwargs)
    conn.execute("""
        INSERT INTO items (id, type, subtype, source, content, gold_score,
            business_relevance, reusability, name, leverage, novelty, legal_weight)
        VALUES (:id, :type, :subtype, :source, :content, :gold_score,
            :business_relevance, :reusability, :name, :leverage, :novelty, :legal_weight)
    """, defaults)
    conn.commit()


def test_is_clean_source_requires_existing_path(tmp_path):
    missing = tmp_path / "nix.md"
    assert kg._is_clean_source(str(missing)) is False
    real = tmp_path / "ok.md"
    real.write_text("x")
    assert kg._is_clean_source(str(real)) is True


def test_is_clean_source_rejects_denylisted_paths():
    assert kg._is_clean_source("/root/ARCHIV/old_data/x.md") is False
    assert kg._is_clean_source("/root/_trash/x.md") is False
    assert kg._is_clean_source("/root/.git_QUARANTINED_2026/x.md") is False


def test_clean_name_extracts_basename_for_file_paths():
    assert kg._clean_name("file:/root/foo/BAR.md") == "BAR.md"
    assert kg._clean_name("  Titel  ") == "Titel"
    assert kg._clean_name("") is None
    assert kg._clean_name("x") is None


def test_sync_keeps_only_gold_items(tmp_path, monkeypatch):
    blackhole = tmp_path / "blackhole.db"
    gold = tmp_path / "gold.db"

    real_good = tmp_path / "good.md"
    real_good.write_text("# Guter Inhalt")
    real_archiv = tmp_path / "ARCHIV" / "old_data" / "bad.md"
    real_archiv.parent.mkdir(parents=True)
    real_archiv.write_text("alt")
    missing_file = tmp_path / "missing.md"  # existiert nicht -> bad_source

    long_content = "x" * 600  # erfuellt MIN_CONTENT_LENGTH

    conn = sqlite3.connect(str(blackhole))
    _make_blackhole_schema(conn)
    _insert_item(conn, id="g1", source=str(real_good), name="Gold Item", content=long_content, gold_score=0.85, type="capability")
    _insert_item(conn, id="b1", source=str(real_archiv), name="Alt", content=long_content, gold_score=0.85, type="capability")
    _insert_item(conn, id="b2", source=str(real_good), name="Low", content=long_content, gold_score=0.5, type="capability")
    _insert_item(conn, id="b3", source=str(real_good), name="Wrong", content="short", gold_score=0.85, type="symbol")
    _insert_item(conn, id="b4", source=str(missing_file), name="NoFile", content=long_content, gold_score=0.85, type="skill")
    conn.close()

    stats = kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)
    assert stats["total_blackhole"] == 5
    assert stats["gold_kept"] == 1
    assert stats["rejected"]["bad_source"] == 2
    assert stats["rejected"]["low_score"] == 1
    assert stats["rejected"]["empty_content"] == 1

    # Gold-DB pruefen
    gconn = sqlite3.connect(str(gold))
    gconn.row_factory = sqlite3.Row
    rows = gconn.execute("SELECT * FROM knowledge_gold").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == "g1"
    gconn.close()


def test_query_gold_searches_name_and_content(tmp_path, monkeypatch):
    blackhole = tmp_path / "blackhole.db"
    gold = tmp_path / "gold.db"
    real = tmp_path / "doc.md"
    real.write_text("x")
    long = "x" * 600

    conn = sqlite3.connect(str(blackhole))
    _make_blackhole_schema(conn)
    _insert_item(conn, id="q1", source=str(real), name="Local Model Serving", content=f"Ollama setup. {long}", gold_score=0.9, type="capability")
    _insert_item(conn, id="q2", source=str(real), name="Unrelated", content=f"Something else. {long}", gold_score=0.9, type="capability")
    conn.close()

    kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)
    results = kg.query_gold(topic="Ollama", gold_db_path=gold)
    assert len(results) == 1
    assert results[0]["id"] == "q1"

    results = kg.query_gold(topic="Local Model", gold_db_path=gold)
    assert len(results) == 1


def test_query_gold_respects_type_filter(tmp_path, monkeypatch):
    blackhole = tmp_path / "blackhole.db"
    gold = tmp_path / "gold.db"
    real_cap = tmp_path / "cap.md"
    real_cap.write_text("x")
    real_skill = tmp_path / "skill.md"
    real_skill.write_text("x")
    long = "x" * 600

    conn = sqlite3.connect(str(blackhole))
    _make_blackhole_schema(conn)
    _insert_item(conn, id="c1", source=str(real_cap), name="Capability", content=long, gold_score=0.9, type="capability")
    _insert_item(conn, id="s1", source=str(real_skill), name="Skill", content=long, gold_score=0.9, type="skill")
    conn.close()

    kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)
    assert len(kg.query_gold(type_filter="capability", gold_db_path=gold)) == 1
    assert len(kg.query_gold(type_filter="skill", gold_db_path=gold)) == 1


def test_enrich_research_brief_adds_gold_section(tmp_path, monkeypatch):
    blackhole = tmp_path / "blackhole.db"
    gold = tmp_path / "gold.db"
    real = tmp_path / "doc.md"
    real.write_text("x")
    long = "x" * 600

    conn = sqlite3.connect(str(blackhole))
    _make_blackhole_schema(conn)
    _insert_item(conn, id="r1", source=str(real), name="AI Automation", content=f"Process automation with local models. {long}", gold_score=0.95, type="capability")
    conn.close()

    kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)

    brief = [
        "# Brief",
        "",
        "## Haeufigste Finding-Klassen (Bus)",
        "- AI Automation: 5 Events",
        "",
        "## Leitplanken",
        "Reversibel.",
    ]
    enriched = kg.enrich_research_brief(brief, gold_db_path=gold)
    assert any("Vorhandenes Gold-Wissen" in line for line in enriched)
    assert any("AI Automation" in line for line in enriched)


def test_sync_is_idempotent(tmp_path, monkeypatch):
    blackhole = tmp_path / "blackhole.db"
    gold = tmp_path / "gold.db"
    real = tmp_path / "doc.md"
    real.write_text("x")
    long = "x" * 600

    conn = sqlite3.connect(str(blackhole))
    _make_blackhole_schema(conn)
    _insert_item(conn, id="i1", source=str(real), name="Alpha", content=long, gold_score=0.9, type="capability")
    conn.close()

    s1 = kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)
    s2 = kg.sync_gold_db(blackhole_path=blackhole, gold_db_path=gold)
    assert s1["gold_kept"] == s2["gold_kept"] == 1

    gconn = sqlite3.connect(str(gold))
    count = gconn.execute("SELECT COUNT(*) FROM knowledge_gold").fetchone()[0]
    assert count == 1
    gconn.close()


def test_get_stats_reports_empty_when_no_db(tmp_path):
    missing = tmp_path / "missing.db"
    stats = kg.get_stats(gold_db_path=missing)
    assert stats["exists"] is False
    assert stats["count"] == 0
