# Proposal: Cron-Eintrag für daily_agent_smoke.sh

**Status:** proposal-only  
**Risk:** P1 — führt read-only Smoke-Skript täglich aus  
**Requires:** Maurice GO + manuelle root-crontab-Eintrag

## Ziel

`scripts/daily_agent_smoke.sh` täglich um 07:30 UTC ausführen.

## Befehl für root-crontab

```cron
# HECATE daily agent smoke — read-only, no Telegram, no mutations
30 7 * * * cd /root/projects/loop-master && ./scripts/daily_agent_smoke.sh >> /var/log/hecate-daily-agent-smoke.log 2>&1
```

## Was passiert

- Läuft die 5 Agenten-Smoke-Befehle hintereinander.
- Schreibt Reports nach `reports/`.
- Schreibt `raw_trace` in `/var/lib/loop-master/learning_ledger.jsonl`.
- Logs Ausgaben nach `/var/log/hecate-daily-agent-smoke.log`.

## Was NICHT passiert

- Keine Mutationen, keine systemd-Änderungen, keine Telegram-Nachrichten.

## Stop-Bedingung

```bash
touch /var/lib/loop-master/.stop_daily_agent_smoke
```

Das Skript prüft diese Datei am Anfang und beendet sich, falls vorhanden.

## Nächster Schritt

Maurice führt den `crontab -e` Befehl selbst aus (per Policy: `/etc`-Edits nur durch Maurice).
