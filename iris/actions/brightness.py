"""Luminosité de l'écran : ``brightnessctl`` puis ``light``."""

from __future__ import annotations

from iris.actions import system


def _tool() -> str:
    if system.which("brightnessctl"):
        return "brightnessctl"
    if system.which("light"):
        return "light"
    raise RuntimeError("brightnessctl (ou light) n'est pas installé")


def get_brightness() -> int:
    tool = _tool()
    if tool == "brightnessctl":
        res = system.run(["brightnessctl", "-m"])
        # intel_backlight,backlight,12000,50%,24000
        for line in res.out.splitlines():
            parts = line.split(",")
            if len(parts) >= 4 and parts[3].endswith("%"):
                return int(parts[3].rstrip("%"))
        raise RuntimeError("lecture de la luminosité impossible")
    res = system.run(["light", "-G"])
    return int(float(res.out or 0))


def set_brightness(percent: int) -> int:
    percent = max(1, min(100, int(percent)))
    tool = _tool()
    res = system.run(
        ["brightnessctl", "-q", "set", f"{percent}%"]
        if tool == "brightnessctl"
        else ["light", "-S", str(percent)]
    )
    if not res.ok:
        raise RuntimeError(res.err or "réglage de la luminosité impossible")
    return percent


def change_brightness(delta: int) -> int:
    tool = _tool()
    if tool == "brightnessctl":
        spec = f"{abs(delta)}%{'+' if delta >= 0 else '-'}"
        res = system.run(["brightnessctl", "-q", "-n1", "set", spec])
    else:
        res = system.run(["light", "-A" if delta >= 0 else "-U", str(abs(delta))])
    if not res.ok:
        raise RuntimeError(res.err or "réglage de la luminosité impossible")
    try:
        return get_brightness()
    except RuntimeError:
        return -1
