---
status: vorgeschlagen
loop: housekeep-large_dir-snap-private-tmp
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: housekeep-large_dir-snap-private-tmp

**Zweck:** Housekeeping: delete /tmp/snap-private-tmp (2.08 GB)
**Schedule:** `einmalig`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# housekeep-large_dir-snap-private-tmp — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start housekeep-large_dir-snap-private-tmp)
OUTPUT=$(mktemp /var/lib/loop-master/housekeep-large_dir-snap-private-tmp.XXXX.out)
if python3 -m hecate.system_housekeeper apply snap-private-tmp > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop housekeep-large_dir-snap-private-tmp`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
