# Proposal: GitHub Remote für loop-master

**Status:** proposal-only  
**Risk:** P2 — external publication, requires explicit destination  
**Requires:** Maurice GO

## Ziel

Den lokalen Commit `acaf7cb` (feat: add 5 Hetzner agent contracts and smoke commands) zu einem GitHub-Remote pushen.

## Befehle

```bash
cd /root/projects/loop-master
git remote add origin https://github.com/mauricepfeiferai-jpg/matheo-loop-master.git
# Repo muss vorher auf GitHub erstellt werden (public oder private)
git push -u origin master
```

## Empfohlener Repo-Name

`mauricepfeiferai-jpg/matheo-loop-master`

Alternativen: `matheo-hecate`, `matheo-agent-os`

## Sicherheitshinweis

- Repo enthält keine Secrets (Verträge sind Prompt-Contracts, keine Tokens/Keys).
- Reports/ und `/var/lib/loop-master/` sind nicht committed.
- Vor Push: `git status` prüfen, dass nur beabsichtigte Dateien im Commit sind.

## Stop-Regel

Nur ausführen, wenn Maurice den Remote-Namen bestätigt oder selbst das Repo anlegt.
