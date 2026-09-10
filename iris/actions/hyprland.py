"""Pilotage d'Hyprland via ``hyprctl``.

Quand Iris tourne en service systemd, ``HYPRLAND_INSTANCE_SIGNATURE`` peut manquer :
on la retrouve dans ``$XDG_RUNTIME_DIR/hypr/``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from iris.actions import system

log = logging.getLogger(__name__)


def ensure_env() -> bool:
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "hypr"
    if not runtime.is_dir():
        return False
    instances = [p for p in runtime.iterdir() if p.is_dir() and (p / ".socket.sock").exists()]
    if not instances:
        return False
    newest = max(instances, key=lambda p: p.stat().st_mtime)
    os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = newest.name
    log.info("Instance Hyprland détectée : %s", newest.name)
    return True


def available() -> bool:
    return system.which("hyprctl") is not None and ensure_env()


def hyprctl(*args: str, as_json: bool = False) -> Any:
    ensure_env()
    argv = ["hyprctl", *(["-j"] if as_json else []), *args]
    result = system.run(argv, timeout=5)
    if not result.ok:
        raise RuntimeError(result.err or result.out or "hyprctl a échoué")
    if as_json:
        try:
            return json.loads(result.out or "null")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"réponse hyprctl illisible : {exc}") from exc
    return result.out


# Hyprland ≥ 0.56 : ``hyprctl dispatch`` évalue du Lua (``hl.dsp.window.close()``…) ;
# l'ancienne syntaxe ``closewindow address:0x…`` échoue avec « hl.dispatch: expected a
# dispatcher ». On tente l'ancienne syntaxe une fois, puis on traduit si nécessaire.
_lua_dispatch: bool | None = None


def _lua_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lua_args(**fields: str) -> str:
    inner = ", ".join(f"{k} = {_lua_str(v)}" for k, v in fields.items() if v)
    return f"({{ {inner} }})" if inner else "()"


def to_lua(name: str, *args: str) -> str:
    """Traduit un dispatcher classique en appel Lua ``hl.dsp.…`` (Hyprland ≥ 0.56)."""
    arg = " ".join(a for a in args if a).strip()
    if name == "killactive":
        return "hl.dsp.window.close()"
    if name == "closewindow":
        return "hl.dsp.window.close" + _lua_args(window=arg)
    if name == "focuswindow":
        return "hl.dsp.focus" + _lua_args(window=arg)
    if name == "workspace":
        return "hl.dsp.focus" + _lua_args(workspace=arg)
    if name in ("movetoworkspace", "movetoworkspacesilent"):
        lua = "hl.dsp.window.move" + _lua_args(workspace=arg)
        if name.endswith("silent"):
            lua = lua[:-3] + ", follow = false })"
        return lua
    if name == "fullscreen":
        return "hl.dsp.window.fullscreen" + _lua_args(
            mode="maximized" if arg == "1" else "fullscreen"
        )
    if name == "togglefloating":
        return "hl.dsp.window.float" + _lua_args(action="toggle")
    if name == "movewindow" and arg.startswith("mon:"):
        return "hl.dsp.window.move" + _lua_args(monitor=arg[4:])
    if name == "focusmonitor":
        return "hl.dsp.focus" + _lua_args(monitor=arg)
    raise RuntimeError(f"dispatcher sans équivalent Lua : {name} {arg}".strip())


def _is_lua_syntax_error(message: str) -> bool:
    return "hl.dispatch" in message


def dispatch(*args: str) -> str:
    global _lua_dispatch
    if not args:
        raise RuntimeError("dispatch sans dispatcher")
    if _lua_dispatch:
        return hyprctl("dispatch", to_lua(*args))
    try:
        return hyprctl("dispatch", *args)
    except RuntimeError as exc:
        if _lua_dispatch is False or not _is_lua_syntax_error(str(exc)):
            raise
        log.info("Hyprland en mode Lua : les dispatchers sont traduits (hl.dsp.…)")
        _lua_dispatch = True
        return hyprctl("dispatch", to_lua(*args))


def switch_workspace(n: int) -> None:
    dispatch("workspace", str(n))


def workspace_relative(delta: int) -> None:
    dispatch("workspace", f"e{'+' if delta >= 0 else '-'}{abs(delta)}")


def move_active_to_workspace(n: int) -> None:
    dispatch("movetoworkspace", str(n))


def close_active_window() -> None:
    dispatch("killactive")


def toggle_fullscreen() -> None:
    dispatch("fullscreen", "0")


def toggle_floating() -> None:
    dispatch("togglefloating")


def active_window() -> dict[str, Any]:
    data = hyprctl("activewindow", as_json=True)
    return data if isinstance(data, dict) else {}


def clients() -> list[dict[str, Any]]:
    data = hyprctl("clients", as_json=True)
    return [c for c in data if isinstance(c, dict)] if isinstance(data, list) else []


def close_window(address: str) -> None:
    dispatch("closewindow", f"address:{address}")


def focus_window(address: str) -> None:
    dispatch("focuswindow", f"address:{address}")


def find_clients(*needles: str) -> list[dict[str, Any]]:
    """Fenêtres dont la classe ou le titre contient l'un des motifs (insensible à la casse)."""
    keys = [n.lower() for n in needles if n]
    found = []
    for client in clients():
        haystack = " ".join(
            str(client.get(k, "")) for k in ("class", "initialClass", "title", "initialTitle")
        ).lower()
        if any(k in haystack for k in keys):
            found.append(client)
    return found


def close_all_windows() -> int:
    count = 0
    for client in clients():
        address = client.get("address")
        if address:
            try:
                close_window(address)
                count += 1
            except RuntimeError as exc:
                log.warning("Impossible de fermer %s : %s", client.get("class"), exc)
    return count


def current_workspace() -> int | None:
    data = hyprctl("activeworkspace", as_json=True)
    return int(data["id"]) if isinstance(data, dict) and "id" in data else None
