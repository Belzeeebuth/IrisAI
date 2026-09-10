"""Voix IA locale : Kokoro-82M via ``kokoro-onnx`` (ONNX Runtime, CPU, 24 kHz).

Bien plus naturelle que Piper, sans réseau. Français : voix ``ff_siwis`` (``lang="fr-fr"``) ;
anglais : ``af_heart``, ``af_bella``, ``am_michael``… Le modèle reste chargé en mémoire.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from iris.audio.playback import play_pcm
from iris.audio.wavutil import float32_to_int16
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech, speak_streaming
from iris.tts.voices import kokoro_files

log = logging.getLogger(__name__)

DEFAULT_VOICES = {"fr": "ff_siwis", "en": "af_heart"}
LANG_CODES = {"fr": "fr-fr", "en": "en-us"}


class KokoroTTS:
    name = "kokoro"

    def __init__(self, cfg: TTSConfig, language: str = "fr", player: str = "auto") -> None:
        self.cfg = cfg
        self.player = player
        self.language = language if language in DEFAULT_VOICES else "fr"
        files = kokoro_files(cfg.kokoro_model, cfg.kokoro_models_dir)
        if files is None:
            raise RuntimeError(
                f"Modèle Kokoro « {cfg.kokoro_model} » introuvable — `iris voices download kokoro`"
            )
        self.model_path, self.voices_path = files
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "kokoro-onnx n'est pas installé : pip install 'iris-assistant[voice]'"
            ) from exc
        self._engine = None
        self.sample_rate = 24000
        log.info("TTS Kokoro : %s (voix %s)", self.model_path.name, self.voice_for(self.language))

    # ------------------------------------------------------------------ interne
    def _load(self):
        if self._engine is None:
            from kokoro_onnx import Kokoro

            started = time.monotonic()
            self._engine = Kokoro(str(self.model_path), str(self.voices_path))
            log.info("Kokoro chargé en %.1fs", time.monotonic() - started)
        return self._engine

    def voice_for(self, language: str) -> str:
        return self.cfg.kokoro_voice or DEFAULT_VOICES.get(language, DEFAULT_VOICES["fr"])

    def lang_code(self, language: str) -> str:
        return self.cfg.kokoro_lang or LANG_CODES.get(language, "fr-fr")

    # ------------------------------------------------------------------ public
    def voices(self) -> list[str]:
        return list(self._load().get_voices())

    def synthesize(self, text: str, language: str | None = None) -> tuple[bytes, int]:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return b"", self.sample_rate
        language = language or self.language
        engine = self._load()
        audio, rate = engine.create(
            text,
            voice=self.voice_for(language),
            speed=self.cfg.kokoro_speed,
            lang=self.lang_code(language),
        )
        self.sample_rate = int(rate)
        return float32_to_int16(np.asarray(audio, dtype=np.float32)).tobytes(), self.sample_rate

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
            log.error("Synthèse Kokoro impossible : %s", exc)
            return False


def resolve_kokoro_path(cfg: TTSConfig) -> Path | None:
    files = kokoro_files(cfg.kokoro_model, cfg.kokoro_models_dir)
    return files[0] if files else None
