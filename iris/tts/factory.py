from __future__ import annotations

import logging

from iris.config import Config
from iris.tts.console import ConsoleTTS, NullTTS

log = logging.getLogger(__name__)


def build_tts(cfg: Config, prefer_console: bool = False):
    """Construit le backend TTS selon la config (auto : piper → espeak → console)."""
    if prefer_console:
        return ConsoleTTS()
    backend = cfg.tts.backend
    player = cfg.audio.player

    if backend == "none":
        return NullTTS()
    if backend == "console":
        return ConsoleTTS()

    if backend in ("elevenlabs",):
        if not cfg.privacy.allow_cloud:
            raise RuntimeError("tts.backend = 'elevenlabs' nécessite privacy.allow_cloud = true")
        from iris.tts.elevenlabs import ElevenLabsTTS

        return ElevenLabsTTS(cfg.tts, player)

    errors: list[str] = []
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
