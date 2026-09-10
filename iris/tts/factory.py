from __future__ import annotations

import logging

from iris.config import Config
from iris.tts.console import ConsoleTTS, NullTTS

log = logging.getLogger(__name__)


def build_tts(cfg: Config, prefer_console: bool = False):
    """Construit le backend TTS selon la config (auto : kokoro → piper → espeak → console)."""
    if prefer_console:
        return ConsoleTTS()
    backend = cfg.tts.backend
    player = cfg.audio.player
    language = cfg.reply_language

    if backend == "none":
        return NullTTS()
    if backend == "console":
        return ConsoleTTS()

    if backend == "elevenlabs":
        if not cfg.privacy.allow_cloud:
            raise RuntimeError("tts.backend = 'elevenlabs' nécessite privacy.allow_cloud = true")
        from iris.tts.elevenlabs import ElevenLabsTTS

        return ElevenLabsTTS(cfg.tts, player)

    if backend == "openai":
        from iris.tts.openai_speech import OpenAISpeechTTS, is_local_url

        if not cfg.privacy.allow_cloud and not is_local_url(cfg.tts.openai_base_url):
            raise RuntimeError(
                "tts.backend = 'openai' vers un serveur distant nécessite privacy.allow_cloud = true"
            )
        return OpenAISpeechTTS(cfg.tts, language, cfg.assistant.tone, player)

    errors: list[str] = []
    if backend in ("auto", "kokoro"):
        try:
            from iris.tts.kokoro import KokoroTTS

            return KokoroTTS(cfg.tts, language, player)
        except Exception as exc:
            errors.append(f"kokoro: {exc}")
            if backend == "kokoro":
                raise
    if backend in ("auto", "piper"):
        try:
            from iris.tts.piper import PiperTTS

            return PiperTTS(cfg.tts, player)
        except Exception as exc:
            errors.append(f"piper: {exc}")
            if backend == "piper":
                raise
    if backend in ("auto", "espeak"):
        try:
            from iris.tts.espeak import EspeakTTS

            return EspeakTTS(cfg.tts)
        except Exception as exc:
            errors.append(f"espeak: {exc}")
            if backend == "espeak":
                raise
    log.warning(
        "Aucune voix disponible (%s) — réponses affichées dans la console", " ; ".join(errors)
    )
    return ConsoleTTS()
