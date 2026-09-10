"""Compréhension du langage : texte transcrit → intention + paramètres."""

from iris.nlu.intents import Intent, IntentParser, parse_yes_no
from iris.nlu.normalize import canonical, normalize

__all__ = ["Intent", "IntentParser", "parse_yes_no", "canonical", "normalize"]
