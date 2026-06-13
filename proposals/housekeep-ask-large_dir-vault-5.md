---
status: approved
loop: housekeep-ask-large_dir-vault
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/vault

**Kategorie:** large_dir
**Grösse:** 103.39 GB
**Alter:** 3.9 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected/system path or >10 GB; human decision required

## Aktion
ask auf /root/vault

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-vault` oder `/deny housekeep-ask-large_dir-vault`.
