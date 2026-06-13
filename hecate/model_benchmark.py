#!/usr/bin/env python3
"""Benchmark lokale Modelle fuer HECATE-Aufgaben.

Parallele Ausfuehrung, kurze Timeouts, schnelle Kandidaten zuerst.
Speichert Ergebnisse in /var/lib/loop-master/model_benchmark.json.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from hecate.reasoning_router import OLLAMA_HOST, TaskType
import urllib.request

PROMPTS = {
    TaskType.CLASSIFY: "Classify only as hardware/config/security: disk 95% full",
    TaskType.CODE_ANALYZE: "Review: def add(a,b): return a+b. One risk.",
    TaskType.REASON: "Server load 8.0. 3 possible causes, max 20 words.",
    TaskType.VERIFY: "Claim: Earth is flat. Evidence: NASA. TRUE/FALSE.",
    TaskType.VISION: "One improvement for a self-healing server agent. Max 30 words.",
}

# Modelle, die auf dem Server verfuegbar sind. Prioritaet: schnell > qualitativ.
# Minimaler Benchmark: schnellste Modelle, kurze Prompts.
MODELS = {
    TaskType.CLASSIFY: [
        ("qwen2.5:1.5b", 60),
    ],
    TaskType.CODE_ANALYZE: [
        ("qwen2.5:1.5b", 90),
    ],
    TaskType.REASON: [
        ("qwen2.5:1.5b", 90),
    ],
    TaskType.VERIFY: [
        ("qwen2.5:1.5b", 90),
    ],
    TaskType.VISION: [
        ("qwen2.5:1.5b", 90),
    ],
}


def _generate(model: str, prompt: str, timeout: int) -> dict:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 64},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            elapsed = time.perf_counter() - start
            return {
                "model": model,
                "ok": True,
                "response": data.get("response", "").strip()[:120],
                "elapsed": round(elapsed, 2),
                "tokens": data.get("eval_count", 0),
            }
    except Exception as exc:
        return {"model": model, "ok": False, "error": str(exc)[:120], "elapsed": timeout}


def benchmark(task: TaskType) -> list[dict]:
    prompt = PROMPTS[task]
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_generate, model, prompt, timeout): model
            for model, timeout in MODELS[task]
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results


def benchmark_all() -> dict:
    out = {}
    for task in MODELS:
        print(f"Benchmarking {task.value}...", flush=True)
        out[task.value] = benchmark(task)
    return out


def pick_fastest_per_task(results: dict) -> dict:
    """Waehlt pro Task das schnellste ok-Modell."""
    picks = {}
    for task, models in results.items():
        ok = [m for m in models if m.get("ok")]
        if ok:
            picks[task] = min(ok, key=lambda m: m["elapsed"])
        else:
            picks[task] = None
    return picks


if __name__ == "__main__":
    results = benchmark_all()
    out = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "fastest_per_task": pick_fastest_per_task(results),
    }
    out_path = Path("/var/lib/loop-master/model_benchmark.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(out_path)
