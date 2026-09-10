import io
import json
import urllib.error
import urllib.request

import pytest

from iris.tts.cache import TTSCache
from iris.tts.cartesia import CartesiaError, CartesiaTTS
from iris.tts.elevenlabs import ElevenLabsError, ElevenLabsTTS, ElevenVoice
from iris.tts.factory import auto_order, build_tts

VOICES_JSON = {
    "voices": [
        {
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
            "name": "Sarah",
            "category": "premade",
            "labels": {"accent": "american", "gender": "female"},
        },
        {
            "voice_id": "XB0fDUlXrJqFMkgaVdrz",
            "name": "Charlotte",
            "category": "premade",
            "labels": {"accent": "swedish"},
        },
        {
            "voice_id": "abc123abc123abc123ab",
            "name": "Camille FR",
            "category": "cloned",
            "labels": {"language": "fr"},
        },
    ]
}
LIBRARY_JSON = {
    "voices": [
        {
            "public_owner_id": "owner1",
            "voice_id": "libvoice000000000001",
            "name": "Léa",
            "accent": "standard",
            "gender": "female",
            "age": "young",
            "descriptive": "warm",
            "use_case": "conversational",
            "category": "professional",
            "language": "fr",
            "description": "Voix française chaleureuse",
            "preview_url": "https://x/preview.mp3",
        },
    ]
}


