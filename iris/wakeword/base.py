from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WakeMatch:
    phrase: str  # phrase d'activation reconnue (forme canonique)
    ratio: float  # similarité (1.0 = exacte)
    remainder: str  # texte restant = commande éventuelle, dans sa forme d'origine
    position: str  # "prefix" | "suffix"
