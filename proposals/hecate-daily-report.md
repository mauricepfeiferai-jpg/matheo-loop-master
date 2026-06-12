---
status: vorgeschlagen
loop: hecate-daily-report
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: hecate-daily-report

**Zweck:** R1: Bus verdichten, Tagesreport nach /var/lib/loop-master/daily_report.md + Telegram (nur neue krit sofort, nie Spam)
**Schedule:** `0 8 * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# hecate-daily-report — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start hecate-daily-report)
OUTPUT=$(mktemp /var/lib/loop-master/hecate-daily-report.XXXX.out)
if python3 -m hecate.report > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop hecate-daily-report`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
