from __future__ import annotations

import logging
import shutil
import subprocess

from iris.config import TTSConfig
from iris.tts.base import clean_for_speech

log = logging.getLogger(__name__)


class EspeakTTS:
    """Voix de secours robotique mais universelle (espeak-ng)."""

    name = "espeak"

    def __init__(self, cfg: TTSConfig) -> None:
        self.cfg = cfg
        self.binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.binary:
            raise RuntimeError("espeak-ng introuvable")

    def speak(self, text: str) -> bool:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return False
        try:
            subprocess.run(
                [self.binary, "-v", self.cfg.espeak_voice, "-s", "165", text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
            return True
        except Exception as exc:
            log.warning("espeak a échoué : %s", exc)
            return False
