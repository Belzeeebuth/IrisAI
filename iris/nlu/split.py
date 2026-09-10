"""Découpage de plusieurs commandes dans une phrase : « ouvre le terminal et va sur le workspace 2 »."""

from __future__ import annotations

import re
from collections.abc import Callable

_SEPARATORS = re.compile(
    r"\s+(?:et puis|puis|et ensuite|ensuite|et apres|apres ca|et|and then|then|and)\s+",
    re.IGNORECASE,
)


# Intentions dont l'objet peut être partagé : « ouvre firefox et spotify » → « ouvre spotify ».
ELLIPTIC_INTENTS = {"open_app", "close_app", "bluetooth_connect", "bluetooth_disconnect"}


def split_commands(
    text: str, intent_of: Callable[[str], str | None], max_parts: int = 4
) -> list[str]:
    """Retourne les parties si chacune est une commande reconnue, sinon ``[text]``.

    ``intent_of(text)`` renvoie le nom de l'intention reconnue ou None.
    """
    parts = [p.strip(" ,;") for p in _SEPARATORS.split(text)]
    parts = [p for p in parts if p]
    if len(parts) < 2 or len(parts) > max_parts:
        return [text]
    intents = [intent_of(p) for p in parts]
    if all(intents):
        return parts
    expanded: list[str] = []
    expanded_intents: list[str | None] = []
    for part, intent in zip(parts, intents, strict=True):
        if intent or not expanded:
            expanded.append(part)
            expanded_intents.append(intent)
            continue
        verb = expanded[-1].split()[0]
        candidate = f"{verb} {part}"
        candidate_intent = intent_of(candidate)
        if expanded_intents[-1] in ELLIPTIC_INTENTS and candidate_intent == expanded_intents[-1]:
            expanded.append(candidate)
            expanded_intents.append(candidate_intent)
        else:
            expanded[-1] = f"{expanded[-1]} et {part}"
            expanded_intents[-1] = intent_of(expanded[-1])
    if len(expanded) >= 2 and all(expanded_intents):
        return expanded
    return [text]
