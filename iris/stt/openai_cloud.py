"""Fallback cloud : API Whisper d'OpenAI (désactivé par défaut, nécessite privacy.allow_cloud)."""

from __future__ import annotations

import logging
import os

import numpy as np

from iris.audio.wavutil import pcm_to_wav_bytes
from iris.config import STTConfig
from iris.stt.base import is_hallucination

log = logging.getLogger(__name__)


class OpenAIWhisperSTT:
    name = "openai"

    def __init__(self, cfg: STTConfig) -> None:
        self.cfg = cfg
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY absent de l'environnement")

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        import requests

        wav = pcm_to_wav_bytes(audio.astype(np.int16).tobytes(), sample_rate)
        data = {"model": self.cfg.openai_model, "response_format": "text"}
        if language:
            data["language"] = language
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": ("audio.wav", wav, "audio/wav")},
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        return "" if is_hallucination(text) else text
