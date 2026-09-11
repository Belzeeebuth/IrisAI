"""Installation du service utilisateur systemd (lancement automatique avec la session graphique)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from iris import paths
from iris.actions import system

UNIT_NAME = "iris.service"

UNIT_TEMPLATE = """[Unit]
Description=Iris — assistant vocal pour Omarchy OS
Documentation=https://github.com/belzeeebuth/irisai
# Démarre avec la session Hyprland (UWSM active graphical-session.target) et s'arrête avec elle.
PartOf=graphical-session.target
After=graphical-session.target pipewire.service wireplumber.service

[Service]
Type=simple
ExecStart={exec_path} run
Restart=on-failure
RestartSec=3
TimeoutStopSec=10
Environment=PYTHONUNBUFFERED=1
# Le modèle Whisper fragmente beaucoup le tas : sans ce seuil, la glibc conserve
# ~300 Mo déjà libérés au lieu de les rendre au système.
Environment=MALLOC_TRIM_THRESHOLD_=131072
# Iris ne doit jamais faire tomber la session : on la met à part et on limite ses caprices.
Slice=background.slice
Nice=5

[Install]
WantedBy=graphical-session.target
"""


def iris_executable() -> str:
    """Chemin absolu de la commande `iris` (venv ou ~/.local/bin)."""
    for candidate in (
        Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0].endswith("iris") else None,
        Path(sys.executable).parent / "iris",
        Path.home() / ".local/bin/iris",
        Path(shutil.which("iris") or ""),
    ):
        if candidate and candidate.is_file():
            return str(candidate)
    return f"{sys.executable} -m iris"


def unit_path() -> Path:
    return paths.systemd_user_dir() / UNIT_NAME


def render_unit(exec_path: str | None = None) -> str:
    return UNIT_TEMPLATE.format(exec_path=exec_path or iris_executable())


def install(enable: bool = True, start: bool = True) -> list[str]:
    messages: list[str] = []
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_unit(), encoding="utf-8")
    messages.append(f"Unité écrite : {path}")
    if not system.which("systemctl"):
        messages.append("systemctl introuvable : active le service manuellement.")
        return messages
    system.run(["systemctl", "--user", "daemon-reload"])
    if enable:
        res = system.run(["systemctl", "--user", "enable", UNIT_NAME])
        messages.append(
            "Service activé au démarrage de la session." if res.ok else f"enable : {res.err}"
        )
    if start:
        res = system.run(["systemctl", "--user", "restart", UNIT_NAME])
        messages.append("Service démarré." if res.ok else f"start : {res.err}")
    messages.append(f"Journal : journalctl --user -u {UNIT_NAME} -f")
    return messages


def uninstall() -> list[str]:
    messages: list[str] = []
    if system.which("systemctl"):
        system.run(["systemctl", "--user", "disable", "--now", UNIT_NAME])
        messages.append("Service arrêté et désactivé.")
    path = unit_path()
    if path.exists():
        path.unlink()
        messages.append(f"Unité supprimée : {path}")
    if system.which("systemctl"):
        system.run(["systemctl", "--user", "daemon-reload"])
    return messages


def status() -> str:
    if not system.which("systemctl"):
        return "systemctl introuvable"
    res = system.run(["systemctl", "--user", "status", "--no-pager", UNIT_NAME])
    return res.out or res.err
