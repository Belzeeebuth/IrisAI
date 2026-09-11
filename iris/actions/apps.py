"""Ouvrir / fermer des applications par leur nom parlé.

Résolution d'un nom (« navigateur », « spotify », « prism launcher ») :
1. alias utilisateur (``[apps]`` de la config) ;
2. alias embarqués (``iris/data/apps.toml``) ;
3. exécutable du même nom dans le PATH ;
4. meilleure correspondance parmi les alias et les fichiers ``.desktop`` installés — nom,
   nom français, mot-clé, commande ou classe de fenêtre.

La dernière étape est volontairement tolérante : la voix passe par une transcription, et
« prismenscher » doit tout de même ouvrir Prism Launcher.
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import cached_property
from importlib import resources
from pathlib import Path

from iris.actions import hyprland, system
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)

_FIELD_CODES = re.compile(r"%[fFuUdDnNickvm]")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Note de correspondance entre le nom entendu et une application, de 0 à 100.
_SURE = 68.0  # au-dessus : correspondance franche (exacte, préfixe, mêmes mots…)
_MAYBE = 30.0  # en dessous : on préfère répondre qu'on n'a pas trouvé
_KEYWORD = 74.0  # mot-clé exact d'un .desktop (« minecraft » → Prism Launcher)
_FUZZY_MIN = 0.72  # ressemblance globale suffisante à elle seule
_PARTIAL_MIN = 0.55  # ressemblance plus lâche, admise si un mot marquant est commun
_SHAPE_SPAN = 0.7  # écart de longueur toléré entre deux noms de même forme
_WORD_MIN = 0.86  # ressemblance entre deux mots pris isolément
_WORD_LEN = 4  # en deçà, un mot commun ne prouve rien (« le », « son »)


@dataclass
class ResolvedApp:
    query: str
    label: str
    argv: list[str] | None = None  # commande à lancer
    webapp: str | None = None  # URL de web-app
    match_keys: tuple[str, ...] = ()  # motifs pour retrouver ses fenêtres
    source: str = ""


def _squash(text: str) -> str:
    return text.replace(" ", "")


def _same_word(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= _WORD_MIN


def _prefix_of_words(a: str, b: str) -> bool:
    """L'un des deux noms commence l'autre, en s'arrêtant sur une fin de mot.

    « prism » annonce bien « prism launcher », alors que « obs » ne dit rien
    de « obsidienne » et « foot » rien de « football manager ».
    """
    long, short = (a, b) if len(a) >= len(b) else (b, a)
    return long.startswith(short) and (len(long) == len(short) or long[len(short)] == " ")


def _shares_word(asked: list[str], found: list[str]) -> bool:
    """Un mot marquant est commun aux deux noms (« prism » dans « prism lensure »)."""
    return any(len(a) >= _WORD_LEN and any(_same_word(a, b) for b in found) for a in asked)


def _same_shape(asked: list[str], found: list[str]) -> bool:
    """Même nombre de mots et longueur voisine : au plus un mot a été mal transcrit.

    « prism lensure » a la forme de « prism launcher ». « cloud code » n'a ni celle de
    « code » ni celle de « opencode » : un mot entier y resterait inexpliqué, et c'est
    ainsi que « lance Claude Code » a pu ouvrir l'éditeur.
    """
    if len(asked) != len(found):
        return False
    a, b = len("".join(asked)), len("".join(found))
    return min(a, b) >= _SHAPE_SPAN * max(a, b)


def match_score(asked: str, name: str) -> float:
    """À quel point l'application ``name`` répond à la demande ``asked``, de 0 à 100.

    Au-delà de ``_SURE`` la correspondance est franche ; en dessous elle repose sur une
    ressemblance et ne sert qu'à rattraper une transcription imparfaite.
    """
    if not asked or not name:
        return 0.0
    if name == asked:
        return 100.0
    if _squash(name) == _squash(asked):
        return 92.0  # « libre office writer » → « libreoffice writer »
    if _prefix_of_words(asked, name):
        return 84.0  # « prism » → « prism launcher »
    asked_words, name_words = asked.split(), name.split()
    if all(w in name_words for w in asked_words):
        return 76.0  # « launcher prism » désigne bien « prism launcher »
    if asked in name:
        return 68.0
    matcher = SequenceMatcher(None, _squash(asked), _squash(name))
    # Deux bornes supérieures bon marché avant le calcul complet : l'écrasante majorité
    # des applications installées n'a rien à voir avec ce qui vient d'être dit.
    if matcher.real_quick_ratio() < _PARTIAL_MIN or matcher.quick_ratio() < _PARTIAL_MIN:
        return 0.0
    ratio = matcher.ratio()
    if ratio >= _FUZZY_MIN:
        return 40.0 + 20.0 * ratio  # « prismenscher » → « prism launcher »
    if (
        ratio >= _PARTIAL_MIN
        and _same_shape(asked_words, name_words)
        and _shares_word(asked_words, name_words)
    ):
        return 20.0 + 20.0 * ratio  # « prism lensure » : un mot juste, l'autre approché
    return 0.0


@dataclass(frozen=True)
class DesktopEntry:
    """Ce qu'on retient d'un fichier ``.desktop`` installé."""

    name: str
    exec_line: str
    desktop_id: str
    terminal: bool = False
    wm_class: str = ""
    localized: str = ""  # Name[fr]
    keywords: tuple[str, ...] = ()

    @cached_property
    def command(self) -> str:
        parts = _FIELD_CODES.sub("", self.exec_line).split()
        return Path(parts[0]).name if parts else ""

    @cached_property
    def names(self) -> tuple[str, ...]:
        """Tous les noms sous lesquels l'application peut être demandée."""
        stem = self.desktop_id.removesuffix(".desktop").rsplit(".", 1)[-1]
        found = (self.name, self.localized, _CAMEL.sub(" ", stem), self.command, self.wm_class)
        return tuple(dict.fromkeys(c for c in (canonical(n) for n in found) if c))

    def score(self, asked: str) -> float:
        best = max((match_score(asked, n) for n in self.names), default=0.0)
        return max(best, _KEYWORD if asked in self.keywords else 0.0)


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
        self._alias_cache = {
            key: [canonical(n) for n in entry.get("names", [])] + [key]
            for key, entry in self.builtin.items()
        }
        self._desktop_cache: list[DesktopEntry] | None = None

    # ------------------------------------------------------------------ résolution
    def resolve(self, query: str) -> ResolvedApp | None:
        full = canonical(query)
        q = re.sub(
            r"^(?:l'|le |la |les |un |une |mon |ma |mes |the |my |a |an )?"
            r"(?:nouvelle |nouveau |nouvel |new )?"
            r"(?:application |app |appli |logiciel |programme |jeu |jeux |game "
            r"|page |onglet |fenetre |tab |window )?"
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
            if any(v in self._alias_names(key, entry) for v in variants):
                app = self._from_alias(q, key, entry)
                if app:
                    return app

        # 3. exécutable direct — on préfère son .desktop, qui donne un nom présentable
        for candidate in (q, q.replace(" ", "-"), _squash(q)):
            if system.which(candidate):
                entry = self._entry_for_command(candidate)
                app = self._from_desktop(q, entry) if entry else None
                return app or ResolvedApp(
                    q, candidate, [candidate], match_keys=(candidate,), source="path"
                )

        # 4. meilleure correspondance, y compris approximative
        return self._best_match(q)

    def _alias_names(self, key: str, entry: dict) -> list[str]:
        return self._alias_cache.get(key) or [canonical(n) for n in entry.get("names", [])] + [key]

    def _best_match(self, q: str) -> ResolvedApp | None:
        """Passe tout le catalogue en revue et garde la meilleure correspondance.

        Les candidats sont essayés du mieux noté au moins bon : un alias dont aucun
        exécutable n'est installé laisse sa place au suivant.
        """
        candidates: list[tuple[float, int, Callable[[], ResolvedApp | None]]] = []

        for name, command in self.user_aliases.items():
            score = match_score(q, name)
            if score >= _MAYBE:
                candidates.append(
                    (
                        score,
                        -len(name),
                        lambda n=name, c=command: self._from_command(n, c, "config"),
                    )
                )

        for key, entry in self.builtin.items():
            score = max(match_score(q, n) for n in self._alias_names(key, entry))
            if score >= _MAYBE:
                candidates.append(
                    (score, -len(key), lambda k=key, e=entry: self._from_alias(q, k, e))
                )

        for entry in self._desktop_entries():
            score = entry.score(q)
            if score >= _MAYBE:
                candidates.append(
                    (score, -len(entry.name), lambda e=entry: self._from_desktop(q, e))
                )

        for score, _tie, build in sorted(candidates, key=lambda c: (c[0], c[1]), reverse=True):
            app = build()
            if app is not None:
                if score < _SURE:
                    log.info("« %s » rapproché de « %s » (%.0f/100)", q, app.label, score)
                return app
        return None

    def _from_alias(self, query: str, key: str, entry: dict) -> ResolvedApp | None:
        override = self.overrides.get(key)
        commands = ([override] if override else []) + list(entry.get("exec", []))
        app = self._first_available(query, commands, key)
        if app is not None:
            app.match_keys = tuple({key, *self._alias_names(key, entry), *app.match_keys})
        return app

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
    def _desktop_entries(self) -> list[DesktopEntry]:
        if self._desktop_cache is not None:
            return self._desktop_cache
        dirs = [
            Path(p) / "applications"
            for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        ]
        dirs.insert(
            0, Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
        )
        entries: list[DesktopEntry] = []
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

    def _entry_for_command(self, command: str) -> DesktopEntry | None:
        for entry in self._desktop_entries():
            if entry.command == command:
                return entry
        return None

    def _from_desktop(self, q: str, entry: DesktopEntry) -> ResolvedApp | None:
        try:
            argv = system.expand(_FIELD_CODES.sub("", entry.exec_line))
        except ValueError:
            return None
        if not argv:
            return None
        if entry.terminal:
            term = self.resolve("terminal")
            if term and term.argv:
                argv = [*term.argv, "-e", *argv]
        keys = {
            Path(argv[0]).name,
            entry.wm_class,
            entry.desktop_id.removesuffix(".desktop"),
            *entry.names,
        }
        return ResolvedApp(
            q,
            entry.name,
            argv,
            match_keys=tuple(sorted(k for k in keys if k)),
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


def _parse_desktop(path: Path) -> DesktopEntry | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_main = False
    fields: dict[str, str] = {}
    hidden = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_main = line == "[Desktop Entry]"
            continue
        if not in_main or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in ("NoDisplay", "Hidden") and value.lower() == "true":
            hidden = True
        elif key == "Type" and value != "Application":
            return None
        elif key not in fields:
            fields[key] = value
    name, exec_line = fields.get("Name", ""), fields.get("Exec", "")
    if hidden or not name or not exec_line:
        return None
    keywords = [
        canonical(word)
        for entry in ("Keywords", "Keywords[fr]")
        for word in fields.get(entry, "").split(";")
        if canonical(word)
    ]
    return DesktopEntry(
        name=name,
        exec_line=exec_line,
        desktop_id=path.name,
        terminal=fields.get("Terminal", "").lower() == "true",
        wm_class=fields.get("StartupWMClass", ""),
        localized=fields.get("Name[fr]", ""),
        keywords=tuple(dict.fromkeys(keywords)),
    )
