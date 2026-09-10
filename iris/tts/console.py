from __future__ import annotations

import sys


class ConsoleTTS:
    """Affiche la réponse au lieu de la prononcer (tests, mode texte, machine sans audio)."""

    name = "console"

    def __init__(self, stream=None, prefix: str = "🗣  Iris : ") -> None:
        self.stream = stream or sys.stdout
        self.prefix = prefix
        self.spoken: list[str] = []

    def speak(self, text: str) -> bool:
        self.spoken.append(text)
        print(f"{self.prefix}{text}", file=self.stream, flush=True)
        return True


class NullTTS:
    name = "none"

    def speak(self, text: str) -> bool:
        return True
