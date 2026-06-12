---
status: vorgeschlagen
loop: hecate-research-weekly
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: hecate-research-weekly

**Zweck:** R2: Loop-Research-Team — Wochen-Brief generieren, dann claude -p Session, die beste Loop-Inhalte (GitHub/Web/Hermes) recherchiert und als Proposals einreicht
**Schedule:** `0 6 * * 1`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# hecate-research-weekly — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start hecate-research-weekly)
OUTPUT=$(mktemp /var/lib/loop-master/hecate-research-weekly.XXXX.out)
if python3 -m hecate.research_brief && claude -p "$(cat /var/lib/loop-master/research_brief.md)" --max-turns 30 > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop hecate-research-weekly`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
