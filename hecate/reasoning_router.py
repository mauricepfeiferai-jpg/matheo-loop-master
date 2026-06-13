#!/usr/bin/env python3
"""Reasoning Router — waehlt das passende lokale Modell fuer jede Aufgabe.

Aufgaben:
  classify     → schnelles Mini-Modell fuer Labels/Kategorien
  code_analyze → Coder-Modell fuer Struktur, Patches, Reviews
  reason       → Reasoner fuer Entscheidungen, Risiken, Visionen
  embed        → Embedding-Modell fuer semantische Suche
  verify       → Coder-Modell um Behauptungen gegen Fakten zu pruefen
  vision       → Reasoner fuer grosse Konzepte und Zukunftsplanung

Alle Modelle laufen lokal ueber Ollama. Cloud-Modelle nur nach explizitem GO.
"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class TaskType(str, Enum):
    CLASSIFY = "classify"
    CODE_ANALYZE = "code_analyze"
    REASON = "reason"
    EMBED = "embed"
    VERIFY = "verify"
    VISION = "vision"


class ReasoningError(Exception):
    """Modell-Aufruf schlug fehl oder Timeout."""


@dataclass(frozen=True)
class ModelConfig:
    name: str
    context_length: int
    timeout: int
    temperature: float = 0.2


# Lokale Modelle, die auf dem Server verfuegbar sind.
DEFAULT_MODELS: dict[TaskType, ModelConfig] = {
    TaskType.CLASSIFY:    ModelConfig("qwen2.5:1.5b", context_length=32000, timeout=60),
    TaskType.CODE_ANALYZE: ModelConfig("qwen2.5-coder:7b", context_length=32000, timeout=180),
    TaskType.REASON:      ModelConfig("qwen3:8b", context_length=32000, timeout=240),
    TaskType.EMBED:       ModelConfig("nomic-embed-text", context_length=8192, timeout=30),
    TaskType.VERIFY:      ModelConfig("qwen2.5-coder:7b", context_length=32000, timeout=120),
    TaskType.VISION:      ModelConfig("qwen3:8b", context_length=32000, timeout=300),
}

OLLAMA_HOST = "http://127.0.0.1:11434"


def _ollama_generate(model: str, prompt: str, temperature: float, timeout: int) -> str:
    """Ruft /api/generate auf. Stream wird hier nicht verwendet."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "")


def _ollama_embed(model: str, text: str, timeout: int) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("embedding", [])


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


class ReasoningRouter:
    """Waehlt Modell, cached Embeddings, faellt auf lokale Modelle zurueck."""

    def __init__(
        self,
        models: dict[TaskType, ModelConfig] | None = None,
        ollama_host: str = OLLAMA_HOST,
        cache_dir: Path | None = None,
    ):
        self.models = models or DEFAULT_MODELS
        self.ollama_host = ollama_host
        self.cache_dir = cache_dir or Path("/var/lib/loop-master/embeddings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, model: str, text: str) -> Path:
        import hashlib
        h = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.json"

    def is_ollama_alive(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.ollama_host}/api/tags", timeout=5)
            return True
        except Exception:
            return False

    def generate(self, task: TaskType, prompt: str, context: str = "") -> str:
        cfg = self.models[task]
        full_prompt = self._build_prompt(task, prompt, context, cfg.context_length)
        try:
            return _ollama_generate(cfg.name, full_prompt, cfg.temperature, cfg.timeout)
        except Exception as exc:
            raise ReasoningError(f"{cfg.name} failed: {exc}") from exc

    def embed(self, text: str) -> list[float]:
        cfg = self.models[TaskType.EMBED]
        key = self._cache_key(cfg.name, text)
        if key.exists():
            return json.loads(key.read_text())
        try:
            vec = _ollama_embed(cfg.name, text, cfg.timeout)
        except Exception as exc:
            raise ReasoningError(f"{cfg.name} embed failed: {exc}") from exc
        key.write_text(json.dumps(vec))
        return vec

    def classify(self, text: str, labels: list[str]) -> str:
        prompt = (
            f"Klassifiziere den folgenden Text in EINES dieser Labels: {', '.join(labels)}.\n"
            f"Antworte NUR mit dem Label, nichts anderes.\n\nText:\n{text}\n\nLabel:"
        )
        return self.generate(TaskType.CLASSIFY, prompt).strip()

    def reason(self, question: str, context: str = "") -> str:
        prompt = (
            f"Du bist der HECATE Operator Layer auf einem Hetzner-Server. "
            f"Denke sorgfaeltig, technisch, knapp. Gib 3 Optionen wenn moeglich.\n\n"
            f"Frage: {question}\n\nAntwort:"
        )
        return self.generate(TaskType.REASON, prompt, context)

    def vision(self, topic: str, context: str = "") -> str:
        prompt = (
            f"Entwickle eine Vision fuer HECATE, das autonome Operator-System.\n"
            f"Thema: {topic}\n"
            f"Struktur: Problem → Konzept → Umsetzungsschritte → Risiko → Erfolgsmass.\n\nVision:"
        )
        return self.generate(TaskType.VISION, prompt, context)

    def verify(self, claim: str, evidence: str) -> str:
        prompt = (
            f"Puefe die Behauptung anhand der Beweise. Antworte mit TRUE/FALSE/UNCERTAIN "
            f"und einer kurzen Begruendung.\n\nBehauptung: {claim}\n\nBeweise:\n{evidence}\n\nErgebnis:"
        )
        return self.generate(TaskType.VERIFY, prompt)

    def code_analyze(self, code_or_path: str, question: str) -> str:
        prompt = (
            f"Analysiere den folgenden Code und beantworte die Frage. "
            f"Fokus auf Struktur, Abhaengigkeiten und Risiken.\n\n"
            f"Code/Pfad: {code_or_path}\n\nFrage: {question}\n\nAnalyse:"
        )
        return self.generate(TaskType.CODE_ANALYZE, prompt)

    def _build_prompt(self, task: TaskType, prompt: str, context: str, max_ctx: int) -> str:
        # Grobe Heuristik: 1 Token ~ 4 Zeichen. Wir halten uns deutlich unterhalb.
        max_chars = max_ctx // 4
        if context:
            prompt = f"Kontext:\n{_truncate(context, max_chars // 2)}\n\n{prompt}"
        return _truncate(prompt, max_chars)


def get_router() -> ReasoningRouter:
    return ReasoningRouter()
