"""Sessions de workspaces nommées : ouvrir un ensemble d'applications sur leurs workspaces,
sauvegarder les fenêtres ouvertes sous un nom (journal, table ``prefs``)."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from pathlib import Path

from iris.actions import hyprland, system
from iris.actions.apps import AppResolver
from iris.config import Session, SessionApp
from iris.core.journal import Journal
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)
PREF_PREFIX = "session."


class SessionManager:
    def __init__(self, sessions: list[Session], journal: Journal | None, apps: AppResolver) -> None:
        self.configured = {canonical(s.name): s for s in sessions}
        self.journal = journal
        self.apps = apps

    # ------------------------------------------------------------------ résolution
    def names(self) -> list[str]:
        names = [s.name for s in self.configured.values()]
        if self.journal is not None:
            names += [
                k[len(PREF_PREFIX) :] for k in self.journal.all_prefs() if k.startswith(PREF_PREFIX)
            ]
        return sorted(set(names))

    def find(self, query: str) -> Session | None:
        q = canonical(query)
        for session in self.configured.values():
            if q == canonical(session.name) or any(q == canonical(p) for p in session.phrases):
                return session
        saved = self._saved(q)
        if saved is not None:
            return saved
        best: tuple[float, Session] | None = None
        for session in self.configured.values():
            for phrase in [session.name, *session.phrases]:
                ratio = SequenceMatcher(None, q, canonical(phrase)).ratio()
                if ratio >= 0.8 and (best is None or ratio > best[0]):
                    best = (ratio, session)
        return best[1] if best else None

    def _saved(self, q: str) -> Session | None:
        if self.journal is None:
            return None
        data = self.journal.get_pref(PREF_PREFIX + q)
        if not isinstance(data, list):
            return None
        apps = [
            SessionApp(exec=str(a.get("exec")), workspace=a.get("workspace"))
            for a in data
            if isinstance(a, dict) and a.get("exec")
        ]
        return Session(name=q, phrases=[q], apps=apps) if apps else None

    # ------------------------------------------------------------------ actions
    def open(self, query: str, launcher: str = "auto") -> tuple[str, int]:
        session = self.find(query)
        if session is None:
            raise RuntimeError(
                f"session inconnue : {query}"
                + (f" (disponibles : {', '.join(self.names())})" if self.names() else "")
            )
        launched = 0
        hypr = hyprland.available()
        for app in session.apps:
            if app.workspace is not None and hypr:
                try:
                    hyprland.switch_workspace(app.workspace)
                except RuntimeError as exc:
                    log.warning("workspace %s : %s", app.workspace, exc)
            resolved = self.apps.resolve(app.exec)
            if resolved is not None and resolved.argv:
                ok = system.launch(resolved.argv, launcher=launcher)
            elif resolved is not None and resolved.webapp:
                from iris.actions import omarchy

                omarchy.launch_webapp(resolved.webapp, launcher)
                ok = True
            else:
                ok = system.launch(app.exec, launcher=launcher, shell=True)
            launched += int(bool(ok))
        return session.name, launched

    def save(self, name: str) -> int:
        """Enregistre les fenêtres ouvertes (classe → commande) ; retourne le nombre d'applications."""
        if self.journal is None:
            raise RuntimeError("journal indisponible")
        if not hyprland.available():
            raise RuntimeError("Hyprland injoignable")
        apps: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for client in hyprland.clients():
            cls = str(client.get("class") or client.get("initialClass") or "").strip()
            ws = client.get("workspace", {})
            ws_id = int(ws.get("id", 0)) if isinstance(ws, dict) else 0
            if not cls or ws_id <= 0 or (cls, ws_id) in seen:
                continue
            seen.add((cls, ws_id))
            command = self._command_for_class(cls)
            if command:
                apps.append({"exec": command, "workspace": ws_id})
        if not apps:
            raise RuntimeError("aucune fenêtre à enregistrer")
        self.journal.set_pref(PREF_PREFIX + canonical(name), apps)
        return len(apps)

    def _command_for_class(self, window_class: str) -> str | None:
        lowered = window_class.lower()
        for candidate in (lowered, lowered.split(".")[-1], lowered.replace(" ", "-")):
            if system.which(candidate):
                return candidate
        resolved = self.apps.resolve(lowered.split(".")[-1])
        if resolved is not None and resolved.argv:
            return " ".join(resolved.argv)
        if resolved is not None and resolved.webapp:
            return f"webapp:{resolved.webapp}"
        return Path(lowered).name or None
