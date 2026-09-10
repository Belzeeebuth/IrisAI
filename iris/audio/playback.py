"""Lecture audio (PCM int16) via le premier lecteur disponible.

Ordre « auto » : pw-play (PipeWire), paplay, aplay, ffplay, puis sounddevice.
Un fichier WAV temporaire est utilisé pour les lecteurs en ligne de commande.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

from iris.audio.wavutil import pcm_to_wav_bytes

log = logging.getLogger(__name__)

PLAYERS: dict[str, list[str]] = {
    "pw-play": ["pw-play"],
    "paplay": ["paplay"],
    "aplay": ["aplay", "-q"],
    "ffplay": ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    "mpv": ["mpv", "--no-terminal", "--no-video"],
}


def available_player(preferred: str = "auto") -> str | None:
    order = list(PLAYERS) + ["sounddevice"] if preferred == "auto" else [preferred]
    for name in order:
        if name == "sounddevice":
            try:
                import sounddevice  # noqa: F401

                return name
            except Exception:
                continue
        if shutil.which(PLAYERS[name][0]):
            return name
    return None


def play_pcm(pcm: bytes, sample_rate: int, channels: int = 1, player: str = "auto") -> bool:
    if not pcm:
        return False
    name = available_player(player)
    if name is None:
        log.warning("Aucun lecteur audio disponible (pw-play, paplay, aplay, ffplay, sounddevice)")
        return False
    if name == "sounddevice":
        return _play_sounddevice(pcm, sample_rate, channels)
    return _play_wav_file(pcm_to_wav_bytes(pcm, sample_rate, channels), PLAYERS[name])


def _play_sounddevice(pcm: bytes, sample_rate: int, channels: int) -> bool:
    try:
        import numpy as np
        import sounddevice as sd

        audio = np.frombuffer(pcm, dtype=np.int16).reshape(-1, channels)
        sd.play(audio, sample_rate, blocking=True)
        return True
    except Exception as exc:
        log.warning("Lecture sounddevice impossible : %s", exc)
        return False


def _play_wav_file(wav: bytes, argv: list[str]) -> bool:
    fd, path = tempfile.mkstemp(prefix="iris-", suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(wav)
        subprocess.run(
            [*argv, path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        return True
    except Exception as exc:
        log.warning("Lecture avec %s impossible : %s", argv[0], exc)
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def play_wav_bytes(wav: bytes, player: str = "auto") -> bool:
    name = available_player(player)
    if name is None:
        return False
    if name == "sounddevice":
        import io
        import wave

        with wave.open(io.BytesIO(wav), "rb") as w:
            return _play_sounddevice(
                w.readframes(w.getnframes()), w.getframerate(), w.getnchannels()
            )
    return _play_wav_file(wav, PLAYERS[name])
