from unittest.mock import patch

import pytest

from hecate.reasoning_router import (
    DEFAULT_MODELS,
    OLLAMA_HOST,
    ReasoningError,
    ReasoningRouter,
    TaskType,
)


def test_default_models_cover_all_tasks():
    for task in TaskType:
        assert task in DEFAULT_MODELS, f"Missing model config for {task}"


def test_is_ollama_alive_true():
    with patch("hecate.reasoning_router.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = lambda *a: None
        router = ReasoningRouter()
        assert router.is_ollama_alive() is True
        mock_open.assert_called_once_with(f"{OLLAMA_HOST}/api/tags", timeout=5)


def test_is_ollama_alive_false():
    with patch("hecate.reasoning_router.urllib.request.urlopen", side_effect=Exception("boom")):
        router = ReasoningRouter()
        assert router.is_ollama_alive() is False


def test_generate_calls_ollama_generate():
    with patch("hecate.reasoning_router._ollama_generate") as mock_gen:
        mock_gen.return_value = "Antwort"
        router = ReasoningRouter()
        r = router.generate(TaskType.REASON, "Was ist HECATE?")
        assert r == "Antwort"
        mock_gen.assert_called_once()
        model, prompt, temp, timeout = mock_gen.call_args[0]
        assert model == DEFAULT_MODELS[TaskType.REASON].name
        assert "HECATE" in prompt


def test_generate_raises_on_error():
    with patch("hecate.reasoning_router._ollama_generate", side_effect=Exception("ollama down")):
        router = ReasoningRouter()
        with pytest.raises(ReasoningError, match="ollama down"):
            router.generate(TaskType.CLASSIFY, "x")


def test_classify_prompt_format():
    with patch("hecate.reasoning_router._ollama_generate") as mock_gen:
        mock_gen.return_value = "PRODUCT"
        router = ReasoningRouter()
        r = router.classify("Ein Content-Tool", ["PRODUCT", "EXPERIMENT", "ARCHIVE"])
        assert r == "PRODUCT"
        prompt = mock_gen.call_args[0][1]
        assert "Klassifiziere" in prompt
        assert "PRODUCT" in prompt
        assert "EXPERIMENT" in prompt


def test_embed_uses_cache(tmp_path):
    with patch("hecate.reasoning_router._ollama_embed") as mock_emb:
        mock_emb.return_value = [0.1, 0.2, 0.3]
        router = ReasoningRouter(cache_dir=tmp_path)
        vec = router.embed("hallo welt")
        assert vec == [0.1, 0.2, 0.3]
        # Zweiter Aufruf muss cache nutzen
        vec2 = router.embed("hallo welt")
        assert vec2 == vec
        assert mock_emb.call_count == 1


def test_truncate_limits_prompt_length():
    router = ReasoningRouter()
    short = router._build_prompt(TaskType.REASON, "kurz", "", 32000)
    assert short == "kurz"

    long_text = "x" * 20000
    truncated = router._build_prompt(TaskType.REASON, long_text, "", 32000)
    assert len(truncated) < 9000  # 32000/4 = 8000 plus Reserve
