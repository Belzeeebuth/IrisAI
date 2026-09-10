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

_CUDA_MARKERS = ("cublas", "cudnn", "cuda", "libcudart", "nvidia")


def cuda_usable() -> bool:
    """CUDA n'est utilisable que si les bibliothèques NVIDIA sont chargeables (cuBLAS 12 + cuDNN)."""
    import ctypes

    for name in ("libcublas.so.12", "libcudnn.so.9"):
        try:
            ctypes.CDLL(name)
        except OSError:
            return False
    return True


def resolve_device(requested: str) -> tuple[str, str | None]:
    """(device effectif, raison du repli éventuel)."""
    if requested in ("cuda", "auto") and not cuda_usable():
        if requested == "cuda":
            return "cpu", "device = cuda demandé mais libcublas.so.12 / libcudnn.so.9 introuvables"
        return "cpu", None
    return ("cuda" if requested == "auto" else requested), None


def _is_cuda_error(exc: BaseException) -> bool:
    return any(marker in str(exc).lower() for marker in _CUDA_MARKERS)


class FasterWhisperSTT:
    name = "faster-whisper"

    def __init__(self, cfg: STTConfig, hotwords: str | None = "Iris") -> None:
        self.cfg = cfg
        self.hotwords = hotwords
        self._model = None
        self.device = "cpu"
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
        device, reason = resolve_device(self.cfg.device)
        if reason:
            log.warning(
                '%s — transcription sur CPU (installe cuda/cudnn ou mets stt.device = "cpu")',
                reason,
            )
        compute_type = self.cfg.compute_type
        if device == "cpu" and compute_type in ("float16", "int8_float16", "bfloat16"):
            compute_type = "int8"  # types GPU impossibles sur CPU
        self.device = device
        log.info(
            "Chargement du modèle Whisper « %s » (%s, %s)…", self.cfg.model, device, compute_type
        )
        try:
            self._model = WhisperModel(self.cfg.model, device=device, compute_type=compute_type)
        except (RuntimeError, OSError, ValueError) as exc:
            if device == "cpu" or not _is_cuda_error(exc):
                raise
            log.warning("CUDA inutilisable (%s) — repli sur CPU", exc)
            self.device = "cpu"
            self._model = WhisperModel(self.cfg.model, device="cpu", compute_type="int8")
        log.info("Modèle Whisper prêt en %.1fs (%s)", time.monotonic() - started, self.device)

    def _run(self, samples: np.ndarray, language: str | None):
        assert self._model is not None
        return self._model.transcribe(
            samples,
            language=language,
            beam_size=self.cfg.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
            hotwords=self.hotwords,
        )

    @staticmethod
    def _collect(segments) -> list[str]:
        return _collect_segments(segments)

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        self.load()
        assert self._model is not None
        if sample_rate != 16000:
            audio = _resample(audio, sample_rate, 16000)
        samples = int16_to_float32(audio)
        if samples.size < 1600:  # < 0,1 s
            return ""
        try:
            segments, info = self._run(samples, language)
            parts = self._collect(segments)
        except (RuntimeError, OSError) as exc:
            if self.device == "cpu" or not _is_cuda_error(exc):
                raise
            # bibliothèques CUDA absentes au moment de l'inférence : on recharge sur CPU une fois
            log.warning("CUDA en échec à la transcription (%s) — repli définitif sur CPU", exc)
            self.cfg.device = "cpu"
            self._model = None
            self.load()
            segments, info = self._run(samples, language)
            parts = self._collect(segments)
        text = " ".join(p for p in parts if p).strip()
        self.last_language = getattr(info, "language", None)
        if is_hallucination(text):
            log.debug("Transcription ignorée (hallucination probable) : %r", text)
            return ""
        log.debug("Transcription (%s, p=%.2f) : %r", info.language, info.language_probability, text)
        return text


def _collect_segments(segments) -> list[str]:
    parts: list[str] = []
    for seg in segments:
        if getattr(seg, "no_speech_prob", 0.0) > 0.7:
            continue
        parts.append(seg.text.strip())
    return parts


def _resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Ré-échantillonnage linéaire simple (suffisant pour la parole)."""
    if src == dst or audio.size == 0:
        return audio
    duration = audio.shape[0] / src
    n = int(duration * dst)
    x_old = np.linspace(0, duration, audio.shape[0], endpoint=False)
    x_new = np.linspace(0, duration, n, endpoint=False)
    return np.interp(x_new, x_old, audio.astype(np.float32)).astype(audio.dtype)
