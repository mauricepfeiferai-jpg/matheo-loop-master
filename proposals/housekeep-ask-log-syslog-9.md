---
status: telegram_approval
loop: housekeep-ask-log-syslog
erstellt: durch hecate.system_housekeeper
telegram_approval: required
---

# Freigabe erforderlich: ask /var/log/syslog

**Kategorie:** log
**Grösse:** 0.14 GB
**Alter:** 0.0 Tage
**Begruendung:** Log file >= 50.0 MB
**Vorschlag des lokalen Classifiers:** ask_maurice (95%)
**Evidenz:** Protected/system path or >10 GB; human decision required

## Aktion
ask auf /var/log/syslog

## Sicherheitsmassnahmen
1. Backup vorher pruefen (nur bei migrate/archive)
2. Ledger-Eintrag nachher
3. Verify-Loop prueft Erfolg

## Freigabe
Antworte im Telegram mit `/approve housekeep-ask-log-syslog` oder `/deny housekeep-ask-log-syslog`.
