---
status: vorgeschlagen
loop: housekeep-deprecated-gpe-openclaw
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: housekeep-deprecated-gpe-openclaw

**Zweck:** Housekeeping: archive_to_backup /root/gpe-openclaw (1.54 GB)
**Schedule:** `einmalig`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# housekeep-deprecated-gpe-openclaw — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start housekeep-deprecated-gpe-openclaw)
OUTPUT=$(mktemp /var/lib/loop-master/housekeep-deprecated-gpe-openclaw.XXXX.out)
if python3 -m hecate.system_housekeeper apply gpe-openclaw > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop housekeep-deprecated-gpe-openclaw`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
