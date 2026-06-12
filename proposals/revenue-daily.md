---
status: vorgeschlagen
loop: revenue-daily
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: revenue-daily

**Zweck:** DER 100x-Hebel: taeglich EINEN konkreten Vertriebsschritt erzwingen (KFZ-Lindemann-Angebot, Agent-Stack-Kit) — Telegram-Prompt mit genau 3 Optionen. Engpass ist Distribution, nicht Code.
**Schedule:** `0 9 * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# revenue-daily — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start revenue-daily)
OUTPUT=$(mktemp /var/lib/loop-master/revenue-daily.XXXX.out)
if python3 -m hecate.report && echo 'TODO: revenue_nudge.py — naechste Bau-Session' > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop revenue-daily`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
