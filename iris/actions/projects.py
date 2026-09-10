"""Projets : « ouvre le projet cnvs-clone » → éditeur + terminal dans le dossier.

Résolution : ``[projects]`` de la config (nom → chemin), puis les dossiers de ``system.project_dirs``
(un niveau de sous-dossiers, correspondance floue sur le nom).
"""

from __future__ import annotations

import logging
import shlex
from difflib import SequenceMatcher
from pathlib import Path

from iris.actions import system
from iris.actions.apps import AppResolver
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)

TERMINAL_CWD_FLAGS = {
    "ghostty": ["--working-directory={path}"],
    "alacritty": ["--working-directory", "{path}"],
    "kitty": ["--directory", "{path}"],
    "foot": ["--working-directory", "{path}"],
    "wezterm": ["start", "--cwd", "{path}"],
}


class ProjectResolver:
    def __init__(
        self,
        projects: dict[str, str] | None = None,
        dirs: list[str] | None = None,
        apps: AppResolver | None = None,
    ) -> None:
        self.projects = {canonical(k): Path(v).expanduser() for k, v in (projects or {}).items()}
        self.dirs = [Path(d).expanduser() for d in (dirs or [])]
        self.apps = apps or AppResolver()

    def candidates(self) -> dict[str, Path]:
        found: dict[str, Path] = dict(self.projects)
        for base in self.dirs:
            if not base.is_dir():
                continue
            try:
                for child in sorted(base.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        found.setdefault(canonical(child.name), child)
            except OSError:
                continue
        return found

    def resolve(self, query: str) -> Path | None:
        q = canonical(query).replace(" ", "-")
        if not q:
            return None
        candidates = self.candidates()
        for key, path in candidates.items():
            if key.replace(" ", "-") == q:
                return path
        best: tuple[float, Path] | None = None
        for key, path in candidates.items():
            k = key.replace(" ", "-")
            score = 0.85 if (q in k or k in q) else SequenceMatcher(None, q, k).ratio()
            if score >= 0.7 and (best is None or score > best[0]):
                best = (score, path)
        if best is None:
            direct = Path(query).expanduser()
            return direct if direct.is_dir() else None
        return best[1]

    def open(
        self, query: str, launcher: str = "auto", editor: bool = True, terminal: bool = True
    ) -> tuple[str, Path]:
        path = self.resolve(query)
        if path is None or not path.is_dir():
            raise RuntimeError(f"projet introuvable : {query}")
        launched = []
        if editor:
            app = self.apps.resolve("editor")
            if app is not None and app.argv:
                system.launch([*app.argv, str(path)], launcher=launcher)
                launched.append(Path(app.argv[0]).name)
        if terminal:
            argv = self.terminal_argv(path)
            if argv:
                system.launch(argv, launcher=launcher)
                launched.append(Path(argv[0]).name)
        if not launched:
            raise RuntimeError("ni éditeur ni terminal disponible")
        return path.name, path

    def terminal_argv(self, path: Path) -> list[str] | None:
        term = self.apps.resolve("terminal")
        if term is None or not term.argv:
            return None
        exe = Path(term.argv[0]).name
        flags = TERMINAL_CWD_FLAGS.get(exe)
        if flags:
            return [*term.argv, *[f.format(path=str(path)) for f in flags]]
        quoted = shlex.join(term.argv)
        return ["sh", "-c", f"cd {shlex.quote(str(path))} && exec {quoted}"]
