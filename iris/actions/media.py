"""Contrôle des lecteurs multimédia via ``playerctl`` (MPRIS)."""

from __future__ import annotations

from iris.actions import system


def _playerctl(*args: str) -> None:
    if not system.which("playerctl"):
        raise RuntimeError("playerctl n'est pas installé")
    res = system.run(["playerctl", *args], timeout=5)
    if not res.ok:
        raise RuntimeError(res.err or "aucun lecteur actif")


def play_pause() -> None:
    _playerctl("play-pause")


def next_track() -> None:
    _playerctl("next")


def previous_track() -> None:
    _playerctl("previous")


def now_playing() -> str:
    if not system.which("playerctl"):
        return ""
    res = system.run(["playerctl", "metadata", "--format", "{{artist}} - {{title}}"], timeout=5)
    return res.out if res.ok else ""
