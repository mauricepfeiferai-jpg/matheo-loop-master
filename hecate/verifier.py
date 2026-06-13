"""Verifier — Hecate sub-agent for grading maker output against a rubric.

Runs a SEPARATE LLM call via model_router with complexity="grader".
The grader sees ONLY the artifact + rubric, never the maker's reasoning
or system prompt. Returns structured verdict with score, gaps, and suggestions.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

# model_router lives in content-engine/lib; import via sys.path
sys.path.insert(0, str(Path("/root/projects/content-engine/lib").resolve()))

from model_router import chat  # type: ignore[import-untyped]


@dataclass(frozen=True)
class Verdict:
    """Structured result of a verification run."""

    verdict: str          # "pass" or "fail"
    score: int            # 0–100
    gaps: list[str]       # Criteria that failed
    suggestions: list[str]  # Concrete improvement hints


# ─────────────────────────────────────────
# System prompt for the grader model
# ─────────────────────────────────────────

_GRADER_SYSTEM = """You are an impartial verifier.
Your job is to grade an artifact against a rubric.
You receive ONLY the artifact and the rubric — nothing about the maker,
no reasoning chains, no system prompts. Be strict but fair.

Output ONLY valid JSON in this exact shape (no markdown, no commentary):
{
  "verdict": "pass" or "fail",
  "score": integer 0–100,
  "gaps": ["short description of each failed criterion"],
  "suggestions": ["concrete, actionable improvement"]
}"""


# ─────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────

_TEMPLATE = """ARTIFACT TYPE: {artifact_type}

--- ARTIFACT ---
{artifact}

--- RUBRIC ---
{rubric_text}

Grade the artifact against every rubric criterion.
Return ONLY the JSON object described in your instructions.
"""


def _build_prompt(artifact: str, rubric: list[str], artifact_type: str) -> str:
    rubric_numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(rubric))
    return _TEMPLATE.format(
        artifact_type=artifact_type,
        artifact=artifact.strip(),
        rubric_text=rubric_numbered,
    )


# ─────────────────────────────────────────
# JSON extraction / parsing
# ─────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """Grab first JSON object from raw LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        # fenced code block
        lines = raw.splitlines()
        # drop opening fence
        if lines[0].startswith("```"):
            lines = lines[1:]
        # drop closing fence
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def _parse_response(raw: str) -> Verdict:
    """Parse grader JSON into a Verdict dataclass."""
    payload = _extract_json(raw)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Grader returned invalid JSON: {exc}") from exc

    verdict = "pass" if str(data.get("verdict", "")).lower() == "pass" else "fail"
    score = max(0, min(100, int(data.get("score", 0))))
    gaps = [str(g) for g in data.get("gaps", []) if g]
    suggestions = [str(s) for s in data.get("suggestions", []) if s]

    return Verdict(verdict=verdict, score=score, gaps=gaps, suggestions=suggestions)


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────

def verify(
    artifact: str,
    rubric: list[str],
    *,
    artifact_type: str = "code",
    complexity: str = "grader",
) -> Verdict:
    """Grade *artifact* against *rubric* using a detached grader model.

    Args:
        artifact: The maker output to evaluate (code, text, report).
        rubric: Ordered list of criteria strings.
        artifact_type: Label for the prompt (e.g. "code", "report", "text").
        complexity: Router role; defaults to "grader".

    Returns:
        Verdict with verdict, score, gaps, and suggestions.
    """
    if not rubric:
        raise ValueError("Rubric must contain at least one criterion.")

    user_prompt = _build_prompt(artifact, rubric, artifact_type)
    raw, label = chat(_GRADER_SYSTEM, user_prompt, complexity=complexity)

    if raw is None:
        raise RuntimeError(f"Grader LLM call failed (label={label}).")

    return _parse_response(raw)


# ─────────────────────────────────────────
# CLI test mode
# ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hecate Verifier — CLI test mode")
    parser.add_argument("--artifact", "-a", required=True, help="Path to artifact file")
    parser.add_argument("--rubric", "-r", required=True, help="Path to rubric file (one criterion per line)")
    parser.add_argument("--type", "-t", default="code", help="Artifact type label")
    parser.add_argument("--complexity", "-c", default="grader", help="Router complexity role")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    rubric_path = Path(args.rubric)

    if not artifact_path.exists():
        parser.error(f"Artifact file not found: {artifact_path}")
    if not rubric_path.exists():
        parser.error(f"Rubric file not found: {rubric_path}")

    artifact_text = artifact_path.read_text(encoding="utf-8")
    rubric_lines = [
        line.strip()
        for line in rubric_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    print(f"[Verifier] Artifact: {artifact_path} ({len(artifact_text)} chars)")
    print(f"[Verifier] Rubric:   {rubric_path} ({len(rubric_lines)} criteria)")
    print(f"[Verifier] Type:     {args.type}")
    print(f"[Verifier] Role:     {args.complexity}")
    print("-" * 40)

    try:
        result = verify(
            artifact_text,
            rubric_lines,
            artifact_type=args.type,
            complexity=args.complexity,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Verdict:      {result.verdict}")
    print(f"Score:        {result.score}/100")
    print(f"Gaps ({len(result.gaps)}):")
    for gap in result.gaps:
        print(f"  - {gap}")
    print(f"Suggestions ({len(result.suggestions)}):")
    for suggestion in result.suggestions:
        print(f"  - {suggestion}")
