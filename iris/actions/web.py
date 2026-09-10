"""Ouverture d'URL et recherche web (navigateur par défaut)."""

from __future__ import annotations

from urllib.parse import quote_plus

from iris.actions import system


def open_url(url: str, launcher: str = "auto") -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if system.which("omarchy-launch-browser"):
        ok = system.launch(["omarchy-launch-browser", url], launcher=launcher)
    else:
        ok = system.launch(["xdg-open", url], launcher=launcher)
    if not ok:
        raise RuntimeError("impossible d'ouvrir le navigateur")
    return url


def search(query: str, template: str, launcher: str = "auto") -> str:
    url = template.format(q=quote_plus(query))
    return open_url(url, launcher)
