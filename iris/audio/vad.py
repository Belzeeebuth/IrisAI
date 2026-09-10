"""Détection d'activité vocale et découpage en phrases (« utterances »).

Deux détecteurs :
- ``energy`` : seuil RMS avec estimation adaptative du bruit de fond (aucune dépendance) ;
- ``webrtc``  : ``webrtcvad`` si installé (plus robuste au bruit).

``VadSegmenter.push(frame)`` reçoit des trames int16 de ``frame_ms`` et renvoie la phrase
complète (numpy int16) quand un silence de ``silence_ms`` suit la parole.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

from iris.audio.wavutil import rms
from iris.config import AudioConfig

log = logging.getLogger(__name__)


class EnergyVad:
    def __init__(self, threshold: float = 0.010, ratio: float = 3.0) -> None:
        self.threshold = threshold
        self.ratio = ratio
        self.noise_floor = 0.004

    def is_speech(self, frame: np.ndarray) -> bool:
        level = rms(frame)
        speech = level > max(self.threshold, self.noise_floor * self.ratio)
        if not speech:
            # moyenne mobile lente du bruit de fond
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * level
        return speech


class WebRtcVad:
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000) -> None:
        import webrtcvad  # noqa: WPS433 - optionnel

        self._vad = webrtcvad.Vad(max(0, min(3, aggressiveness)))
        self._rate = sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        return bool(self._vad.is_speech(frame.astype(np.int16).tobytes(), self._rate))


def build_vad(cfg: AudioConfig):
    backend = cfg.vad_backend
    if backend in ("auto", "webrtc"):
        try:
            vad = WebRtcVad(cfg.vad_aggressiveness, cfg.sample_rate)
            log.info("VAD : webrtcvad (agressivité %d)", cfg.vad_aggressiveness)
            return vad
        except Exception as exc:  # ImportError ou fréquence non supportée
            if backend == "webrtc":
                raise
            log.debug("webrtcvad indisponible (%s), VAD énergie utilisé", exc)
    log.info("VAD : énergie (seuil %.3f)", cfg.energy_threshold)
    return EnergyVad(cfg.energy_threshold)


class VadSegmenter:
    def __init__(self, cfg: AudioConfig, vad=None) -> None:
        self.cfg = cfg
        self.vad = vad or build_vad(cfg)
        frame_s = cfg.frame_ms / 1000.0
        self._pre_roll_frames = max(1, int(cfg.pre_roll_ms / cfg.frame_ms))
        self._silence_frames = max(1, int(cfg.silence_ms / cfg.frame_ms))
        self._min_speech_frames = max(1, int(cfg.min_speech_ms / cfg.frame_ms))
        self._max_frames = max(self._min_speech_frames + 1, int(cfg.max_utterance_s / frame_s))
        self._pre_roll: deque[np.ndarray] = deque(maxlen=self._pre_roll_frames)
        self._recent: deque[bool] = deque(maxlen=5)
        self.reset()

    def reset(self) -> None:
        self._in_speech = False
        self._frames: list[np.ndarray] = []
        self._speech_frames = 0
        self._silence_run = 0
        self._pre_roll.clear()
        self._recent.clear()

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def push(self, frame: np.ndarray) -> np.ndarray | None:
        speech = self.vad.is_speech(frame)
        self._recent.append(speech)

        if not self._in_speech:
            self._pre_roll.append(frame)
            # déclenchement : 3 trames de parole parmi les 5 dernières
            if sum(self._recent) >= 3:
                self._in_speech = True
                self._frames = list(self._pre_roll)
                self._speech_frames = sum(self._recent)
                self._silence_run = 0
            return None

        self._frames.append(frame)
        if speech:
            self._speech_frames += 1
            self._silence_run = 0
        else:
            self._silence_run += 1

        ended = self._silence_run >= self._silence_frames
        too_long = len(self._frames) >= self._max_frames
        if not (ended or too_long):
            return None

        frames = self._frames
        enough = self._speech_frames >= self._min_speech_frames
        self.reset()
        if not enough:
            return None
        if ended and self._silence_frames > 2:
            # on retire une partie du silence final (garde ~200 ms)
            keep = max(0, len(frames) - self._silence_frames + int(200 / self.cfg.frame_ms))
            frames = frames[:keep] or frames
        return np.concatenate(frames).astype(np.int16, copy=False)
