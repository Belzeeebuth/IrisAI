"""Multi-écrans Hyprland : déplacer une fenêtre ou le focus vers un écran voisin."""

from __future__ import annotations

from iris.actions import hyprland

DIRECTIONS = {
    "left": "l",
    "gauche": "l",
    "right": "r",
    "droite": "r",
    "up": "u",
    "haut": "u",
    "down": "d",
    "bas": "d",
    "next": "+1",
    "suivant": "+1",
    "prev": "-1",
    "precedent": "-1",
}


def _dir(direction: str) -> str:
    key = DIRECTIONS.get(direction.strip().lower())
    if key is None:
        raise RuntimeError(f"direction inconnue : {direction}")
    return key


def move_window_to_monitor(direction: str) -> None:
    hyprland.dispatch("movewindow", f"mon:{_dir(direction)}")


def focus_monitor(direction: str) -> None:
    hyprland.dispatch("focusmonitor", _dir(direction))


def list_monitors() -> list[dict]:
    data = hyprland.hyprctl("monitors", as_json=True)
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []
