"""Transcription locale avec faster-whisper (CTranslate2).

Le modèle est chargé paresseusement au premier appel (téléchargé depuis Hugging Face
la première fois, puis mis en cache dans ~/.cache/huggingface).
"""

from __future__ import annotations

import logging
import time

import numpy as np

from iris.audio.wavutil import int16_to_float32
from iris.config import STTConfig
from iris.stt.base import is_hallucination

log = logging.getLogger(__name__)


class FasterWhisperSTT:
    name = "faster-whisper"

    def __init__(self, cfg: STTConfig, hotwords: str | None = "Iris") -> None:
        self.cfg = cfg
        self.hotwords = hotwords
        self._model = None
        self.last_language: str | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "faster-whisper n'est pas installé : pip install 'iris-assistant[stt]'"
            ) from exc
        started = time.monotonic()
        log.info(
            "Chargement du modèle Whisper « %s » (%s, %s)…",
            self.cfg.model,
            self.cfg.device,
            self.cfg.compute_type,
        )
        self._model = WhisperModel(
            self.cfg.model, device=self.cfg.device, compute_type=self.cfg.compute_type
        )
        log.info("Modèle Whisper prêt en %.1fs", time.monotonic() - started)

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        self.load()
        assert self._model is not None
        if sample_rate != 16000:
            audio = _resample(audio, sample_rate, 16000)
        samples = int16_to_float32(audio)
        if samples.size < 1600:  # < 0,1 s
            return ""
        segments, info = self._model.transcribe(
            samples,
            language=language,
            beam_size=self.cfg.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
            hotwords=self.hotwords,
        )
        parts: list[str] = []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0.0) > 0.7:
                continue
            parts.append(seg.text.strip())
        text = " ".join(p for p in parts if p).strip()
        self.last_language = getattr(info, "language", None)
        if is_hallucination(text):
            log.debug("Transcription ignorée (hallucination probable) : %r", text)
            return ""
        log.debug("Transcription (%s, p=%.2f) : %r", info.language, info.language_probability, text)
        return text


def _resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Ré-échantillonnage linéaire simple (suffisant pour la parole)."""
    if src == dst or audio.size == 0:
        return audio
    duration = audio.shape[0] / src
    n = int(duration * dst)
    x_old = np.linspace(0, duration, audio.shape[0], endpoint=False)
    x_new = np.linspace(0, duration, n, endpoint=False)
    return np.interp(x_new, x_old, audio.astype(np.float32)).astype(audio.dtype)
