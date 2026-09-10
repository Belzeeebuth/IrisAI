"""Dictée : taper du texte dans la fenêtre active.

Outils (ordre « auto ») : ``wtype`` (Wayland natif), ``ydotool`` (nécessite le daemon), puis repli
``clipboard`` : le texte est copié avec ``wl-copy`` et une notification invite à coller.
"""

from __future__ import annotations

from iris.actions import notify, system

ORDER = ("wtype", "ydotool", "clipboard")


def available_tool(preferred: str = "auto") -> str | None:
    candidates = ORDER if preferred == "auto" else (preferred,)
    for tool in candidates:
        if tool == "clipboard":
            if system.which("wl-copy"):
                return tool
        elif system.which(tool):
            return tool
    return None


def type_text(text: str, preferred: str = "auto", press_enter: bool = False) -> str:
    """Tape ``text`` ; retourne l'outil utilisé. Lève RuntimeError si aucun outil."""
    tool = available_tool(preferred)
    if tool is None:
        raise RuntimeError("aucun outil de saisie (installe wtype : sudo pacman -S wtype)")
    if tool == "wtype":
        res = system.run(["wtype", "--", text], timeout=30)
        if res.ok and press_enter:
            res = system.run(["wtype", "-k", "Return"], timeout=5)
    elif tool == "ydotool":
        res = system.run(["ydotool", "type", "--", text], timeout=30)
        if res.ok and press_enter:
            res = system.run(["ydotool", "key", "28:1", "28:0"], timeout=5)
    else:
        res = system.run(["wl-copy", "--", text], timeout=5)
        if res.ok:
            notify.send(
                "Texte copié",
                "Colle-le avec Ctrl+V (installe wtype pour une saisie directe).",
                icon="edit-paste",
            )
    if not res.ok:
        raise RuntimeError(res.err or f"{tool} a échoué")
    return tool
