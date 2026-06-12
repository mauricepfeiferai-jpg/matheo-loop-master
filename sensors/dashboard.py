"""Loop-Dashboard: aggregierte Sicht auf den Findings-Bus.
Ersetzt lab/observatory (das den toten health-sentinel monatelang
kommentarlos anzeigte): hier wird BEWERTET, nicht nur angezeigt.
Dedupliziert auf (f_class, subject) — Wiederholungen zaehlen hoch statt zu spammen."""
import json
import sys
from collections import OrderedDict
from pathlib import Path

from sensors.bus import BUS_PATH

_ORDER = ["krit", "hoch", "info"]


def _load(bus_path: Path) -> list[dict]:
    if not bus_path.exists():
        return []
    out = []
    for line in bus_path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def render(bus_path: Path = BUS_PATH) -> str:
    findings = _load(bus_path)
    if not findings:
        return "Keine Findings im Bus.\n"
    # Dedup: gleiche (f_class, subject) -> letztes Finding gewinnt, Count steigt
    dedup: OrderedDict[tuple, dict] = OrderedDict()
    counts: dict[tuple, int] = {}
    for f in findings:
        key = (f.get("f_class", "?"), f.get("subject", "?"))
        dedup[key] = f
        counts[key] = counts.get(key, 0) + 1

    by_sev: dict[str, list[tuple[tuple, dict]]] = {s: [] for s in _ORDER}
    for key, f in dedup.items():
        by_sev.setdefault(f.get("severity", "info"), []).append((key, f))

    lines = ["═══ LOOP-MASTER DASHBOARD ═══",
             f"Bus: {bus_path}  ({len(findings)} Events, {len(dedup)} unique)", ""]
    for sev in _ORDER:
        items = by_sev.get(sev, [])
        lines.append(f"── {sev.upper()} ({len(items)}) " + "─" * 30)
        for key, f in items:
            n = counts[key]
            rep = f"  [{n}x]" if n > 1 else ""
            lines.append(f"  {f['f_class']} @ {f['subject']}{rep}")
            lines.append(f"      {f['evidence'][:160]}")
            if f.get("suggested_fix"):
                lines.append(f"      → {f['suggested_fix'][:140]}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(render(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
