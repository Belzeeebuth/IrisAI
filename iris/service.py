"""Installation du service utilisateur systemd (lancement automatique avec la session graphique)."""

from __future__ import annotations

import shutil
import sys
import time
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


def installed() -> bool:
    """L'unité est-elle connue de systemd ? (elle peut venir d'ailleurs que `install`)"""
    if unit_path().exists():
        return True
    if not system.which("systemctl"):
        return False
    return system.run(["systemctl", "--user", "cat", UNIT_NAME]).ok


def active() -> bool:
    return system.run(["systemctl", "--user", "is-active", UNIT_NAME]).out.strip() == "active"


def ready_since(moment: float) -> bool:
    """Iris a-t-elle écrit son état après *moment* ?

    Le fichier d'état survit à l'arrêt du service : sans la comparaison d'horodatage,
    on prendrait l'état laissé par l'instance précédente pour une preuve de vie.
    """
    from iris.core.status import StatusWriter

    data = StatusWriter.read() or {}
    try:
        written = float(data.get("ts", 0.0))
    except (TypeError, ValueError):
        return False
    return written >= moment and data.get("state") not in (None, "", "off")


def restart(wait_s: float = 30.0) -> tuple[bool, list[str]]:
    """Relance le service, puis attend qu'Iris écoute de nouveau (chargement du modèle compris)."""
    if not system.which("systemctl"):
        return False, ["systemctl introuvable : relance « iris run » à la main."]
    if not installed():
        return False, [
            f"Service non installé ({unit_path()}) : lance d'abord `iris service install`."
        ]

    res = system.run(["systemctl", "--user", "restart", UNIT_NAME], timeout=30)
    if not res.ok:
        return False, [f"Relance impossible : {(res.err or res.out).strip()}", _journal_hint()]
    # Après `restart`, l'ancien processus est mort : tout état plus récent vient du nouveau.
    started = time.time()
    messages = ["Service relancé."]

    deadline = time.monotonic() + max(wait_s, 0.0)
    while time.monotonic() < deadline:
        if ready_since(started):
            messages.append(f"Iris écoute de nouveau (prête en {time.time() - started:.0f} s).")
            return True, messages
        if not active():
            messages += [
                f"Le service s'est arrêté aussitôt (état : {_active_state()}).",
                _journal_hint(),
            ]
            return False, messages
        time.sleep(0.3)

    messages += [
        f"Toujours pas d'écoute après {wait_s:.0f} s — le service tourne, mais il démarre mal.",
        _journal_hint(),
    ]
    return False, messages


def _active_state() -> str:
    return system.run(["systemctl", "--user", "is-active", UNIT_NAME]).out.strip() or "inconnu"


def _journal_hint() -> str:
    return f"Journal : journalctl --user -u {UNIT_NAME} -n 50 --no-pager"


def status() -> str:
    if not system.which("systemctl"):
        return "systemctl introuvable"
    res = system.run(["systemctl", "--user", "status", "--no-pager", UNIT_NAME])
    return res.out or res.err
