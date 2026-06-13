---
status: telegram_approval
loop: housekeep-ask-large_dir-snap-private-tmp
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /tmp/snap-private-tmp

**Kategorie:** large_dir
**Grösse:** 2.08 GB
**Alter:** 39.3 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected/system path or >10 GB; human decision required

## Aktion
ask auf /tmp/snap-private-tmp

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-snap-private-tmp` oder `/deny housekeep-ask-large_dir-snap-private-tmp`.
