from __future__ import annotations

import re
from typing import Protocol

_MARKDOWN = re.compile(r"[*_`#>]+")
_URL = re.compile(r"https?://\S+")


class TTS(Protocol):
    name: str

    def speak(self, text: str) -> bool:
        """Prononce ``text`` (bloquant). Retourne False si rien n'a pu être joué."""
        ...


def clean_for_speech(text: str, max_chars: int = 600) -> str:
    """Nettoie un texte avant synthèse : markdown, URLs, longueur."""
    text = _MARKDOWN.sub("", text)
    text = _URL.sub("lien", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        cut = text[:max_chars]
        # coupe à la dernière phrase complète si possible
        idx = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[: idx + 1] if idx > max_chars // 2 else cut + "…"
    return text
