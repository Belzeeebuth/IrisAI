from __future__ import annotations

import logging

import numpy as np

from iris.config import Config

log = logging.getLogger(__name__)


class FallbackSTT:
    """Essaie le moteur principal, bascule sur le secondaire en cas d'erreur."""

    def __init__(self, primary, fallback) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}+{fallback.name}"

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        try:
            return self.primary.transcribe(audio, sample_rate, language)
        except Exception as exc:
            log.warning(
                "STT %s en échec (%s), bascule sur %s", self.primary.name, exc, self.fallback.name
            )
            return self.fallback.transcribe(audio, sample_rate, language)


class NullSTT:
    name = "none"

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        return ""


def build_stt(cfg: Config):
    backend = cfg.stt.backend
    cloud_ok = cfg.privacy.allow_cloud

    if backend == "none":
        return NullSTT()

    if backend == "openai":
        if not cloud_ok:
            raise RuntimeError("stt.backend = 'openai' nécessite privacy.allow_cloud = true")
        from iris.stt.openai_cloud import OpenAIWhisperSTT

        return OpenAIWhisperSTT(cfg.stt)

    from iris.stt.faster_whisper import FasterWhisperSTT

    local = FasterWhisperSTT(cfg.stt)
    if cfg.stt.cloud_fallback and cloud_ok:
        try:
            from iris.stt.openai_cloud import OpenAIWhisperSTT

            return FallbackSTT(local, OpenAIWhisperSTT(cfg.stt))
        except Exception as exc:
            log.warning("Fallback cloud STT indisponible : %s", exc)
    return local
