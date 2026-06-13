---
status: vorgeschlagen
loop: housekeep-ask-large_dir-projects
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/projects

**Kategorie:** large_dir
**Grösse:** 20.04 GB
**Alter:** 0.7 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected path or >10 GB; human decision required

## Aktion
ask auf /root/projects

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-projects` oder `/deny housekeep-ask-large_dir-projects`.
