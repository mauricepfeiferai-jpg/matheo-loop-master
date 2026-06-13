#!/usr/bin/env python3
"""Benchmark lokale Modelle fuer HECATE-Aufgaben."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from hecate.reasoning_router import OLLAMA_HOST, TaskType
import urllib.request

PROMPTS = {
    TaskType.CLASSIFY: "Classify only as hardware/config/security: disk 95% full",
    TaskType.CODE_ANALYZE: "Review this function: def add(a,b): return a+b. One risk.",
    TaskType.REASON: "Server load is 8.0. List 3 possible causes, max 30 words.",
    TaskType.VERIFY: "Claim: Earth is flat. Evidence: NASA images. Answer TRUE/FALSE.",
    TaskType.VISION: "Propose one improvement for a self-healing server agent. Max 50 words.",
}

MODELS = {
    TaskType.CLASSIFY: ["qwen2.5:0.5b", "qwen2.5:1.5b"],
    TaskType.CODE_ANALYZE: ["qwen2.5-coder:7b"],
    TaskType.REASON: ["qwen3:8b"],
    TaskType.VERIFY: ["qwen2.5-coder:7b"],
    TaskType.VISION: ["qwen3:8b"],
}


def _generate(model: str, prompt: str, timeout: int = 120) -> dict:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0.2}}).encode()
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            elapsed = time.perf_counter() - start
            return {"model": model, "ok": True, "response": data.get("response", "")[:120],
                    "elapsed": round(elapsed, 2), "tokens": data.get("eval_count", 0)}
    except Exception as exc:
        return {"model": model, "ok": False, "error": str(exc)[:120], "elapsed": timeout}


def benchmark(task: TaskType) -> list[dict]:
    prompt = PROMPTS[task]
    results = []
    for model in MODELS[task]:
        results.append(_generate(model, prompt))
    return results


def benchmark_all() -> dict:
    out = {}
    for task in MODELS:
        print(f"Benchmarking {task.value}...")
        out[task.value] = benchmark(task)
    return out


if __name__ == "__main__":
    results = benchmark_all()
    out_path = Path("/var/lib/loop-master/model_benchmark.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(out_path)
