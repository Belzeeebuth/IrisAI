"""Voix IA via un endpoint OpenAI-compatible ``POST {base_url}/audio/speech``.

Fonctionne avec :
- OpenAI (``gpt-4o-mini-tts`` : voix expressives pilotables par ``instructions``) ;
- des serveurs locaux compatibles : Kokoro-FastAPI (http://localhost:8880/v1), Speaches, LM Studio…

Le flux est demandé en PCM 16 bits mono 24 kHz (``response_format = "pcm"``) ; repli WAV si le
serveur ne connaît pas ``pcm``. Bibliothèque standard uniquement (urllib).
"""

from __future__ import annotations

import io
import json
import logging
import os
import urllib.error
import urllib.request
import wave

from iris.audio.playback import play_pcm
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech, speak_streaming

log = logging.getLogger(__name__)

PCM_RATE = 24000

STYLE_BY_TONE = {
    "fr": {
        "warm": "Parle en français, d'une voix chaleureuse, naturelle et posée, avec un léger sourire. "
        "Assistante bienveillante, jamais robotique.",
        "direct": "Parle en français, d'une voix claire, directe et efficace, sans emphase inutile.",
        "coach": "Parle en français, d'une voix énergique et encourageante, comme une coach motivante.",
    },
    "en": {
        "warm": "Speak warmly and naturally, calm and friendly, with a slight smile. Never robotic.",
        "direct": "Speak clearly, directly and efficiently, without unnecessary emphasis.",
        "coach": "Speak with energy and encouragement, like a motivating coach.",
    },
}


class OpenAISpeechTTS:
    name = "openai"

    def __init__(
        self,
        cfg: TTSConfig,
        language: str = "fr",
        tone: str = "warm",
        player: str = "auto",
        cache=None,
    ) -> None:
        self.cfg = cfg
        self.player = player
        self.cache = cache
        self.language = language if language in STYLE_BY_TONE else "fr"
        self.tone = tone
        self.base_url = cfg.openai_base_url.rstrip("/")
        self.api_key = os.environ.get(cfg.openai_api_key_env, "") if cfg.openai_api_key_env else ""
        if not self.api_key and not is_local_url(self.base_url):
            raise RuntimeError(f"{cfg.openai_api_key_env} absent de l'environnement")
        log.info(
            "TTS OpenAI-compatible : %s (%s, voix %s)",
            self.base_url,
            cfg.openai_model,
            cfg.openai_voice,
        )

    def instructions(self, language: str | None = None) -> str:
        if self.cfg.openai_instructions:
            return self.cfg.openai_instructions
        table = STYLE_BY_TONE.get(language or self.language, STYLE_BY_TONE["fr"])
        return table.get(self.tone, table["warm"])

    def _request(self, payload: dict, timeout: float = 60) -> tuple[bytes, str]:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "iris-assistant"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/audio/speech", data=data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.read(), resp.headers.get("Content-Type", "")

    def synthesize(self, text: str, language: str | None = None) -> tuple[bytes, int]:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return b"", PCM_RATE
        if self.cache is not None:
            key = self.cache.key(
                "openai",
                self.base_url,
                self.cfg.openai_model,
                self.cfg.openai_voice,
                self.instructions(language),
                self.cfg.openai_speed,
                text,
            )
            return self.cache.fetch(key, lambda: self._synthesize(text, language))
        return self._synthesize(text, language)

    def _synthesize(self, text: str, language: str | None) -> tuple[bytes, int]:
        payload = {
            "model": self.cfg.openai_model,
            "input": text,
            "voice": self.cfg.openai_voice,
            "response_format": "pcm",
            "speed": self.cfg.openai_speed,
        }
        instructions = self.instructions(language)
        if instructions and self.cfg.openai_model.startswith(("gpt-", "tts-")):
            payload["instructions"] = instructions
        try:
            body, content_type = self._request(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            if exc.code in (400, 422) and "pcm" in detail.lower():
                payload["response_format"] = "wav"
                body, content_type = self._request(payload)
            else:
                raise RuntimeError(f"HTTP {exc.code} : {detail}") from exc
        if body[:4] == b"RIFF" or "wav" in content_type:
            with wave.open(io.BytesIO(body), "rb") as w:
                return w.readframes(w.getnframes()), w.getframerate()
        return body, PCM_RATE

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
            log.error("Synthèse OpenAI-compatible impossible : %s", exc)
            return False


def is_local_url(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":")[0].lower()
    return (
        host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
        or host.endswith(".local")
        or host.startswith("192.168.")
        or host.startswith("10.")
    )
