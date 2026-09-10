"""Cache disque des synthèses : les réponses d'Iris se répètent beaucoup (« Oui ? », « Workspace 2. »),
inutile de payer et d'attendre une voix cloud deux fois pour la même phrase.

Clé = SHA-256(backend, voix, modèle, réglages, langue, texte). Fichiers ``<clé>.pcm`` + ``<clé>.json``
(fréquence d'échantillonnage). Purge LRU au-delà de ``max_mb``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

from iris import paths

log = logging.getLogger(__name__)


class TTSCache:
    def __init__(
        self, directory: Path | str | None = None, max_mb: int = 200, enabled: bool = True
    ) -> None:
        self.dir = Path(directory) if directory else paths.cache_dir() / "tts"
        self.max_bytes = int(max_mb) * 1024 * 1024
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: object) -> str:
        raw = "\x1f".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> tuple[bytes, int] | None:
        if not self.enabled:
            return None
        pcm_path = self.dir / f"{key}.pcm"
        meta_path = self.dir / f"{key}.json"
        try:
            rate = int(json.loads(meta_path.read_text(encoding="utf-8"))["rate"])
            pcm = pcm_path.read_bytes()
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            self.misses += 1
            return None
        now = time.time()
        try:
            os.utime(pcm_path, (now, now))  # LRU
        except OSError:
            pass
        self.hits += 1
        return pcm, rate

    def put(self, key: str, pcm: bytes, rate: int) -> None:
        if not self.enabled or not pcm:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{key}.pcm").write_bytes(pcm)
            (self.dir / f"{key}.json").write_text(
                json.dumps({"rate": rate, "ts": time.time()}), encoding="utf-8"
            )
        except OSError as exc:
            log.debug("cache TTS non écrit : %s", exc)
            return
        self.prune()

    def fetch(self, key: str, synthesize: Callable[[], tuple[bytes, int]]) -> tuple[bytes, int]:
        cached = self.get(key)
        if cached is not None:
            return cached
        pcm, rate = synthesize()
        self.put(key, pcm, rate)
        return pcm, rate

    def prune(self) -> None:
        try:
            files = sorted(self.dir.glob("*.pcm"), key=lambda p: p.stat().st_mtime)
        except OSError:
            return
        total = sum(p.stat().st_size for p in files if p.exists())
        for path in files:
            if total <= self.max_bytes:
                break
            try:
                size = path.stat().st_size
                path.unlink()
                path.with_suffix(".json").unlink(missing_ok=True)
                total -= size
            except OSError:
                continue

    def clear(self) -> int:
        n = 0
        for path in self.dir.glob("*"):
            try:
                path.unlink()
                n += 1
            except OSError:
                pass
        return n

    def size_bytes(self) -> int:
        try:
            return sum(p.stat().st_size for p in self.dir.glob("*.pcm"))
        except OSError:
            return 0
