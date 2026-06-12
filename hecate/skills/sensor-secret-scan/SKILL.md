---
name: sensor-secret-scan
sensor: secret_scan
description: Scannt das Dateisystem auf hartcodierte Secrets (API Keys, Tokens, Passwörter). Use when neue Dateien hinzukommen, Repos geklont werden, oder vor Commits.
---

# Secret-Scan Sensor

## Overview
Regex-basierte Suche nach Token-Mustern in Dateien, mit Perm-Check (world-readable). Schreibt Funde in den Bus mit Severity basierend auf Perm-Wert.

## When to Use
- Vor jedem Commit
- Nach Repo-Klonen
- Bei neuen Konfigurationsdateien
- Wenn Services mit Auth-Problemen fehlschlagen

## Core Process
1. `git ls-files` + manuelle Pfade scannen
2. Regex-Muster auf jede Datei anwenden (API keys, tokens, passwords)
3. `os.stat` für Perm-Check
4. Severity zuweisen: 0o644+ = kritisch, 0o600 = hoch
5. Bus-Finding schreiben mit suggested_fix

## Verification
- [ ] Keine 0o644+ Dateien mit Secrets
- [ ] Keine unrotierten Keys im Repo
- [ ] Alle Funde haben suggested_fix

## Red Flags
- "Das ist nur für Tests" → Secrets gehören nirgends
- "Ich lösche es später" → Wird nie gelöscht
- Token in Logs oder Config-Beispielen
