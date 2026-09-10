"""Normalisation du texte transcrit avant analyse.

``normalize``  : minuscules, accents supprimés, ponctuation retirée (apostrophes, tirets et % conservés).
``canonical``  : ``normalize`` + nombres en lettres → chiffres, « pour cent » → %, tirets → espaces,
                 « github point com » → « github.com ».
"""

from __future__ import annotations

import re
import unicodedata

from iris.nlu.numbers import words_to_digits

_APOSTROPHES = re.compile(r"[’‘`´ʼ]")
_PUNCT = re.compile(r"[^\w\s%'\-\x00]", re.UNICODE)
_INNER_DOT = re.compile(r"(?<=\w)\.(?=\w)")
_WS = re.compile(r"\s+")
_PERCENT = re.compile(r"\b(?:pour ?cent|pourcent|per ?cent|percent)\b")
_PCT_SPACE = re.compile(r"(\d)\s+%")
_DOT_TLD = re.compile(
    r"(\w)\s+(?:point|dot)\s+(com|fr|org|net|io|dev|ai|app|co|eu|de|uk|ch|be|ca)\b"
)
_POLITE_PREFIX = re.compile(
    r"^(?:est ce que tu peux|est ce que tu pourrais|peux tu|pourrais tu|pourrais tu me|tu peux|"
    r"veux tu|veux tu bien|j'aimerais que tu|je veux que tu|je voudrais que tu|"
    r"can you|could you|would you|will you|please|s'il te plait|s'il vous plait|stp|svp)\s+"
)
_POLITE_SUFFIX = re.compile(
    r"\s+(?:s'il te plait|s'il vous plait|stp|svp|please|merci|merci beaucoup)\s*[?!.]*$"
)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    text = strip_accents(text).lower()
    text = _APOSTROPHES.sub("'", text)
    text = text.replace("œ", "oe").replace("æ", "ae")
    text = _INNER_DOT.sub("\x00", text)  # protège « github.com », « 3.5 »
    text = _PUNCT.sub(" ", text).replace("\x00", ".")
    return _WS.sub(" ", text).strip()


def canonical(text: str) -> str:
    text = normalize(text)
    text = _PERCENT.sub("%", text)
    text = words_to_digits(text)
    text = text.replace("-", " ")
    text = _PCT_SPACE.sub(r"\1%", text)
    text = _DOT_TLD.sub(r"\1.\2", text)
    return _WS.sub(" ", text).strip()


def strip_politeness(text: str) -> str:
    """Retire les formules de politesse en tête/queue (« peux-tu … s'il te plaît »)."""
    previous = None
    while previous != text:
        previous = text
        text = _POLITE_PREFIX.sub("", text)
        text = _POLITE_SUFFIX.sub("", text)
        text = text.strip(" ,;:!?.")
    return text
