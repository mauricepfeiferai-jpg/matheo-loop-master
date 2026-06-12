# Loop-Master

Safety-Fundament fuer den Executive Loop. Jede autonome Auto-Aktion laeuft durch safety.harness.run().

## Nutzung
```python
from safety.harness import SafeAction, run
r = run(SafeAction(
    id="restart-ollama",
    do_cmd="systemctl restart ollama",
    undo_cmd="true",
    verify_cmd="curl -sf localhost:11434/api/version",
    snapshot_files=["/etc/systemd/system/ollama.service.d/override.conf"],
))
# r.ok / r.rolled_back / r.denied
```
Deny-List (`safety/denylist.py`) blockt rm -rf ausserhalb _trash, git force/reset, apt, Legal-Pfade, Trading.
