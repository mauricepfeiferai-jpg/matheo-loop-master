---
name: sensor-config-drift
sensor: config_drift
description: Erkennt Konfigurationsabweichungen und Drift in systemd-Services, cron.d und Env-Files. Use when Services geändert wurden, neue Drop-Ins auftauchen, oder Env-Files divergieren.
---

# Config-Drift Sensor

## Overview
Vergleicht laufende Systemkonfiguration gegen erwarteten Zustand. Findet Drop-In-Dateien, redundant definierte Variablen, ungültige cron-User und nicht-traversierbare Verzeichnisse.

## When to Use
- Nach systemd-Änderungen
- Wenn Services unerwartet verhalten
- Vor Deployments (Sanity-Check)
- Wenn neue Drop-In-Dateien auftauchen

## Core Process
1. `systemctl show` für jede Unit ausführen
2. Env-Variablen extrahieren und auf Duplikate prüfen
3. Drop-In-Dateien verifizieren (existiert die Unit?)
4. cron.d Dateien auf ungültige User prüfen
5. Verzeichnis-Traversierung für Service-User testen

## Verification
- [ ] Keine redundanten Env-Variablen
- [ ] Keine orphanen Drop-In-Dateien
- [ ] Alle cron.d-User existieren
- [ ] Service-User können ihre Verzeichnisse traversieren

## Red Flags
- "Das läuft schon so lange" → Drift akkumuliert
- "Ich habe nur schnell was geändert" → Undokumentierte Änderung
- Drop-In ohne existierende Unit


## Known Issues

- config-drift.env-conflict: Aufgetreten 6x. Prüfe vor jeder Ausführung.
- config-drift.not-traversable: Aufgetreten 6x. Prüfe vor jeder Ausführung.
