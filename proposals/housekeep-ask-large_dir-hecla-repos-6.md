---
status: telegram_approval
loop: housekeep-ask-large_dir-hecla-repos
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /root/hecla-repos

**Kategorie:** large_dir
**Grösse:** 3.98 GB
**Alter:** 2.0 Tage
**Begruendung:** Directory >= 1.0 GB
**Vorschlag des lokalen Classifiers:** ask_maurice (60%)
**Evidenz:** No safe rule matched; needs review

## Aktion
ask auf /root/hecla-repos

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-large_dir-hecla-repos` oder `/deny housekeep-ask-large_dir-hecla-repos`.
