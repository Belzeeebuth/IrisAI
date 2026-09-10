"""Conversion des nombres écrits en lettres (français et anglais) en chiffres, 0 → 999.

Whisper produit généralement des chiffres, mais pas toujours (« volume à cinquante »).
Les articles « un / une / a » isolés ne sont jamais convertis.
"""

from __future__ import annotations

import re

FR_UNITS = {
    "zero": 0,
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
}
FR_TENS = {"vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
FR_WORDS = set(FR_UNITS) | set(FR_TENS) | {"cent", "cents", "et"}

EN_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
EN_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
EN_WORDS = set(EN_UNITS) | set(EN_TENS) | {"hundred", "and"}

ARTICLES = {"un", "une"}
_TOKEN = re.compile(r"[\w'.]+(?:-[\w'.]+)*|\S")


def _parse_fr(tokens: list[str]) -> int | None:
    total = 0
    current = 0
    seen = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if tok == "et":
            i += 1
            continue
        if tok in ("cent", "cents"):
            current = (current or 1) * 100
            seen = True
        elif tok == "quatre" and nxt in ("vingt", "vingts"):
            current += 80
            seen = True
            i += 2
            continue
        elif tok in FR_TENS:
            current += FR_TENS[tok]
            seen = True
        elif tok in FR_UNITS:
            current += FR_UNITS[tok]
            seen = True
        else:
            return None
        i += 1
    return total + current if seen else None


def _parse_en(tokens: list[str]) -> int | None:
    current = 0
    seen = False
    for tok in tokens:
        if tok == "and":
            continue
        if tok == "hundred":
            current = (current or 1) * 100
            seen = True
        elif tok in EN_TENS:
            current += EN_TENS[tok]
            seen = True
        elif tok in EN_UNITS:
            current += EN_UNITS[tok]
            seen = True
        else:
            return None
    return current if seen else None


CONNECTORS = {"et", "and"}


def _convert_run(run: list[str]) -> str | None:
    parts = [p for tok in run for p in tok.split("-")]
    while parts and parts[0] in CONNECTORS:
        parts.pop(0)
    while parts and parts[-1] in CONNECTORS:
        parts.pop()
    if not parts:
        return None
    if all(p in ARTICLES for p in parts):
        return None  # « un terminal », « et une image » : article, pas nombre
    if all(p in FR_WORDS for p in parts):
        value = _parse_fr(parts)
        if value is not None:
            return str(value)
    if all(p in EN_WORDS for p in parts):
        value = _parse_en(parts)
        if value is not None:
            return str(value)
    return None


def words_to_digits(text: str) -> str:
    """Remplace chaque suite de mots-nombres par sa valeur (« vingt-cinq » → « 25 »)."""
    tokens = _TOKEN.findall(text)
    out: list[str] = []
    run: list[str] = []

    def is_number_word(tok: str) -> bool:
        parts = tok.split("-")
        return all(p in FR_WORDS or p in EN_WORDS for p in parts)

    def flush() -> None:
        if not run:
            return
        converted = _convert_run(run)
        if converted is not None:
            out.append(converted)
        else:
            out.extend(run)
        run.clear()

    for tok in tokens:
        if is_number_word(tok):
            run.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return " ".join(out)
