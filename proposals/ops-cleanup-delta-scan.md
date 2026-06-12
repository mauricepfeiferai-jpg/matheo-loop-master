---
status: vorgeschlagen
loop: ops-cleanup (einmalig, kein Loop)
erstellt: aus Delta-Scan 2026-06-10
---

# Proposal: Ops-Cleanup aus dem Projekt-Loop-Delta-Scan

Alle Aktionen reversibel; Ausführung nach Freigabe, sensible via safety.harness.

1. **openclaw-gateway USER-Unit disablen** (`systemctl --user disable --now openclaw-gateway`)
   — crash-loopt im 5s-Takt (~17k Fehlstarts/Tag, MODULE_NOT_FOUND); die SYSTEM-Unit
   läuft parallel sauber und macht den Job. Revert: enable.
2. **gpe-dashboard-Container stoppen** — Host-Quellcode wurde gelöscht, Container läuft
   auf Bind-Mount-Geist, `restart=always` = Crash-Looper beim nächsten Docker-Restart.
   Revert: Code wiederherstellen oder Container neu bauen.
3. **PM2-Dump entschärfen** — `~/.pm2/dump.pm2` sichern + leeren: ein verirrtes
   `pm2 resurrect` würde 6 Alt-Agenten inkl. trading_army_orchestrator wecken.
4. **ant-protocol-Container stoppen** — 4 interne Loops failen seit Wochen sekündlich
   (Redis fehlt), produziert nur Fehler-Logs. Revert: docker start.
5. **Zombies kicken** — `claude doctor` (PID 1528007, hängt seit 21.05.) + 4 verwaiste
   headless-Chromium-Sätze (`/tmp/agent-browser-chrome-*`).
6. **Tote User-Units archivieren** — openclaw-node.service, approval-daemon.service.

## Abnahme
Journal ruhig (keine 5s-Restarts mehr), `docker ps` ohne Geister, pm2 list leer + Dump gesichert.

> Umsetzung NUR nach Freigabe ("go ops-cleanup") und durch safety.harness.run() — Deny-List gilt.