class FakeHTTP:
    """Simule urllib.request.urlopen : enregistre les requêtes, renvoie des réponses préparées."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, dict | None]] = []
        self.responses: dict[str, bytes | dict | Exception] = {}

    def __call__(self, req, timeout=0):
        body = json.loads(req.data) if req.data else None
        self.calls.append((req.get_method(), req.full_url, dict(req.header_items()), body))
        for prefix, response in self.responses.items():
            if req.full_url.split("?")[0].endswith(prefix) or prefix in req.full_url:
                if isinstance(response, Exception):
                    raise response
                raw = response if isinstance(response, bytes) else json.dumps(response).encode()
                return _Resp(raw)
        raise AssertionError(f"réponse non préparée pour {req.full_url}")


class _Resp:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.headers = {"Content-Type": "audio/pcm"}
        self.status = 200

    def read(self) -> bytes:
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code: int, detail: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(detail.encode()))


@pytest.fixture
def http(monkeypatch, tmp_path):
    fake = FakeHTTP()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "ca-key")
    return fake


# ---------------------------------------------------------------- ElevenLabs
def test_elevenlabs_synthesize_request(http, cfg):
    http.responses["/v1/voices"] = VOICES_JSON
    http.responses["/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"] = b"\x01\x00" * 50
    tts = ElevenLabsTTS(cfg.tts, "fr")
    pcm, rate = tts.synthesize("Bonjour")
    assert pcm == b"\x01\x00" * 50 and rate == 24000
    method, url, headers, body = http.calls[-1]
    assert method == "POST" and url.startswith(
        "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL?output_format=pcm_24000"
    )
    assert headers["Xi-api-key"] == "el-key"
    assert body["model_id"] == "eleven_multilingual_v2" and body["text"] == "Bonjour"
    assert "language_code" not in body  # non supporté par multilingual_v2
    assert (
        body["voice_settings"]["stability"] == 0.45
        and body["voice_settings"]["use_speaker_boost"] is True
    )
    assert "speed" not in body["voice_settings"]


def test_elevenlabs_flash_language_code_and_continuity(http, cfg):
    cfg.tts.elevenlabs_model = "eleven_flash_v2_5"
    cfg.tts.elevenlabs_speed = 1.1
    cfg.tts.elevenlabs_voice = "abc123abc123abc123ab"  # identifiant direct : pas d'appel /v1/voices
    http.responses["/v1/text-to-speech/abc123abc123abc123ab"] = b"\x00\x00"
    tts = ElevenLabsTTS(cfg.tts, "fr", cache=None)
    tts.synthesize("Première phrase.")
    tts.synthesize("Deuxième phrase.")
    first, second = http.calls[-2][3], http.calls[-1][3]
    assert first["language_code"] == "fr" and "previous_text" not in first
    assert second["previous_text"] == "Première phrase."
    assert first["voice_settings"]["speed"] == 1.1
    assert not any("/v1/voices" in c[1] for c in http.calls)


def test_elevenlabs_v3_stability_snaps(http, cfg):
    cfg.tts.elevenlabs_model = "eleven_v3"
    cfg.tts.elevenlabs_stability = 0.3
    cfg.tts.elevenlabs_voice = "abc123abc123abc123ab"
    settings = ElevenLabsTTS(cfg.tts).voice_settings()
    assert settings["stability"] == 0.5 and "style" not in settings


def test_elevenlabs_voice_resolution(http, cfg):
    http.responses["/v1/voices"] = VOICES_JSON
    tts = ElevenLabsTTS(cfg.tts)
    assert tts.resolve_voice("charlotte") == "XB0fDUlXrJqFMkgaVdrz"
    assert tts.resolve_voice("Camille") == "abc123abc123abc123ab"  # flou
    assert tts.resolve_voice("XB0fDUlXrJqFMkgaVdrz") == "XB0fDUlXrJqFMkgaVdrz"
    with pytest.raises(ElevenLabsError, match="introuvable"):
        tts.resolve_voice("Zorglub")
    assert sum("/v1/voices" in c[1] for c in http.calls) == 1  # cache disque des voix


def test_elevenlabs_library_and_add(http, cfg):
    http.responses["/v1/shared-voices"] = LIBRARY_JSON
    http.responses["/v1/voices/add/owner1/libvoice000000000001"] = {
        "voice_id": "newvoice0000000000001"
    }
    http.responses["/v1/voices"] = VOICES_JSON
    tts = ElevenLabsTTS(cfg.tts)
    found = tts.library("fr", gender="female")
    assert (
        found[0].name == "Léa"
        and found[0].public_owner_id == "owner1"
        and found[0].labels["language"] == "fr"
    )
    assert "language=fr" in http.calls[-1][1] and "gender=female" in http.calls[-1][1]
    assert tts.add_from_library("owner1", "libvoice000000000001", "Léa") == "newvoice0000000000001"
    assert http.calls[-2][3] == {"new_name": "Léa"}


def test_elevenlabs_errors(http, cfg):
    cfg.tts.elevenlabs_voice = "abc123abc123abc123ab"
    tts = ElevenLabsTTS(cfg.tts, cache=None)
    http.responses["/v1/text-to-speech/abc123abc123abc123ab"] = http_error(401)
    with pytest.raises(ElevenLabsError, match="refusée"):
        tts.synthesize("x")
    http.responses["/v1/text-to-speech/abc123abc123abc123ab"] = http_error(429, "quota")
    with pytest.raises(ElevenLabsError, match="quota"):
        tts.synthesize("x")
    assert tts.speak("x") is False  # speak() ne lève jamais


def test_elevenlabs_requires_key(monkeypatch, cfg):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTS(cfg.tts)
    cfg.tts.elevenlabs_api_key = "inline"
    assert ElevenLabsTTS(cfg.tts).api_key == "inline"


def test_elevenlabs_uses_cache(http, cfg, tmp_path):
    cfg.tts.elevenlabs_voice = "abc123abc123abc123ab"
    http.responses["/v1/text-to-speech/abc123abc123abc123ab"] = b"\x05\x00" * 10
    cache = TTSCache(tmp_path / "tts")
    tts = ElevenLabsTTS(cfg.tts, cache=cache)
    tts.synthesize("Oui ?")
    tts._previous_text = ""
    tts.synthesize("Oui ?")
    assert sum("text-to-speech" in c[1] for c in http.calls) == 1
    assert cache.hits == 1 and cache.misses == 1


# ---------------------------------------------------------------- Cartesia
def test_cartesia_synthesize(http, cfg):
    cfg.tts.cartesia_voice = "voice-uuid"
    cfg.tts.cartesia_emotion = "content"
    http.responses["/tts/bytes"] = b"\x02\x00" * 20
    tts = CartesiaTTS(cfg.tts, "fr", cache=None)
    pcm, rate = tts.synthesize("Bonjour")
    assert pcm == b"\x02\x00" * 20 and rate == 24000
    method, url, headers, body = http.calls[-1]
    assert (
        url == "https://api.cartesia.ai/tts/bytes"
        and headers["X-api-key"] == "ca-key"
        and headers["Cartesia-version"] == "2026-08-14"
    )
    assert (
        body["model_id"] == "sonic-3"
        and body["voice"] == {"mode": "id", "id": "voice-uuid"}
        and body["language"] == "fr"
    )
    assert body["output_format"] == {
        "container": "raw",
        "encoding": "pcm_s16le",
        "sample_rate": 24000,
    }
    assert body["generation_config"] == {"emotion": "content"}


def test_cartesia_voices_and_errors(http, cfg):
    http.responses["/voices"] = {
        "data": [
            {"id": "v1", "name": "Hélène", "language": "fr", "tagline": "chaleureuse"},
            {"id": "v2", "name": "Bob", "language": "en"},
        ]
    }
    tts = CartesiaTTS(cfg.tts)
    assert [v["name"] for v in tts.voices("fr")] == ["Hélène"]
    with pytest.raises(CartesiaError, match="cartesia_voice"):
        tts.synthesize("x")


# ---------------------------------------------------------------- cache
def test_cache_roundtrip_and_prune(tmp_path):
    cache = TTSCache(tmp_path / "tts", max_mb=1)
    key = cache.key("a", "b", "Oui ?")
    assert cache.get(key) is None
    cache.put(key, b"\x00" * 1000, 24000)
    assert cache.get(key) == (b"\x00" * 1000, 24000)
    pcm, rate = cache.fetch(key, lambda: (b"neuf", 1))
    assert pcm == b"\x00" * 1000
    for i in range(3):
        cache.put(cache.key("big", i), b"\x00" * 600_000, 24000)
    assert cache.size_bytes() <= 1_048_576
    assert cache.clear() > 0 and cache.size_bytes() == 0
    disabled = TTSCache(tmp_path / "off", enabled=False)
    disabled.put("k", b"x", 1)
    assert disabled.get("k") is None


# ---------------------------------------------------------------- factory
def test_auto_order_prefers_elevenlabs_when_key_and_cloud(monkeypatch, cfg):
    for var in ("ELEVENLABS_API_KEY", "OPENAI_API_KEY", "CARTESIA_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert auto_order(cfg) == ["kokoro", "piper", "espeak"]
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert auto_order(cfg) == ["kokoro", "piper", "espeak"]  # allow_cloud = false
    cfg.privacy.allow_cloud = True
    assert auto_order(cfg) == ["elevenlabs", "openai", "kokoro", "piper", "espeak"]
    monkeypatch.setenv("CARTESIA_API_KEY", "k")
    assert auto_order(cfg)[:3] == ["elevenlabs", "openai", "cartesia"]
    cfg.tts.openai_base_url = "http://localhost:8880/v1"
    cfg.privacy.allow_cloud = False
    assert auto_order(cfg) == ["openai", "kokoro", "piper", "espeak"]


def test_build_tts_auto_picks_elevenlabs(http, cfg):
    cfg.privacy.allow_cloud = True
    assert build_tts(cfg).name == "elevenlabs"
    cfg.tts.backend = "cartesia"
    assert build_tts(cfg).name == "cartesia"
    cfg.tts.backend = "elevenlabs"
    cfg.privacy.allow_cloud = False
    with pytest.raises(RuntimeError, match="allow_cloud"):
        build_tts(cfg)


def test_elevenvoice_summary():
    v = ElevenVoice("id", "Léa", "cloned", {"language": "fr", "gender": "female"}, "desc")
    assert "Léa" in v.summary() and "fr" in v.summary()
