"""Notifications bureau (notify-send → mako/dunst sous Omarchy)."""

from __future__ import annotations

from iris.actions import system


def send(
    title: str, body: str = "", urgency: str = "normal", icon: str = "audio-input-microphone"
) -> bool:
    if not system.which("notify-send"):
        return False
    argv = ["notify-send", "-a", "Iris", "-i", icon, "-u", urgency, title]
    if body:
        argv.append(body)
    return system.run(argv, timeout=5).ok
