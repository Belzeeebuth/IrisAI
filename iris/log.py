"""Configuration du logging (stderr → journald quand lancé par systemd, + fichier optionnel)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO", file: Path | None = None, quiet: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)

    if not quiet:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(stream)

    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        rotating.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(rotating)

    # Les bibliothèques tierces sont bavardes ; on les calme.
    for noisy in ("faster_whisper", "urllib3", "httpx", "numba", "openwakeword"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
