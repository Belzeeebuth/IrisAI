import io
import json
import urllib.request
import wave

import pytest

from iris.tts.base import speak_streaming, split_sentences
from iris.tts.factory import build_tts
from iris.tts.openai_speech import OpenAISpeechTTS, is_local_url


def test_split_sentences():
    assert split_sentences(
        "Workspace lancé. Projet ouvert dans ton éditeur. Veux-tu que je lance aussi les agents ? Oui."
    ) == [
        "Workspace lancé. Projet ouvert dans ton éditeur.",
        "Veux-tu que je lance aussi les agents ? Oui.",
    ]
    assert split_sentences("Court.") == ["Court."]
    assert split_sentences("") == []


def test_speak_streaming_pipeline():
    played: list[str] = []

    def synth(sentence):
        return sentence.encode(), 24000

    def play(pcm, rate):
        played.append(pcm.decode())
        return True

    text = "Première phrase assez longue pour rester seule ici. Deuxième phrase également longue pour le test. Troisième phrase encore plus longue que les autres !"
    assert speak_streaming(synth, play, text) is True
    assert played == split_sentences(text)


def test_speak_streaming_propagates_errors():
    def synth(sentence):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        speak_streaming(
            synth,
            lambda *_: True,
            "Une phrase assez longue pour le test numéro un. Une deuxième phrase assez longue également.",
        )


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "audio/pcm") -> None:
        self.body = body
        self.headers = {"Content-Type": content_type}
        self.status = 200

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_openai_speech_synthesize(monkeypatch, cfg):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["payload"] = json.loads(req.data)
        return FakeResponse(b"\x00\x01" * 100)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    tts = OpenAISpeechTTS(cfg.tts, language="fr", tone="direct")
    pcm, rate = tts.synthesize("Bonjour")
    assert pcm == b"\x00\x01" * 100 and rate == 24000
    assert captured["url"] == "https://api.openai.com/v1/audio/speech"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert (
        captured["payload"]["model"] == "gpt-4o-mini-tts"
        and captured["payload"]["response_format"] == "pcm"
    )
    assert "directe" in captured["payload"]["instructions"]


def test_openai_speech_wav_response(monkeypatch, cfg):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x02\x00" * 10)
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=0: FakeResponse(buf.getvalue(), "audio/wav")
    )
    pcm, rate = OpenAISpeechTTS(cfg.tts).synthesize("x")
    assert rate == 22050 and pcm == b"\x02\x00" * 10


def test_openai_speech_requires_key_unless_local(monkeypatch, cfg):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAISpeechTTS(cfg.tts)
    cfg.tts.openai_base_url = "http://localhost:8880/v1"
    assert OpenAISpeechTTS(cfg.tts).api_key == ""
    assert is_local_url("http://127.0.0.1:8880/v1") and not is_local_url(
        "https://api.openai.com/v1"
    )


def test_factory_openai_backend_cloud_gate(monkeypatch, cfg):
    cfg.tts.backend = "openai"
    with pytest.raises(RuntimeError, match="allow_cloud"):
        build_tts(cfg)
    cfg.tts.openai_base_url = "http://localhost:8880/v1"
    assert build_tts(cfg).name == "openai"
    cfg.tts.backend = "kokoro"
    with pytest.raises(RuntimeError, match="Kokoro"):
        build_tts(cfg)  # modèle absent dans l'environnement de test
