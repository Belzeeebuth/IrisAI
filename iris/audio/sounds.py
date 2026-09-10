"""Petits signaux sonores générés à la volée (aucun fichier à embarquer)."""

from __future__ import annotations

import numpy as np

from iris.audio.wavutil import float32_to_int16


def _tone(freq: float, duration: float, rate: int, volume: float = 0.25) -> np.ndarray:
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    envelope = np.minimum(1.0, np.minimum(t / 0.01, (duration - t) / 0.03))
    return (np.sin(2 * np.pi * freq * t) * envelope * volume).astype(np.float32)


def ack_beep(rate: int = 22050) -> bytes:
    """Deux notes montantes : « je t'écoute »."""
    audio = np.concatenate([_tone(660, 0.07, rate), _tone(990, 0.09, rate)])
    return float32_to_int16(audio).tobytes()


def error_beep(rate: int = 22050) -> bytes:
    audio = _tone(330, 0.15, rate)
    return float32_to_int16(audio).tobytes()
