"""Synthèse locale avec Piper.

Deux chemins :
- API Python ``piper`` (modèle gardé en mémoire → latence minimale) ;
- sinon le binaire ``piper`` (pip ou paquet AUR ``piper-tts-bin``) via sous-processus.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from iris.audio.playback import play_pcm
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech
from iris.tts.voices import voice_files

log = logging.getLogger(__name__)


def find_piper_binary() -> str | None:
    candidates = [
        shutil.which("piper"),
        str(Path(sys.executable).parent / "piper"),
        str(Path.home() / ".local/bin/piper"),
        "/usr/bin/piper",
        "/usr/bin/piper-tts",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


class PiperTTS:
    name = "piper"

    def __init__(self, cfg: TTSConfig, player: str = "auto") -> None:
        self.cfg = cfg
        self.player = player
        files = voice_files(cfg.piper_voice, cfg.piper_voices_dir)
        if files is None:
            raise RuntimeError(
                f"Voix Piper « {cfg.piper_voice} » introuvable — `iris voices download {cfg.piper_voice}`"
            )
        self.model_path, self.config_path = files
        with open(self.config_path, encoding="utf-8") as fh:
            self.sample_rate = int(json.load(fh).get("audio", {}).get("sample_rate", 22050))
        self._voice = None
        self._binary: str | None = None
        self._mode = self._pick_mode()
        log.info("TTS Piper : %s (%s)", self.model_path.name, self._mode)

    # ------------------------------------------------------------------ interne
    def _pick_mode(self) -> str:
        try:
            from piper import PiperVoice  # noqa: F401

            return "python"
        except Exception:
            self._binary = find_piper_binary()
            if self._binary:
                return "cli"
        raise RuntimeError(
            "Piper introuvable : pip install 'iris-assistant[tts]' (ou paquet piper-tts-bin)"
        )

    def _synthesize_python(self, text: str) -> bytes:
        from piper import PiperVoice, SynthesisConfig

        if self._voice is None:
            self._voice = PiperVoice.load(str(self.model_path), str(self.config_path))
        syn = SynthesisConfig(length_scale=self.cfg.piper_length_scale or None)
        chunks: list[bytes] = []
        silence = b"\x00\x00" * int(self.sample_rate * self.cfg.piper_sentence_silence)
        for chunk in self._voice.synthesize(text, syn_config=syn):
            self.sample_rate = chunk.sample_rate
            chunks.append(chunk.audio_int16_bytes)
            chunks.append(silence)
        return b"".join(chunks)

    def _synthesize_cli(self, text: str) -> bytes:
        assert self._binary
        argv = [
            self._binary,
            "-m",
            str(self.model_path),
            "-c",
            str(self.config_path),
            "--output-raw",
            "--length-scale",
            str(self.cfg.piper_length_scale),
            "--sentence-silence",
            str(self.cfg.piper_sentence_silence),
        ]
        proc = subprocess.run(
            argv,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()[-400:])
        return proc.stdout

    # ------------------------------------------------------------------ public
    def synthesize(self, text: str) -> bytes:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return b""
        return (
            self._synthesize_python(text) if self._mode == "python" else self._synthesize_cli(text)
        )

    def speak(self, text: str) -> bool:
        try:
            pcm = self.synthesize(text)
        except Exception as exc:
            log.error("Synthèse Piper impossible : %s", exc)
            return False
        return play_pcm(pcm, self.sample_rate, player=self.player)
