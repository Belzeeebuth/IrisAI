"""Instances Prism Launcher (Minecraft) : « lance l'instance Astraworld ».

Chaque instance est un dossier de ``~/.local/share/PrismLauncher/instances/``. Le nom
affiché est lu dans son ``instance.cfg`` ; c'est le nom du dossier qui sert
d'identifiant à ``prismlauncher --launch``.

Le nom dit à voix haute est rapproché avec le même barème que les applications, pour
que « astra world » retrouve « Astraworld ».
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from iris.actions import system
from iris.actions.apps import match_score
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)

LAUNCHER = "prismlauncher"
_MIN_SCORE = 30.0  # même seuil que la résolution des applications


@dataclass(frozen=True)
class Instance:
    ident: str  # nom du dossier, attendu par --launch
    name: str  # nom affiché

    @property
    def names(self) -> tuple[str, ...]:
        found = (canonical(self.name), canonical(self.ident))
        return tuple(dict.fromkeys(n for n in found if n))


def directory() -> Path:
    data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    return Path(data) / "PrismLauncher" / "instances"


def available() -> bool:
    return system.which(LAUNCHER) is not None and directory().is_dir()


def instances() -> list[Instance]:
    return [
        Instance(path.parent.name, _display_name(path))
        for path in sorted(directory().glob("*/instance.cfg"))
    ]


def _display_name(cfg: Path) -> str:
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "name" and value.strip():
                return value.strip()
    except OSError as exc:
        log.debug("instance.cfg illisible (%s) : %s", cfg, exc)
    return cfg.parent.name


def resolve(query: str) -> Instance | None:
    """Meilleure instance pour un nom dit à voix haute, ou rien si aucune ne convient."""
    asked = canonical(query)
    if not asked:
        return None
    best: tuple[float, Instance] | None = None
    for instance in instances():
        score = max((match_score(asked, n) for n in instance.names), default=0.0)
        if score >= _MIN_SCORE and (best is None or score > best[0]):
            best = (score, instance)
    return best[1] if best else None


def launch(instance: Instance, launcher: str = "auto") -> None:
    if not system.launch([LAUNCHER, "--launch", instance.ident], launcher=launcher):
        raise RuntimeError(f"impossible de lancer l'instance {instance.name}")
