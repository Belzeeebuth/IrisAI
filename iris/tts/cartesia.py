"""Voix Cartesia Sonic (cloud) : très faible latence, émotions contrôlables (sonic-3), français natif.

Clé : https://play.cartesia.ai → API keys → ``CARTESIA_API_KEY``. Bibliothèque standard uniquement.
``POST https://api.cartesia.ai/tts/bytes`` avec ``X-API-Key`` et ``Cartesia-Version``.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from iris.audio.playback import play_pcm
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech, speak_streaming
from iris.tts.cache import TTSCache

log = logging.getLogger(__name__)

BASE_URL = "https://api.cartesia.ai"
SAMPLE_RATE = 24000
LANGUAGES = {
    "fr",
    "en",
    "de",
    "es",
    "pt",
    "it",
    "nl",
    "pl",
    "ru",
    "sv",
    "tr",
    "ja",
    "zh",
    "ko",
    "hi",
}


class CartesiaError(RuntimeError):
    pass


class CartesiaTTS:
    name = "cartesia"

    def __init__(
        self,
        cfg: TTSConfig,
        language: str = "fr",
        player: str = "auto",
        cache: TTSCache | None = None,
    ) -> None:
        self.cfg = cfg
        self.language = language
        self.player = player
        self.cache = cache
        self.api_key = (
            os.environ.get(cfg.cartesia_api_key_env, "") if cfg.cartesia_api_key_env else ""
        )
        if not self.api_key:
            raise CartesiaError(f"{cfg.cartesia_api_key_env} absent de l'environnement")
        self.sample_rate = SAMPLE_RATE
        log.info(
            "TTS Cartesia : modèle %s, voix %s",
            cfg.cartesia_model,
            cfg.cartesia_voice or "(non définie)",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
        timeout: float = 60,
    ) -> bytes:
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v not in (None, "")}
            )
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": self.cfg.cartesia_version,
            "User-Agent": "iris-assistant",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (401, 403):
                raise CartesiaError("clé Cartesia refusée") from exc
            if exc.code == 429:
                raise CartesiaError("quota Cartesia atteint") from exc
            raise CartesiaError(f"Cartesia HTTP {exc.code} : {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CartesiaError(f"connexion Cartesia impossible : {exc}") from exc

    def voices(self, language: str | None = "fr", limit: int = 100) -> list[dict]:
        raw = self._request("GET", "/voices", params={"limit": limit}, timeout=30)
        data = json.loads(raw)
        items = data.get("data", data) if isinstance(data, dict) else data
        result = []
        for v in items or []:
            if not isinstance(v, dict) or not v.get("id"):
                continue
            if language and v.get("language") and v.get("language") != language:
                continue
            result.append(
                {
                    "id": v["id"],
                    "name": v.get("name", ""),
                    "language": v.get("language", ""),
                    "description": v.get("description") or v.get("tagline") or "",
                    "gender": str(v.get("gender") or ""),
                    "owner": bool(v.get("is_owner")),
                }
            )
        return result

    def _payload(self, text: str, language: str | None) -> dict:
        if not self.cfg.cartesia_voice:
            raise CartesiaError(
                "tts.cartesia_voice n'est pas configuré (`iris voices list --engine cartesia --lang fr`)"
            )
        lang = language or self.language
        payload: dict = {
            "model_id": self.cfg.cartesia_model,
            "transcript": text,
            "voice": {"mode": "id", "id": self.cfg.cartesia_voice},
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": SAMPLE_RATE,
            },
        }
        if lang in LANGUAGES:
            payload["language"] = lang
        generation: dict = {}
        if self.cfg.cartesia_emotion:
            generation["emotion"] = self.cfg.cartesia_emotion
        if abs(self.cfg.cartesia_speed - 1.0) > 1e-6:
            generation["speed"] = self.cfg.cartesia_speed
        if generation:
            payload["generation_config"] = generation
        return payload

    def synthesize(self, text: str, language: str | None = None) -> tuple[bytes, int]:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return b"", SAMPLE_RATE

        def call() -> tuple[bytes, int]:
            return self._request(
                "POST", "/tts/bytes", body=self._payload(text, language)
            ), SAMPLE_RATE

        if self.cache is not None:
            key = self.cache.key(
                "cartesia",
                self.cfg.cartesia_model,
                self.cfg.cartesia_voice,
                self.cfg.cartesia_emotion,
                self.cfg.cartesia_speed,
                language or self.language,
                text,
            )
            return self.cache.fetch(key, call)
        return call()

    def speak(self, text: str, language: str | None = None) -> bool:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return False
        try:
            return speak_streaming(
                lambda sentence: self.synthesize(sentence, language),
                lambda pcm, rate: play_pcm(pcm, rate, player=self.player),
                text,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Synthèse Cartesia impossible : %s", exc)
            return False
