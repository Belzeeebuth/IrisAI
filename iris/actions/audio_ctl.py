"""Volume de la sortie audio par défaut : ``wpctl`` (WirePlumber) puis ``pactl``."""

from __future__ import annotations

import re

from iris.actions import system

SINK_WP = "@DEFAULT_AUDIO_SINK@"
SINK_PA = "@DEFAULT_SINK@"


def _tool() -> str:
    if system.which("wpctl"):
        return "wpctl"
    if system.which("pactl"):
        return "pactl"
    raise RuntimeError("ni wpctl ni pactl n'est disponible")


def get_volume() -> tuple[int, bool]:
    """(volume en %, muet ?)"""
    tool = _tool()
    if tool == "wpctl":
        res = system.run(["wpctl", "get-volume", SINK_WP])
        if not res.ok:
            raise RuntimeError(res.err or "wpctl get-volume a échoué")
        m = re.search(r"Volume:\s*([\d.]+)", res.out)
        vol = int(round(float(m.group(1)) * 100)) if m else 0
        return vol, "[MUTED]" in res.out
    res = system.run(["pactl", "get-sink-volume", SINK_PA])
    m = re.search(r"(\d+)%", res.out)
    vol = int(m.group(1)) if m else 0
    mute = system.run(["pactl", "get-sink-mute", SINK_PA])
    return vol, "yes" in mute.out.lower()


def set_volume(percent: int) -> int:
    percent = max(0, min(100, int(percent)))
    tool = _tool()
    if tool == "wpctl":
        res = system.run(["wpctl", "set-volume", "-l", "1.0", SINK_WP, f"{percent}%"])
    else:
        res = system.run(["pactl", "set-sink-volume", SINK_PA, f"{percent}%"])
    if not res.ok:
        raise RuntimeError(res.err or "réglage du volume impossible")
    return percent


def change_volume(delta: int) -> int:
    """Ajuste de ``delta`` points et retourne le nouveau volume (plafonné à 100 %)."""
    tool = _tool()
    sign = "+" if delta >= 0 else "-"
    if tool == "wpctl":
        res = system.run(["wpctl", "set-volume", "-l", "1.0", SINK_WP, f"{abs(delta)}%{sign}"])
    else:
        res = system.run(["pactl", "set-sink-volume", SINK_PA, f"{sign}{abs(delta)}%"])
    if not res.ok:
        raise RuntimeError(res.err or "réglage du volume impossible")
    try:
        return get_volume()[0]
    except RuntimeError:
        return -1


def set_mute(state: bool | None) -> bool:
    """True/False pour forcer, None pour basculer. Retourne l'état muet final."""
    tool = _tool()
    if tool == "wpctl":
        value = "toggle" if state is None else ("1" if state else "0")
        res = system.run(["wpctl", "set-mute", SINK_WP, value])
    else:
        value = "toggle" if state is None else ("1" if state else "0")
        res = system.run(["pactl", "set-sink-mute", SINK_PA, value])
    if not res.ok:
        raise RuntimeError(res.err or "sourdine impossible")
    try:
        return get_volume()[1]
    except RuntimeError:
        return bool(state)
