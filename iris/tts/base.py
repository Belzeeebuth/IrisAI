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


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÝÉÈ«\"'0-9])")


def split_sentences(text: str, min_chars: int = 40) -> list[str]:
    """Découpe en phrases (regroupe les très courtes) pour synthétiser/jouer en pipeline."""
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged or ([text] if text else [])


def speak_streaming(synthesize, play, text: str) -> bool:
    """Synthétise la phrase N+1 pendant que la phrase N est jouée (latence perçue réduite).

    ``synthesize(sentence) -> (pcm, rate)`` ; ``play(pcm, rate) -> bool``.
    """
    import queue
    import threading

    sentences = split_sentences(text)
    if not sentences:
        return False
    if len(sentences) == 1:
        pcm, rate = synthesize(sentences[0])
        return play(pcm, rate)

    q: queue.Queue = queue.Queue(maxsize=2)

    def producer() -> None:
        try:
            for sentence in sentences:
                q.put(synthesize(sentence))
        except Exception as exc:  # noqa: BLE001
            q.put(exc)
        finally:
            q.put(None)

    threading.Thread(target=producer, name="iris-tts", daemon=True).start()
    played = False
    while True:
        item = q.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        pcm, rate = item
        if pcm:
            played = play(pcm, rate) or played
    return played
