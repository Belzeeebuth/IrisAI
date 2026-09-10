"""Voix cloud ElevenLabs (optionnelle ; nécessite ELEVENLABS_API_KEY et privacy.allow_cloud)."""

from __future__ import annotations

import logging
import os

from iris.audio.playback import play_pcm
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050


class ElevenLabsTTS:
    name = "elevenlabs"

    def __init__(self, cfg: TTSConfig, player: str = "auto") -> None:
        self.cfg = cfg
        self.player = player
        self.api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY absent de l'environnement")
        if not cfg.elevenlabs_voice_id:
            raise RuntimeError("tts.elevenlabs_voice_id n'est pas configuré")

    def synthesize(self, text: str) -> bytes:
        import requests

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}"
        resp = requests.post(
            url,
            params={"output_format": f"pcm_{SAMPLE_RATE}"},
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": self.cfg.elevenlabs_model},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content

    def speak(self, text: str) -> bool:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return False
        try:
            pcm = self.synthesize(text)
        except Exception as exc:
            log.error("ElevenLabs a échoué : %s", exc)
            return False
        return play_pcm(pcm, SAMPLE_RATE, player=self.player)
