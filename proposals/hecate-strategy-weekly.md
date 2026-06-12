---
status: vorgeschlagen
loop: hecate-strategy-weekly
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: hecate-strategy-weekly

**Zweck:** Opus-Wochensynthese: Bus + Ledger + Proposals + Revenue-Stand -> 3 strategische Optionen fuer die Woche (System denkt sich selbst neu)
**Schedule:** `0 18 * * 0`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# hecate-strategy-weekly — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start hecate-strategy-weekly)
OUTPUT=$(mktemp /var/lib/loop-master/hecate-strategy-weekly.XXXX.out)
if claude -p "Lies /var/lib/loop-master/daily_report.md + research_brief.md + /root/projects/loop-master/proposals/. Synthese mit max Thinking: 3 Optionen fuer die Woche, Fokus 100x/Revenue." --max-turns 20 > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop hecate-strategy-weekly`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
