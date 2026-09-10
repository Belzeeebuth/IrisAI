"""État d'Iris pour Waybar / Quickshell : fichier JSON + signal optionnel.

Format Waybar (``return-type = "json"``) : ``{"text", "alt", "tooltip", "class"}``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from iris.actions import system

log = logging.getLogger(__name__)

ICONS = {
    "idle": "󰍬",
    "active": "󰍬",
    "confirming": "󰋗",
    "paused": "󰍭",
    "dictating": "󰏫",
    "speaking": "󰔊",
    "thinking": "󰔟",
    "off": "󰍭",
}
LABELS_FR = {
    "idle": "en veille",
    "active": "à l'écoute",
    "confirming": "attend confirmation",
    "paused": "en pause",
    "dictating": "dictée",
    "speaking": "parle",
    "thinking": "réfléchit",
    "off": "arrêtée",
}


def default_status_file() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/iris-{os.getuid()}"))
    return runtime / "iris" / "state.json"


class StatusWriter:
    def __init__(self, path: Path | str | None = None, waybar_signal: int = 0) -> None:
        self.path = Path(path) if path else default_status_file()
        self.waybar_signal = int(waybar_signal or 0)
        self.state = "off"
        self.detail = ""

    def write(self, state: str, detail: str = "") -> None:
        self.state, self.detail = state, detail
        payload = {
            "text": ICONS.get(state, "󰍬"),
            "alt": state,
            "class": state,
            "tooltip": f"Iris : {LABELS_FR.get(state, state)}" + (f"\n{detail}" if detail else ""),
            "state": state,
            "detail": detail,
            "ts": time.time(),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.debug("état non écrit (%s) : %s", self.path, exc)
            return
        if self.waybar_signal > 0 and system.which("pkill"):
            system.run(["pkill", f"-RTMIN+{self.waybar_signal}", "waybar"], timeout=2)

    @staticmethod
    def read(path: Path | str | None = None) -> dict | None:
        p = Path(path) if path else default_status_file()
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def pid_file() -> Path:
    return default_status_file().parent / "iris.pid"
