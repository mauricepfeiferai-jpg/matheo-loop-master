---
status: vorgeschlagen
loop: loop-kernel-master-harness
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: loop-kernel-master-harness

**Zweck:** Master-Harness als Executive-Check regelmaessig laufen lassen
**Schedule:** `0 4 * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# loop-kernel-master-harness — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start loop-kernel-master-harness)
OUTPUT=$(mktemp /var/lib/loop-master/loop-kernel-master-harness.XXXX.out)
if bash /root/loop_kernel/master-harness/loop.sh > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop loop-kernel-master-harness`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
