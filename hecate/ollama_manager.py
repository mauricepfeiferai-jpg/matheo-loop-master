"""Ollama Manager — sorgt dafuer, dass HECATE lokale Modelle effizient nutzt.

Auf dem Hetzner-Server laeuft Ollama CPU-only. Mehrere grosse Modelle
gleichzeitig im RAM fuehren zu Timeouts und Swapping.
Dieses Modul kuemmert sich um:
- Auflisten laufender Modelle
- Entladen nicht benoetigter Modelle vor einem geplanten Aufruf
- Pruefen, ob genug Speicher fuer ein bestimmtes Modell verfuegbar ist
- Empfehlen eines kleineren Modells, wenn der Speicher knapp ist
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

OLLAMA_HOST = "http://127.0.0.1:11434"


class OllamaError(Exception):
    """Fehler bei Ollama-Operationen."""


@dataclass(frozen=True)
class RunningModel:
    name: str
    size_vram: int  # Bytes
    until: str


def _api(path: str, data: Optional[dict] = None, timeout: int = 30) -> dict:
    url = f"{OLLAMA_HOST}{path}"
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise OllamaError(f"Ollama API {path} failed: {exc}") from exc


def list_running_models() -> list[RunningModel]:
    """Gibt alle aktuell im Speicher geladenen Modelle zurueck."""
    data = _api("/api/ps")
    models = []
    for m in data.get("models", []):
        models.append(RunningModel(
            name=m.get("name", "unknown"),
            size_vram=m.get("size_vram", 0),
            until=m.get("expires_at", "unknown"),
        ))
    return models


def unload_model(name: str, timeout: int = 60) -> bool:
    """Entlaedt ein Modell aus dem Arbeitsspeicher.

    Ollama unterstuetzt kein offizielles Unload. Workaround:
    Wir senden einen leeren Generate-Aufruf mit keep_alive=0,
    was das Modell nach kurzer Zeit aus dem Speicher entfernt.
    """
    try:
        _api("/api/generate", {
            "model": name,
            "prompt": "",
            "keep_alive": 0,
            "stream": False,
        }, timeout=timeout)
        return True
    except OllamaError:
        return False


def ensure_only_model_loaded(target: str, timeout: int = 60) -> bool:
    """Entlaedt alle laufenden Modelle ausser dem Zielmodell.

    Returns:
        True, wenn nur noch das Zielmodell laeuft (oder es schon so war).
    """
    running = list_running_models()
    changed = False
    for m in running:
        if m.name != target:
            unload_model(m.name, timeout=timeout)
            changed = True
    return changed


def estimate_model_size_gb(name: str) -> float:
    """Schaetzt die RAM-Groesse eines Modells anhand seines Namens.

    Dies ist eine Heuristik, bis Ollama die tatsaechliche Groesse liefert.
    """
    lower = name.lower()
    if ":" in lower:
        tag = lower.split(":")[1]
        # Beispiele: 0.5b, 1.5b, 7b, 14b, 30b, 32b, 80b
        import re
        match = re.search(r"(\d+(?:\.\d+)?)b", tag)
        if match:
            params = float(match.group(1))
            # 1B Parameter ~ 0.5 GB im 4-bit-Quant-Zustand
            return params * 0.5
    # Fallback: Standardannahme
    return 4.0


def available_memory_gb() -> float:
    """Gibt verfuegbaren Arbeitsspeicher in GB zurueck."""
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                if ":" in line:
                    key, val = line.split(":", 1)
                    mem[key.strip()] = int(val.split()[0]) / 1024 / 1024  # GB
        # MemAvailable ist der wahre freie Speicher
        return mem.get("MemAvailable", 0.0)
    except Exception:
        return 0.0


def can_fit_model(name: str, headroom_gb: float = 2.0) -> bool:
    """Prueft, ob das Modell in den verfuegbaren RAM passt."""
    needed = estimate_model_size_gb(name) + headroom_gb
    return available_memory_gb() >= needed


def recommend_model_for_task(preferred: str, task: str = "") -> str:
    """Empfiehlt ein Modell, das auf den Server passt.

    Falls das bevorzugte Modell nicht passt, wird zu einem kleineren
    Fallback gewechselt.
    """
    if can_fit_model(preferred):
        return preferred

    # Fallback-Hierarchie: kleineres Modell waehlen
    fallbacks = {
        "qwen2.5-coder:14b": "qwen2.5-coder:7b",
        "qwen2.5-coder:7b": "qwen2.5:1.5b",
        "qwen2.5:1.5b": "qwen2.5:0.5b",
        "qwen3:8b": "qwen2.5:1.5b",
        "qwen3:30b-a3b": "qwen2.5:1.5b",
        "qwen3:32b": "qwen2.5:1.5b",
    }
    fallback = fallbacks.get(preferred, "qwen2.5:0.5b")
    if can_fit_model(fallback):
        return fallback
    return "qwen2.5:0.5b"


def prepare_for_model(name: str, timeout: int = 60) -> dict:
    """Bereitet Ollama auf einen Modell-Aufruf vor.

    1. Entlaedt alle anderen Modelle.
    2. Prueft, ob genug Speicher verfuegbar ist.
    3. Empfiehlt ein passendes Modell.

    Returns:
        Dict mit 'model', 'unloaded', 'memory_ok', 'available_gb'
    """
    unloaded = ensure_only_model_loaded(name, timeout=timeout)
    available = available_memory_gb()
    recommended = recommend_model_for_task(name)
    memory_ok = can_fit_model(recommended)

    return {
        "model": recommended,
        "requested_model": name,
        "unloaded": unloaded,
        "memory_ok": memory_ok,
        "available_gb": round(available, 2),
    }


def main() -> int:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ps":
        models = list_running_models()
        print(f"Running models: {len(models)}")
        for m in models:
            print(f"  {m.name}: {m.size_vram / 1024 / 1024:.1f} MB")
        print(f"Available memory: {available_memory_gb():.2f} GB")
        return 0

    if len(sys.argv) > 2 and sys.argv[1] == "prepare":
        result = prepare_for_model(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("Usage: python3 -m hecate.ollama_manager ps | prepare <model>")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
