# HECATE — Loop Agent Master (v2, kanonisch)

> Das System, das Loops prüft, kreiert, researcht und testet.
> Gebaut 2026-06-09/10 aus dem Besten zweier Sessions. Eine Wahrheit, ein Gate.

**Status 2026-06-13:** `/root/projects/loop-master` ist der einzige aktive HECATE-Master.
`/root/hecate` v1 und `/root/loop_kernel` sind reversibel pausiert; ihre Funktionen wandern
als gated Proposals hierher. Siehe [`ARCHIVE_old_hecate.md`](./ARCHIVE_old_hecate.md).

## Die 5 Loops (100x-Architektur)

| # | Loop | Takt | Status | Zweck |
|---|------|------|--------|-------|
| 1 | hecate-sensors | */15 | 🟢 LÄUFT (root-crontab) | 7 Sensoren prüfen ALLE Loops + System (Außen-Prüfung) |
| 2 | hecate-daily-report | 08:00 | 📋 Proposal | R1: Verdichten → Telegram, nie Spam |
| 3 | hecate-research-weekly | Mo 06:00 | 📋 Proposal | R2: findet beste Loop-Inhalte → reicht Proposals ein |
| 4 | revenue-daily | 09:00 | 📋 Proposal | DER 100x-Hebel: täglich 1 Vertriebsschritt (Engpass = Distribution!) |
| 5 | hecate-strategy-weekly | So 18:00 | 📋 Proposal | Opus-Synthese: System denkt sich neu, 3 Optionen/Woche |

## Bausteine

- `safety/` — Harness: Deny-List + Checkpoint→Verify→Auto-Rollback. JEDE Umsetzung läuft hierdurch.
- `sensors/` — 7 Sensoren + flock-Bus + Dashboard (`python3 -m sensors.dashboard`). Fehlerisoliert.
- `hecate/hermes_adapter.py` — Hermes Agent (Nous Research) als Ausführungs- und Messaging-Schicht.
  `send_message`, `chat`, `run_skill`, `status`. Telegram-Escalation nutzt den Adapter.
- `hecate/ledger.py` — Innen-Beweis (aus Parallel-Session): kein Output-Artefakt ≥200B = kein Erfolg.
  State: `/var/lib/loop-master/ledger.db` (Abweichung zur Parallel-Session: ein State-Ort für alles).
- `hecate/report.py` — R1-Verdichter (deterministisch, Anti-Spam-Gedächtnis).
- `hecate/research_brief.py` — R2-Brief-Generator (Input für claude -p Research).
- `hecate/loop_factory.py` — kreiert neue Loops: ab Geburt Ledger-instrumentiert + Harness-pflichtig + gated.
- `proposals/` — das Gate: vorgeschlagen → freigegeben (Maurice) → umgesetzt → verifiziert.
  Telegram-1-Tap: galaxia-approval-bot läuft bereits (Integration = nächste Etappe).
- `SOUL.md` — Identity des Executive (Etappe 4).

## Eiserne Regeln (testbewiesen, 57 Tests)

1. Kein Beweis = kein Erfolg (Ledger; Exit 0 zählt nicht).
2. Ein crashender Prüfer darf nie die Prüfung killen (health-sentinel-Lektion).
3. Restart heilt keine Konfig-Ursache (ollama, 18 Restarts).
4. Prompt-Constraints sind keine Sicherung — die Deny-List ist Code (core.py-Lektion).
5. Nichts wird live ohne Freigabe; alles Reversible mit Auto-Rollback.
6. Loops, die nicht auf Revenue/Distribution einzahlen, sind Selbstzweck (100x-Filter).

## Kommandos

```bash
cd /root/projects/loop-master
python3 -m pytest tests/ -q          # 57 Tests
python3 -m sensors.run_all           # Sensor-Lauf (läuft auch */15 via Cron)
python3 -m sensors.dashboard         # Loop-Dashboard
python3 -m hecate.report             # Tagesreport bauen
python3 -m hecate.research_brief     # Research-Brief generieren
python3 -m hecate.ledger report      # Loop-Erfolgs-Buchführung
```
