---
status: vorgeschlagen
loop: housekeep-deprecated-_archive
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: housekeep-deprecated-_archive

**Zweck:** Housekeeping: archive_to_backup /root/_archive (0.01 GB)
**Schedule:** `einmalig`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# housekeep-deprecated-_archive — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start housekeep-deprecated-_archive)
OUTPUT=$(mktemp /var/lib/loop-master/housekeep-deprecated-_archive.XXXX.out)
if python3 -m hecate.system_housekeeper apply _archive > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop housekeep-deprecated-_archive`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
