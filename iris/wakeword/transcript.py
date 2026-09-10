"""Mot d'activation reconnu dans la transcription (aucun modèle à entraîner).

Chaque phrase transcrite est comparée, mot à mot et de manière floue, aux phrases
d'activation configurées. « Hé Iris, ouvre le terminal » donne ``remainder = "ouvre le terminal"``.
Whisper transcrit parfois « Iris » en « Irisse », « Irish », « Éris »… d'où la tolérance floue.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from iris.nlu.normalize import canonical
from iris.wakeword.base import WakeMatch

_EDGE_PUNCT = re.compile(r"^[\s,;:!?.…\"'«»()-]+|[\s,;:!?.…\"'«»()-]+$")
# Petits mots parasites tolérés juste avant le mot d'activation (« euh, Iris… »).
_FILLERS = {
    "euh",
    "heu",
    "hum",
    "oh",
    "ah",
    "eh",
    "et",
    "bon",
    "alors",
    "um",
    "uh",
    "so",
    "hey",
    "he",
}


def _clean(word: str) -> str:
    return _EDGE_PUNCT.sub("", word)


class TranscriptWake:
    def __init__(self, phrases: Iterable[str], threshold: float = 0.76) -> None:
        self.phrases = [p for p in (canonical(p) for p in phrases) if p]
        if not self.phrases:
            raise ValueError("Au moins une phrase d'activation est nécessaire")
        self.threshold = threshold

    def match(self, text: str) -> WakeMatch | None:
        words = [w for w in (_clean(w) for w in text.split()) if w]
        if not words:
            return None

        best: WakeMatch | None = None

        def consider(candidate: WakeMatch) -> None:
            nonlocal best
            if best is None or candidate.ratio > best.ratio:
                best = candidate

        for phrase in self.phrases:
            k = len(phrase.split())
            # --- préfixe, avec 0 ou 1 mot parasite devant
            for start in (0, 1):
                if start == 1 and (len(words) < 2 or canonical(words[0]) not in _FILLERS):
                    continue
                window = words[start : start + k]
                if len(window) < k:
                    continue
                ratio = self._ratio(" ".join(window), phrase)
                if ratio >= self.threshold:
                    remainder = " ".join(words[start + k :])
                    consider(WakeMatch(phrase, ratio, _clean(remainder), "prefix"))
            # --- suffixe : « ouvre le terminal, Iris »
            if len(words) > k:
                window = words[-k:]
                ratio = self._ratio(" ".join(window), phrase)
                if ratio >= self.threshold:
                    remainder = " ".join(words[:-k])
                    consider(WakeMatch(phrase, ratio, _clean(remainder), "suffix"))
        return best

    @staticmethod
    def _ratio(candidate: str, phrase: str) -> float:
        canon = canonical(candidate)
        if canon == phrase:
            return 1.0
        return SequenceMatcher(None, canon, phrase).ratio()
