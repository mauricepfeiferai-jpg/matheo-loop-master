---
status: vorgeschlagen
loop: old-hecate-hydra-scan
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: old-hecate-hydra-scan

**Zweck:** Hydra Cron-Health-Scan aus altem HECATE v1 beibehalten
**Schedule:** `*/10 * * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# old-hecate-hydra-scan — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start old-hecate-hydra-scan)
OUTPUT=$(mktemp /var/lib/loop-master/old-hecate-hydra-scan.XXXX.out)
if bash /root/hecate/workers/hermes-herkules/labors/02_lernean_hydra/scan.sh > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop old-hecate-hydra-scan`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
