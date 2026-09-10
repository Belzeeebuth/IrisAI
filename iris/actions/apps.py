"""Ouvrir / fermer des applications par leur nom parlé.

Résolution d'un nom (« navigateur », « spotify », « obsidian ») :
1. alias utilisateur (``[apps]`` de la config) ;
2. alias embarqués (``iris/data/apps.toml``) ;
3. exécutable du même nom dans le PATH ;
4. fichier ``.desktop`` dont le ``Name`` correspond.
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from iris.actions import hyprland, system
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)

_FIELD_CODES = re.compile(r"%[fFuUdDnNickvm]")


@dataclass
class ResolvedApp:
    query: str
    label: str
    argv: list[str] | None = None  # commande à lancer
    webapp: str | None = None  # URL de web-app
    match_keys: tuple[str, ...] = ()  # motifs pour retrouver ses fenêtres
    source: str = ""


def _load_builtin_aliases() -> dict[str, dict]:
    text = resources.files("iris.data").joinpath("apps.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


class AppResolver:
    def __init__(
        self,
        user_aliases: dict[str, str] | None = None,
        terminal: str = "",
        browser: str = "",
        editor: str = "",
    ) -> None:
        self.user_aliases = {canonical(k): v for k, v in (user_aliases or {}).items()}
        self.builtin = _load_builtin_aliases()
        self.overrides = {"terminal": terminal, "browser": browser, "editor": editor}
        self._desktop_cache: list[tuple[str, str, str, bool]] | None = None

    # ------------------------------------------------------------------ résolution
    def resolve(self, query: str) -> ResolvedApp | None:
        full = canonical(query)
        q = re.sub(
            r"^(?:l'|le |la |les |un |une |mon |ma |mes |the |my |a |an )?"
            r"(?:nouvelle |nouveau |nouvel |new )?"
            r"(?:application |app |appli |logiciel |programme |page |onglet |fenetre |tab |window )?"
            r"(?:de |d'|of )?",
            "",
            full,
        ).strip()
        q = re.sub(r"\s+(?:page|onglet|fenetre|tab|window)$", "", q).strip()
        if not q:
            return None
        variants = [full, q] if full != q else [q]

        # 1. alias utilisateur (avec ou sans article : « mon éditeur » / « éditeur »)
        for variant in variants:
            if variant in self.user_aliases:
                return self._from_command(variant, self.user_aliases[variant], "config")

        # 2. alias embarqués
        for key, entry in self.builtin.items():
            names = [canonical(n) for n in entry.get("names", [])] + [key]
            if any(v in names for v in variants):
                override = self.overrides.get(key)
                candidates = ([override] if override else []) + list(entry.get("exec", []))
                app = self._first_available(q, candidates, key)
                if app:
                    app.match_keys = tuple({key, *names, *(app.match_keys)})
                    return app

        # 3. exécutable direct
        for candidate in (q, q.replace(" ", "-"), q.replace(" ", "")):
            if system.which(candidate):
                return ResolvedApp(
                    q, candidate, [candidate], match_keys=(candidate,), source="path"
                )

        # 4. fichier .desktop
        return self._from_desktop(q)

    def _first_available(self, query: str, candidates: list[str], key: str) -> ResolvedApp | None:
        for command in candidates:
            app = self._from_command(
                query, command, "alias", label=key if command.startswith("webapp:") else None
            )
            if app is not None:
                return app
        return None

    def _from_command(
        self, query: str, command: str, source: str, label: str | None = None
    ) -> ResolvedApp | None:
        command = command.strip()
        if not command:
            return None
        if command.startswith("webapp:"):
            url = command[len("webapp:") :]
            return ResolvedApp(
                query, label or query, webapp=url, match_keys=(query,), source=source
            )
        try:
            argv = system.expand(command)
        except ValueError:
            return None
        if not argv or not argv[0]:
            return None  # variable d'environnement vide ($TERMINAL non défini)
        if system.which(argv[0]) is None:
            return None
        exe = Path(argv[0]).name
        display = exe
        if "-e" in argv:
            i = argv.index("-e")
            if i + 1 < len(argv) and argv[i + 1]:
                # « $TERMINAL -e prog » : on annonce « prog », pas le terminal qui l'héberge.
                display = Path(argv[i + 1]).name
        return ResolvedApp(query, label or display, argv, match_keys=(exe, query), source=source)

    # ------------------------------------------------------------------ .desktop
    def _desktop_entries(self) -> list[tuple[str, str, str, bool]]:
        if self._desktop_cache is not None:
            return self._desktop_cache
        dirs = [
            Path(p) / "applications"
            for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        ]
        dirs.insert(
            0, Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
        )
        entries: list[tuple[str, str, str, bool]] = []
        seen: set[str] = set()
        for d in dirs:
            if not d.is_dir():
                continue
            for path in sorted(d.glob("*.desktop")):
                if path.name in seen:
                    continue
                seen.add(path.name)
                entry = _parse_desktop(path)
                if entry:
                    entries.append(entry)
        self._desktop_cache = entries
        return entries

    def _from_desktop(self, q: str) -> ResolvedApp | None:
        best: tuple[int, tuple[str, str, str, bool]] | None = None
        for entry in self._desktop_entries():
            name = canonical(entry[0])
            if name == q:
                score = 3
            elif name.startswith(q) or q.startswith(name):
                score = 2
            elif q in name:
                score = 1
            else:
                continue
            if best is None or score > best[0]:
                best = (score, entry)
        if best is None:
            return None
        name, exec_line, desktop_id, terminal = best[1]
        argv = system.expand(_FIELD_CODES.sub("", exec_line))
        if terminal:
            term = self.resolve("terminal")
            if term and term.argv:
                argv = [*term.argv, "-e", *argv]
        exe = Path(argv[0]).name if argv else desktop_id
        return ResolvedApp(
            q,
            name,
            argv,
            match_keys=(exe, canonical(name), desktop_id.removesuffix(".desktop")),
            source="desktop",
        )

    # ------------------------------------------------------------------ actions
    def open(self, query: str, launcher: str = "auto") -> ResolvedApp | None:
        app = self.resolve(query)
        if app is None:
            return None
        if app.webapp:
            from iris.actions import omarchy

            omarchy.launch_webapp(app.webapp, launcher)
            return app
        assert app.argv
        if not system.launch(app.argv, launcher=launcher):
            raise RuntimeError(f"impossible de lancer {app.label}")
        return app

    def close(self, query: str) -> tuple[ResolvedApp | None, int]:
        """Ferme les fenêtres correspondantes. Retourne (app résolue, nombre de fenêtres fermées)."""
        app = self.resolve(query)
        keys = list(app.match_keys) if app else [canonical(query)]
        closed = 0
        if hyprland.available():
            for client in hyprland.find_clients(*keys):
                try:
                    hyprland.close_window(client["address"])
                    closed += 1
                except (RuntimeError, KeyError) as exc:
                    log.warning("fermeture impossible : %s", exc)
        if closed == 0 and app and app.argv and system.which("pkill"):
            exe = Path(app.argv[0]).name
            if (
                exe not in {"sh", "bash", "uwsm", "xdg-open"}
                and system.run(["pkill", "-x", exe]).ok
            ):
                closed = 1
        return app, closed


def _parse_desktop(path: Path) -> tuple[str, str, str, bool] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_main = False
    name = exec_line = ""
    terminal = False
    hidden = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_main = line == "[Desktop Entry]"
            continue
        if not in_main or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "Name" and not name:
            name = value
        elif key == "Exec":
            exec_line = value
        elif key == "Terminal":
            terminal = value.lower() == "true"
        elif key in ("NoDisplay", "Hidden") and value.lower() == "true":
            hidden = True
        elif key == "Type" and value != "Application":
            return None
    if hidden or not name or not exec_line:
        return None
    return name, exec_line, path.name, terminal
