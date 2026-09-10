"""Intégration Omarchy : thèmes, verrouillage, capture d'écran, web-apps, mode nuit.

Chaque fonction utilise le script ``omarchy-*`` s'il existe, avec un repli générique.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from iris.actions import system
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)


def is_omarchy() -> bool:
    return (
        system.which("omarchy-theme-set") is not None
        or (Path.home() / ".local/share/omarchy").is_dir()
    )


def themes_dir() -> Path:
    return Path(os.environ.get("OMARCHY_PATH", Path.home() / ".local/share/omarchy")) / "themes"


def list_themes() -> list[str]:
    d = themes_dir()
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def theme_next() -> None:
    if not system.which("omarchy-theme-next"):
        raise RuntimeError("omarchy-theme-next indisponible (pas sous Omarchy ?)")
    res = system.run(["omarchy-theme-next"], timeout=30)
    if not res.ok:
        raise RuntimeError(res.err or "changement de thème impossible")


def theme_set(name: str) -> str:
    if not system.which("omarchy-theme-set"):
        raise RuntimeError("omarchy-theme-set indisponible (pas sous Omarchy ?)")
    wanted = canonical(name).replace(" ", "-")
    themes = list_themes()
    chosen = wanted
    if themes:
        matches = [t for t in themes if canonical(t).replace(" ", "-") == wanted]
        if not matches:
            matches = [t for t in themes if wanted in canonical(t).replace(" ", "-")]
        if not matches:
            raise RuntimeError(f"thème inconnu : {name} (disponibles : {', '.join(themes)})")
        chosen = matches[0]
    res = system.run(["omarchy-theme-set", chosen], timeout=30)
    if not res.ok:
        raise RuntimeError(res.err or f"impossible d'appliquer le thème {chosen}")
    return chosen


def lock_screen() -> None:
    for argv in (["omarchy-lock-screen"], ["hyprlock"], ["loginctl", "lock-session"]):
        if system.which(argv[0]):
            if system.launch(argv, launcher="direct"):
                return
    raise RuntimeError(
        "aucun outil de verrouillage trouvé (omarchy-lock-screen, hyprlock, loginctl)"
    )


def screenshot() -> str:
    if system.which("omarchy-cmd-screenshot"):
        system.launch(["omarchy-cmd-screenshot"], launcher="direct")
        return "omarchy"
    if system.which("hyprshot"):
        system.launch(["hyprshot", "-m", "region"], launcher="direct")
        return "hyprshot"
    if system.which("grim") and system.which("slurp"):
        system.launch(
            'grim -g "$(slurp)" ~/Pictures/screenshot-$(date +%Y%m%d-%H%M%S).png',
            launcher="direct",
            shell=True,
        )
        return "grim"
    raise RuntimeError("aucun outil de capture (omarchy-cmd-screenshot, hyprshot, grim+slurp)")


def toggle_nightlight() -> None:
    if system.which("omarchy-toggle-nightlight"):
        res = system.run(["omarchy-toggle-nightlight"])
        if not res.ok:
            raise RuntimeError(res.err or "mode nuit impossible")
        return
    raise RuntimeError("omarchy-toggle-nightlight indisponible")


def launch_webapp(url: str, launcher: str = "auto") -> None:
    if system.which("omarchy-launch-webapp"):
        system.launch(["omarchy-launch-webapp", url], launcher=launcher)
    else:
        system.launch(["xdg-open", url], launcher=launcher)
