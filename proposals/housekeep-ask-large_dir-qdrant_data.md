---
status: vorgeschlagen
loop: housekeep-ask-large_dir-qdrant_data
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/qdrant_data

**Kategorie:** large_dir
**Grösse:** 2.12 GB
**Alter:** 22.1 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (60%)
**Evidenz:** No safe rule matched; needs review

## Aktion
ask auf /root/qdrant_data

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-qdrant_data` oder `/deny housekeep-ask-large_dir-qdrant_data`.
