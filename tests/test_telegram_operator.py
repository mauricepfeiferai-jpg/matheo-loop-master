from pathlib import Path
from unittest.mock import MagicMock, patch

from hecate.telegram_operator import TelegramOperator


def test_authorized_owner_only():
    op = TelegramOperator(router=MagicMock())
    assert op._authorized("8531161985") is True
    assert op._authorized("123456") is False


def test_chunks_splits_long_text():
    op = TelegramOperator(router=MagicMock())
    chunks = op._chunks("a" * 5000, limit=4000)
    assert len(chunks) > 1
    assert all(len(c) <= 4000 for c in chunks)


def test_handle_vision_command():
    router = MagicMock()
    with patch("hecate.telegram_operator.VisionEngine.generate_vision") as mock_vision:
        mock_vision.return_value = {
            "proposal_id": "hecate-vision-test",
            "title": "Test Vision",
            "summary": "Test summary",
            "path": "/tmp/test.md",
        }
        op = TelegramOperator(router=router)
        sent = []
        op._send = lambda chat_id, text, buttons=None: sent.append((chat_id, text, buttons)) or True
        op.handle(OWNER_ID_DEFAULT := "8531161985", "/vision bessere Sensoren")
        assert len(sent) == 1
        chat, text, buttons = sent[0]
        assert "VISION-PROPOSAL" in text
        assert buttons is not None


def test_handle_think_command():
    router = MagicMock()
    router.generate.return_value = "Weil HECATE lokal denken soll."
    op = TelegramOperator(router=router)
    sent = []
    op._send = lambda chat_id, text, buttons=None: sent.append(text) or True
    op.handle("8531161985", "/think Warum lokal?")
    assert len(sent) == 1
    assert "Weil HECATE" in sent[0]


def test_handle_freitext_uses_memory():
    router = MagicMock()
    router.generate.return_value = "Option A, B, C"
    op = TelegramOperator(router=router)
    sent = []
    op._send = lambda chat_id, text, buttons=None: sent.append(text) or True
    op.handle("8531161985", "Was meinst du zu dem neuen Sensor-Konzept?")
    assert len(sent) == 1
    assert "Option A" in sent[0]
