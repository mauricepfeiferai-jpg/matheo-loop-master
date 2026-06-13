---
status: telegram_approval
loop: housekeep-ask-large_dir-.hermes
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/.hermes

**Kategorie:** large_dir
**Grösse:** 15.59 GB
**Alter:** 0.0 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected/system path or >10 GB; human decision required

## Aktion
ask auf /root/.hermes

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-.hermes` oder `/deny housekeep-ask-large_dir-.hermes`.
