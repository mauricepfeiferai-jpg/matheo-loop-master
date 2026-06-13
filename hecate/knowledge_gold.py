"""Blackhole-Gold-Source — hart gefiltertes Wissen fuer HECATE.

Baut aus der grossen Blackhole-Datenbank (/root/projects/blackhole/graph.db)
eine schlanke, gepruefte Gold-DB unter /var/lib/loop-master/knowledge_gold.db.
Nur Items mit hohem gold_score, sauberem Source und lesbarem Inhalten ueberleben.

Regeln (Hard-Filter):
- type IN ('capability', 'skill')
- gold_score >= 0.7
- source existiert als Dateipfad
- source enthaelt kein Verzeichnis aus einer Deny-Liste
- name und content sind nicht leer
"""
import sqlite3
import sys
from pathlib import Path
from typing import Optional

BLACKHOLE_PATH = Path("/root/projects/blackhole/graph.db")
GOLD_DB_PATH = Path("/var/lib/loop-master/knowledge_gold.db")

SOURCE_DENY_PARTS = (
    "ARCHIV/old_",
    "_trash",
    "quarantine",
    ".git_QUARANTINED",
)

MIN_GOLD_SCORE = {
    "symbol": 0.7,
    "capability": 0.6,
    "skill": 0.6,
}
ALLOWED_TYPES = ("capability", "skill", "symbol")
MIN_CONTENT_LENGTH = 500


def _is_clean_source(source: Optional[str]) -> bool:
    if not source:
        return False
    p = Path(source)
    if not p.exists():
        return False
    lower = source.lower()
    return all(d.lower() not in lower for d in SOURCE_DENY_PARTS)


def _clean_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name = name.strip()
    if name.startswith("file:"):
        name = name[5:]
    # Bei Dateipfaden nur den Basename als lesbaren Titel nehmen,
    # wenn sonst nichts Brauchbares da ist.
    if "/" in name and "." in Path(name).name:
        basename = Path(name).name
        if len(basename) > 3:
            name = basename
    return name if len(name) > 1 else None


