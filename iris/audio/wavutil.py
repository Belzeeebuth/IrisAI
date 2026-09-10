"""Petits utilitaires WAV / PCM (bibliothèque standard uniquement)."""

from __future__ import annotations

import io
import wave

import numpy as np


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    if audio.dtype == np.float32:
        return audio
    return (audio.astype(np.float32) / 32768.0).clip(-1.0, 1.0)


def float32_to_int16(audio: np.ndarray) -> np.ndarray:
    if audio.dtype == np.int16:
        return audio
    return (audio.clip(-1.0, 1.0) * 32767.0).astype(np.int16)


def rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    f = int16_to_float32(frame)
    return float(np.sqrt(np.mean(f * f)))


def duration_s(audio: np.ndarray, sample_rate: int) -> float:
    return audio.shape[0] / float(sample_rate)
