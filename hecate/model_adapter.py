#!/usr/bin/env python3
"""hecate.model_adapter — Einheitliche Modell-Abstraktion für HECATE.

Wraps hermes_adapter (Hermes/Claude via CLI), codex-bridge (Port 4101,
lokaler OpenAI-Proxy), und reasoning_router (Ollama lokal).

HECATE-Kontext-Pack bleibt modell-unabhängig: Modelle sind austauschbar,
das institutional knowledge in playbooks/learning_ledger bleibt erhalten.

Fallback-Kette:
  "local"  → Ollama → codex-bridge → Hermes
  "codex"  → codex-bridge → Ollama → Hermes
  "hermes" → Hermes → codex-bridge → Ollama

task_type Routing:
  "classify" → immer Ollama (schnell, lokal, günstig)
  "code"     → codex-bridge bevorzugt, fallback Hermes
  "reason"   → prefer bestimmt
  "embed"    → immer Ollama

Keine direkten Anthropic-API-Calls. Alles über CLI-Tools.

CLI:
  python3 -m hecate.model_adapter run --prompt "..." [--prefer local|codex|hermes] [--task reason|code|classify|embed]
  python3 -m hecate.model_adapter status
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

CODEX_BRIDGE_URL = "http://127.0.0.1:4101/v1/chat/completions"
CODEX_BRIDGE_MODEL = "gpt-4o"  # Proxy leitet intern weiter
CODEX_BRIDGE_TIMEOUT = 120

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT = 180

# Modelle für Ollama je nach Task
OLLAMA_TASK_MODELS: dict[str, str] = {
    "classify": "qwen2.5:0.5b",
    "reason": "qwen2.5:1.5b",
    "code": "qwen2.5-coder:7b",
    "embed": "nomic-embed-text",
    "default": "qwen2.5:1.5b",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AdapterResult:
    text: str
    model_used: str
    backend: str  # "local" | "codex" | "hermes"
    ok: bool
    error: str = ""
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "model_used": self.model_used,
            "backend": self.backend,
            "ok": self.ok,
            "error": self.error,
            "ts": self.ts,
        }


def _ollama_alive() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5)
        return True
    except Exception:
        return False


def _codex_bridge_alive() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:4101/health", timeout=5)
        return True
    except Exception:
        # Auch /v1/models versuchen als Fallback-Check
        try:
            urllib.request.urlopen("http://127.0.0.1:4101/v1/models", timeout=5)
            return True
        except Exception:
            return False


def _run_ollama(prompt: str, task_type: str) -> AdapterResult:
    model = OLLAMA_TASK_MODELS.get(task_type, OLLAMA_TASK_MODELS["default"])
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "").strip()
            return AdapterResult(text=text, model_used=model, backend="local", ok=bool(text))
    except Exception as exc:
        return AdapterResult(text="", model_used=model, backend="local", ok=False, error=str(exc))


def _run_codex_bridge(prompt: str) -> AdapterResult:
    payload = json.dumps({
        "model": CODEX_BRIDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        CODEX_BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=CODEX_BRIDGE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            model = data.get("model", CODEX_BRIDGE_MODEL)
            return AdapterResult(text=text, model_used=model, backend="codex", ok=bool(text))
    except Exception as exc:
        return AdapterResult(text="", model_used=CODEX_BRIDGE_MODEL, backend="codex", ok=False, error=str(exc))


def _run_hermes(prompt: str) -> AdapterResult:
    from hecate.hermes_adapter import chat as hermes_chat, HermesAdapterError
    try:
        result = hermes_chat(query=prompt, max_turns=5, quiet=True)
        return AdapterResult(
            text=result.stdout.strip(),
            model_used="hermes",
            backend="hermes",
            ok=result.ok and bool(result.stdout.strip()),
            error=result.stderr if not result.ok else "",
        )
    except HermesAdapterError as exc:
        return AdapterResult(text="", model_used="hermes", backend="hermes", ok=False, error=str(exc))
    except Exception as exc:
        return AdapterResult(text="", model_used="hermes", backend="hermes", ok=False, error=str(exc))


class ModelAdapter:
    """Einheitliche Modell-Abstraktion mit automatischem Fallback."""

    def __init__(self, prefer: str = "local"):
        if prefer not in ("local", "codex", "hermes"):
            raise ValueError(f"prefer muss 'local', 'codex' oder 'hermes' sein, war: {prefer!r}")
        self.prefer = prefer

    def _fallback_chain(self, task_type: str) -> list[str]:
        """Bestimmt die Backend-Reihenfolge je nach prefer und task_type."""
        if task_type in ("classify", "embed"):
            return ["local"]  # Kein Fallback für Classification — lokal oder nichts

        if task_type == "code":
            return ["codex", "hermes", "local"]

        # reason / default
        chains = {
            "local":  ["local", "codex", "hermes"],
            "codex":  ["codex", "local", "hermes"],
            "hermes": ["hermes", "codex", "local"],
        }
        return chains.get(self.prefer, ["local", "codex", "hermes"])

    def run(self, prompt: str, task_type: str = "reason") -> AdapterResult:
        """Führt den Prompt aus, mit automatischem Fallback."""
        chain = self._fallback_chain(task_type)
        last_result: AdapterResult | None = None

        for backend in chain:
            if backend == "local":
                result = _run_ollama(prompt, task_type)
            elif backend == "codex":
                result = _run_codex_bridge(prompt)
            else:
                result = _run_hermes(prompt)

            last_result = result
            if result.ok:
                return result

        # Alle Backends fehlgeschlagen
        if last_result is None:
            last_result = AdapterResult(text="", model_used="none", backend="none", ok=False, error="No backend available")
        return last_result

    def status(self) -> dict:
        return {
            "prefer": self.prefer,
            "ollama_alive": _ollama_alive(),
            "codex_bridge_alive": _codex_bridge_alive(),
            "hermes": "via CLI",
        }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="HECATE Model Adapter")
    sub = parser.add_subparsers(dest="cmd")

    r = sub.add_parser("run")
    r.add_argument("--prompt", required=True)
    r.add_argument("--prefer", default="local", choices=["local", "codex", "hermes"])
    r.add_argument("--task", default="reason", choices=["reason", "code", "classify", "embed"])

    sub.add_parser("status")

    args = parser.parse_args()

    if args.cmd == "run":
        adapter = ModelAdapter(prefer=args.prefer)
        result = adapter.run(args.prompt, task_type=args.task)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        sys.exit(0 if result.ok else 1)
    elif args.cmd == "status":
        adapter = ModelAdapter()
        print(json.dumps(adapter.status(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