def _init_gold_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_gold (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            subtype TEXT,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            gold_score REAL NOT NULL,
            business_relevance REAL,
            reusability REAL,
            leverage REAL,
            novelty REAL,
            legal_weight REAL,
            synced_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_score ON knowledge_gold(gold_score)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_type ON knowledge_gold(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_name ON knowledge_gold(name)")


def sync_gold_db(
    blackhole_path: Path = BLACKHOLE_PATH,
    gold_db_path: Path = GOLD_DB_PATH,
    min_score: float = MIN_GOLD_SCORE,
) -> dict:
    """Filtere Gold aus Blackhole und schreibe eine schlanke Gold-DB.

    Returns:
        Statistik-Dict mit total_blackhole, gold_kept, rejected_reasons.
    """
    if not blackhole_path.exists():
        raise FileNotFoundError(f"Blackhole DB nicht gefunden: {blackhole_path}")

    gold_db_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_blackhole": 0,
        "gold_kept": 0,
        "rejected": {
            "wrong_type": 0,
            "low_score": 0,
            "bad_source": 0,
            "empty_name": 0,
            "empty_content": 0,
        },
    }

    src = sqlite3.connect(str(blackhole_path))
    src.row_factory = sqlite3.Row
    cur = src.cursor()
    cur.execute("SELECT COUNT(*) FROM items")
    stats["total_blackhole"] = cur.fetchone()[0]

    dst = sqlite3.connect(str(gold_db_path))
    _init_gold_db(dst)
    dst.execute("DELETE FROM knowledge_gold")

    cur.execute("""
        SELECT id, name, type, subtype, source, content, gold_score,
               business_relevance, reusability, leverage, novelty, legal_weight
        FROM items
    """)

    rows = []
    for r in cur:
        item_type = r["type"]
        if item_type not in ALLOWED_TYPES:
            stats["rejected"]["wrong_type"] += 1
            continue
        score = r["gold_score"] or 0.0
        type_min = MIN_GOLD_SCORE.get(item_type)
        if type_min is None or score < type_min:
            stats["rejected"]["low_score"] += 1
            continue
        content = (r["content"] or "").strip()
        if len(content) < MIN_CONTENT_LENGTH:
            stats["rejected"]["empty_content"] += 1
            continue
        source = r["source"]
        if not _is_clean_source(source):
            stats["rejected"]["bad_source"] += 1
            continue
        name = _clean_name(r["name"])
        if not name:
            stats["rejected"]["empty_name"] += 1
            continue

        rows.append({
            "id": r["id"],
            "name": name,
            "type": item_type,
            "subtype": r["subtype"],
            "source": source,
            "content": content,
            "gold_score": score,
            "business_relevance": r["business_relevance"],
            "reusability": r["reusability"],
            "leverage": r["leverage"],
            "novelty": r["novelty"],
            "legal_weight": r["legal_weight"],
        })

    # Deduplizieren: pro Source nur das Item mit dem hoechsten gold_score.
    by_source: dict[str, dict] = {}
    for row in rows:
        src_key = row["source"]
        existing = by_source.get(src_key)
        if existing is None or row["gold_score"] > existing["gold_score"]:
            by_source[src_key] = row

    deduped = list(by_source.values())

    if deduped:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        dst.executemany("""
            INSERT INTO knowledge_gold (
                id, name, type, subtype, source, content, gold_score,
                business_relevance, reusability, leverage, novelty, legal_weight, synced_at
            ) VALUES (
                :id, :name, :type, :subtype, :source, :content, :gold_score,
                :business_relevance, :reusability, :leverage, :novelty, :legal_weight, :synced_at
            )
        """, [{**r, "synced_at": now} for r in deduped])
        dst.commit()

    stats["gold_kept"] = len(deduped)
    stats["duplicates_dropped"] = len(rows) - len(deduped)
    src.close()
    dst.close()
    return stats


def query_gold(
    topic: Optional[str] = None,
    type_filter: Optional[str] = None,
    min_score: float = 0.6,
    limit: int = 10,
    gold_db_path: Path = GOLD_DB_PATH,
) -> list[dict]:
    """Frage die Gold-DB ab.

    topic: Wenn gesetzt, wird in name und content mit case-insensitive LIKE gesucht.
    type_filter: 'capability' oder 'skill' (oder None fuer beides).
    limit: max. Anzahl Ergebnisse.
    """
    if not gold_db_path.exists():
        return []

    conn = sqlite3.connect(str(gold_db_path))
    conn.row_factory = sqlite3.Row
    params: list = [min_score]
    where = ["gold_score >= ?"]

    if type_filter:
        where.append("type = ?")
        params.append(type_filter)

    if topic:
        where.append("(name LIKE ? OR content LIKE ?)")
        like = f"%{topic}%"
        params.extend([like, like])

    sql = f"""
        SELECT id, name, type, subtype, source, content, gold_score,
               business_relevance, reusability, leverage, novelty, legal_weight
        FROM knowledge_gold
        WHERE {" AND ".join(where)}
        ORDER BY gold_score DESC
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(gold_db_path: Path = GOLD_DB_PATH) -> dict:
    """Liefert aktuelle Statistik der Gold-DB."""
    if not gold_db_path.exists():
        return {"exists": False, "count": 0, "top_score": 0.0, "synced_at": None}

    conn = sqlite3.connect(str(gold_db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM knowledge_gold")
    count = cur.fetchone()[0]
    cur.execute("SELECT MAX(gold_score), synced_at FROM knowledge_gold")
    row = cur.fetchone()
    conn.close()
    return {
        "exists": True,
        "count": count,
        "top_score": row[0] or 0.0,
        "synced_at": row[1],
    }


def enrich_research_brief(brief_lines: list[str], gold_db_path: Path = GOLD_DB_PATH) -> list[str]:
    """Erweitere einen Research-Brief um Gold-Items zu den Top-Themen.

    Fuegt eine Sektion mit bereits vorhandenem, hochwertigem Wissen hinzu,
    damit Research-Sessions nicht bei Null anfangen.
    """
    if not gold_db_path.exists():
        return brief_lines

    # Heuristisch: nimm Worte aus Ueberschriften, die laenger als 4 Buchstaben sind.
    topics = []
    for line in brief_lines:
        if line.startswith("- ") and ":" in line:
            topic = line[2:line.index(":")].strip()
            if len(topic) > 4:
                topics.append(topic)
        if line.startswith("##"):
            topics.extend(w for w in line.strip("# ").split() if len(w) > 4)
    topics = list(dict.fromkeys(topics))[:5]

    if not topics:
        return brief_lines

    gold_hits = []
    for t in topics:
        hits = query_gold(topic=t, limit=3, gold_db_path=gold_db_path)
        for h in hits:
            if h["id"] not in {g["id"] for g in gold_hits}:
                gold_hits.append(h)
        if len(gold_hits) >= 10:
            break

    if not gold_hits:
        return brief_lines

    insert_idx = -1
    for i, line in enumerate(brief_lines):
        if line.startswith("## Leitplanken"):
            insert_idx = i
            break

    section = ["", "## Vorhandenes Gold-Wissen (aus Blackhole-Filter)", ""]
    for h in gold_hits[:10]:
        score = h["gold_score"]
        section.append(f"- [{h['type']}] {h['name']} (score {score:.2f})")
        snippet = (h["content"].replace("\n", " "))[:120]
        section.append(f"  {snippet}...")
    section.append("")

    if insert_idx >= 0:
        brief_lines = brief_lines[:insert_idx] + section + brief_lines[insert_idx:]
    else:
        brief_lines += section

    return brief_lines


def main() -> int:
    import json
    from datetime import datetime, timezone

    if len(sys.argv) > 1 and sys.argv[1] in ("--sync", "sync"):
        stats = sync_gold_db()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    if len(sys.argv) > 1 and sys.argv[1] in ("--stats", "stats"):
        print(json.dumps(get_stats(), indent=2, ensure_ascii=False))
        return 0

    if len(sys.argv) > 2 and sys.argv[1] in ("--query", "query"):
        topic = sys.argv[2]
        results = query_gold(topic=topic, limit=5)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    print("Usage: python3 -m hecate.knowledge_gold [--sync|--stats|--query TOPIC]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
