#!/usr/bin/env python3
"""hecate.ledger — Zentrales, append-only Loop-Ledger (Innen-Beweis).

Uebernommen aus der Parallel-Session 2026-06-09, in Hecate integriert.
Kernregel: Ein Lauf gilt NUR als 'ok', wenn das Output-Artefakt existiert
und groesser als min_bytes ist. Exit-Code 0 ist KEIN Beleg.
Komplement zu den Sensoren (Aussen-Pruefung): Loops beweisen hier ihre Arbeit,
die Sensoren pruefen, ob niemand luegt (sensors/ledger_stale.py).

CLI:
    loop_ledger start <loop> [--phase X]      -> run_id
    loop_ledger finish <run_id> --output PFAD -> ok|empty_output|failed (Exit spiegelt Urteil)
    loop_ledger report [--loop NAME]
    loop_ledger stale --hours 26
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Hecate-Konvention: aller State unter /var/lib/loop-master/ (Abweichung zur
# Parallel-Session dokumentiert in HECATE.md). ENV-Override bleibt.
DB_PATH = os.environ.get("LOOP_LEDGER_DB", "/var/lib/loop-master/ledger.db")
DEFAULT_MIN_BYTES = 200  # 67B-Stubs fallen damit automatisch durch

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    loop_name   TEXT NOT NULL,
    phase       TEXT,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    output_path TEXT,
    output_bytes INTEGER,
    output_sha256 TEXT,
    host        TEXT,
    pid         INTEGER,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_loop ON runs(loop_name, started_at);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""

VALID_FINAL = {"ok", "empty_output", "failed", "skipped"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL;")   # parallele Schreiber ok
        self.db.execute("PRAGMA busy_timeout=15000;")
        self.db.executescript(SCHEMA)

    # ---- Schreiben (append-only: nur start + genau ein finish) ----

    def start(self, loop_name, phase=None, note=None):
        run_id = f"{loop_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.db.execute(
            "INSERT INTO runs (run_id, loop_name, phase, status, started_at, host, pid, note) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, loop_name, phase, "started", _now(),
             os.uname().nodename, os.getpid(), note),
        )
        self.db.commit()
        return run_id

    def finish(self, run_id, status=None, output_path=None,
               min_bytes=DEFAULT_MIN_BYTES, note=None):
        row = self.db.execute(
            "SELECT status FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"run_id unbekannt: {run_id}")
        if row[0] != "started":
            raise SystemExit(f"run_id bereits abgeschlossen ({row[0]}): {run_id}")

        out_bytes = None
        out_sha = None

        if status in ("failed", "skipped"):
            final = status
        elif output_path:
            if os.path.isfile(output_path):
                out_bytes = os.path.getsize(output_path)
                if out_bytes >= min_bytes:
                    final = "ok"
                    h = hashlib.sha256()
                    with open(output_path, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    out_sha = h.hexdigest()
                else:
                    final = "empty_output"
            else:
                final = "failed"
                note = (note or "") + f" [output fehlt: {output_path}]"
        else:
            final = "failed"
            note = (note or "") + " [kein output_path angegeben — kein Beweis]"

        if final not in VALID_FINAL:
            raise SystemExit(f"Ungueltiger Status: {final}")

        self.db.execute(
            "UPDATE runs SET status=?, finished_at=?, output_path=?, "
            "output_bytes=?, output_sha256=?, note=COALESCE(?, note) "
            "WHERE run_id=?",
            (final, _now(), output_path, out_bytes, out_sha, note, run_id),
        )
        self.db.commit()
        return final

    # ---- Lesen ----

    def report(self, loop_name=None, limit=20):
        if loop_name:
            q = ("SELECT run_id, phase, status, started_at, finished_at, "
                 "output_bytes, note FROM runs WHERE loop_name=? "
                 "ORDER BY started_at DESC LIMIT ?")
            return self.db.execute(q, (loop_name, limit)).fetchall()
        q = ("SELECT loop_name, status, started_at, finished_at, output_bytes, note "
             "FROM runs WHERE started_at = "
             "(SELECT MAX(started_at) FROM runs r2 WHERE r2.loop_name = runs.loop_name) "
             "ORDER BY loop_name")
        return self.db.execute(q).fetchall()

    def stale(self, hours=26):
        """Loops, deren letzter 'ok'-Lauf aelter als X Stunden ist (oder nie ok)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = ("SELECT loop_name, MAX(CASE WHEN status='ok' THEN started_at END) AS last_ok "
             "FROM runs GROUP BY loop_name "
             "HAVING last_ok IS NULL OR last_ok < ?")
        return self.db.execute(q, (cutoff,)).fetchall()


# ---------------- CLI ----------------

def main():
    p = argparse.ArgumentParser(description="Hecate Loop-Ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("loop_name")
    s.add_argument("--phase")
    s.add_argument("--note")

    f = sub.add_parser("finish")
    f.add_argument("run_id")
    f.add_argument("--status", choices=["failed", "skipped"])
    f.add_argument("--output")
    f.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    f.add_argument("--note")

    r = sub.add_parser("report")
    r.add_argument("--loop")
    r.add_argument("--limit", type=int, default=20)
    r.add_argument("--json", action="store_true")

    st = sub.add_parser("stale")
    st.add_argument("--hours", type=int, default=26)

    a = p.parse_args()
    led = Ledger()

    if a.cmd == "start":
        print(led.start(a.loop_name, phase=a.phase, note=a.note))
    elif a.cmd == "finish":
        final = led.finish(a.run_id, status=a.status, output_path=a.output,
                           min_bytes=a.min_bytes, note=a.note)
        print(final)
        sys.exit(0 if final in ("ok", "skipped") else 1)
    elif a.cmd == "report":
        rows = led.report(loop_name=a.loop, limit=a.limit)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(" | ".join(str(c) if c is not None else "—" for c in row))
    elif a.cmd == "stale":
        rows = led.stale(hours=a.hours)
        if not rows:
            print("Alle Loops innerhalb des Fensters ok.")
        for name, last_ok in rows:
            print(f"STALE: {name} — letzter ok-Lauf: {last_ok or 'NIE'}")
        sys.exit(1 if rows else 0)


if __name__ == "__main__":
    main()
