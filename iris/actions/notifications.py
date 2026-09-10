"""Notifications bureau via mako (``makoctl``) : historique, effacement, ne pas déranger."""

from __future__ import annotations

import json
from dataclasses import dataclass

from iris.actions import system


@dataclass
class Notification:
    app: str
    summary: str
    body: str


def _makoctl(*args: str) -> str:
    if not system.which("makoctl"):
        raise RuntimeError("makoctl n'est pas installé (mako)")
    res = system.run(["makoctl", *args], timeout=5)
    if not res.ok:
        raise RuntimeError(res.err or "makoctl a échoué")
    return res.out


def _field(entry: dict, key: str) -> str:
    value = entry.get(key)
    if isinstance(value, dict):
        value = value.get("data", "")
    return str(value or "").strip()


def history(limit: int = 5) -> list[Notification]:
    """Dernières notifications (les plus récentes d'abord)."""
    raw = _makoctl("history")
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("historique mako illisible") from exc
    entries: list[dict] = []
    for group in data.get("data", []):
        entries.extend(
            e for e in (group if isinstance(group, list) else [group]) if isinstance(e, dict)
        )
    result = [
        Notification(_field(e, "app-name"), _field(e, "summary"), _field(e, "body"))
        for e in entries
    ]
    return [n for n in result if n.summary or n.body][:limit]


def dismiss_all() -> None:
    _makoctl("dismiss", "--all")


def do_not_disturb(state: bool | None) -> bool:
    """Active/désactive le mode ``do-not-disturb`` de mako (None = bascule). Retourne l'état final."""
    if state is None:
        out = _makoctl("mode", "-t", "do-not-disturb")
    elif state:
        out = _makoctl("mode", "-a", "do-not-disturb")
    else:
        out = _makoctl("mode", "-r", "do-not-disturb")
    return "do-not-disturb" in out


def summarize(notifications: list[Notification], lang: str = "fr") -> str:
    if not notifications:
        return "Aucune notification récente." if lang == "fr" else "No recent notifications."
    parts = []
    for n in notifications:
        head = f"{n.app} : " if n.app else ""
        body = f", {n.body}" if n.body and n.body != n.summary else ""
        parts.append(f"{head}{n.summary}{body}"[:160])
    intro = (
        f"{len(notifications)} notification{'s' if len(notifications) > 1 else ''} : "
        if lang == "fr"
        else f"{len(notifications)} notification{'s' if len(notifications) > 1 else ''}: "
    )
    return intro + ". ".join(parts) + "."
