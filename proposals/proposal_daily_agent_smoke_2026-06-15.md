# Proposal: 5 Hetzner-Agenten als manuellen Daily-Smoke automatisieren

**Status:** proposal-only  
**Risk:** P1 — erzeugt Reports + Ledger-Einträge, aber keine Mutationen, kein Telegram  
**Requires:** Maurice GO

## Ziel

Die 5 neuen Hetzner-Agenten (`archivist`, `cost_guard`, `security_scanner`, `backup_checker`, `performance_profiler`) einmal täglich als read-only Smoke-Lauf ausführen — ohne autonome Loops, ohne systemd-Daemons, ohne Telegram.

## Vorgeschlagene Umsetzung

Ein einfaches Wrapper-Skript `scripts/daily_agent_smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /root/projects/loop-master

for agent in archivist cost_guard security_scanner backup_checker performance_profiler; do
  python3 -m hecate.agent_smoke "$agent" || true
done
```

### Optionen

1. **Cron (empfohlen für den Anfang):** Einzelner Eintrag in root-crontab, z. B. 07:30 täglich.
2. **systemd timer:** Robustere Logging-Integration, aber mehr Boilerplate.
3. **HECATE-Daily-Report integrieren:** R1 verdichtet alle Agenten-Reports zu einem Digest.

## Was NICHT passiert

- Keine automatischen Mutationen (kein `rm`, `systemctl`, `chmod`, Backup-Ausführung).
- Kein Telegram-Versand.
- Keine Cloud-Modelle ohne GO.

## Akzeptanzkriterien

- 7 Tage lang manuell beobachtet.
- Reports sinnvoll und nicht zu lang.
- Keine P0/P1 False Positives.
- Maurice bestätigt, dass der Daily-Smoke Arbeitsersparnis bringt.

## Nächster Schritt

Wenn approved: Wrapper-Skript bauen + Cron-Eintrag als Proposal-Datei vorbereiten (nicht aktivieren).
