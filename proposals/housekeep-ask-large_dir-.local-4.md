---
status: vorgeschlagen
loop: housekeep-ask-large_dir-.local
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/.local

**Kategorie:** large_dir
**Grösse:** 5.12 GB
**Alter:** 99.1 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected/system path or >10 GB; human decision required

## Aktion
ask auf /root/.local

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-.local` oder `/deny housekeep-ask-large_dir-.local`.
