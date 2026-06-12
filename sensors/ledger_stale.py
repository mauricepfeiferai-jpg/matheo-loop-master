"""S7: Ledger-Stale — verbindet Innen-Beweis (hecate.ledger) mit Aussen-Pruefung.
Ein Loop, der laut eigenem Ledger seit X Stunden keinen bewiesenen ok-Lauf hat,
wird zum Finding. Faengt still-failende instrumentierte Loops automatisch."""
from pathlib import Path

from sensors.bus import Finding

STALE_HOURS = 26  # > 1 Tag: faengt Daily-Loops, toleriert Wartungsfenster


def collect_from(ledger, hours: int = STALE_HOURS) -> list[Finding]:
    out: list[Finding] = []
    for name, last_ok in ledger.stale(hours=hours):
        out.append(Finding(
            sensor="ledger_stale", severity="hoch",
            f_class="ledger.stale-loop", subject=name,
            evidence=f"kein bewiesener ok-Lauf seit {hours}h (letzter ok: {last_ok or 'NIE'})",
            suggested_fix=f"loop_ledger report --loop {name} pruefen; Output-Artefakt fehlt oder Loop laeuft nicht"))
    return out


def collect() -> list[Finding]:
    from hecate.ledger import DB_PATH, Ledger
    if not Path(DB_PATH).exists():
        return []  # Ledger noch nicht in Benutzung — kein Finding, kein Crash
    return collect_from(Ledger())
