from __future__ import annotations

from typing import Protocol

import numpy as np

# Phrases « hallucinées » par Whisper sur du silence ou du bruit : on les ignore.
HALLUCINATIONS = {
    "sous-titres realises par la communaute d'amara.org",
    "sous-titrage st' 501",
    "sous-titrage societe radio-canada",
    "merci d'avoir regarde cette video",
    "merci d'avoir regarde",
    "abonnez-vous",
    "thank you for watching",
    "thanks for watching",
    "subtitles by the amara.org community",
    "you",
    "...",
}


class STT(Protocol):
    name: str

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None = None) -> str:
        """Retourne le texte transcrit (chaîne vide si rien d'exploitable)."""
        ...


def is_hallucination(text: str) -> bool:
    from iris.nlu.normalize import normalize

    t = normalize(text).strip(" .")
    return not t or t in HALLUCINATIONS
