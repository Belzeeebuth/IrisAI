"""Navigateurs nommés et mots « page / onglet / fenêtre » devant un nom d'application."""

from __future__ import annotations

import pytest

from iris.actions.apps import AppResolver
from iris.nlu.intents import IntentParser

parse = IntentParser([]).parse


@pytest.fixture
def resolver(fake_system):
    fake_system.available.update({"omarchy-launch-browser", "chromium", "firefox"})
    return AppResolver()


def test_named_browser_launches_itself(resolver):
    assert resolver.resolve("firefox").argv == ["firefox"]
    assert resolver.resolve("chrome").argv == ["chromium"]


def test_generic_browser_uses_default(resolver):
    assert resolver.resolve("le navigateur").argv == ["omarchy-launch-browser"]


@pytest.mark.parametrize(
    "query",
    ["une page firefox", "une nouvelle page firefox", "un onglet firefox", "la fenêtre de firefox", "new firefox tab"],
)
def test_page_words_are_ignored(resolver, query):
    app = resolver.resolve(query)
    assert app is not None and app.argv == ["firefox"]


@pytest.mark.parametrize(
    ("text", "name", "app"),
    [
        ("lance moi une page firefox", "open_app", "firefox"),
        ("ouvre un nouvel onglet firefox", "open_app", "firefox"),
        ("open a new firefox window", "open_app", "firefox"),
        ("ferme la page spotify", "close_app", "spotify"),
    ],
)
def test_open_close_intents_strip_page_words(text, name, app):
    intent = parse(text)
    assert intent is not None and intent.name == name
    assert intent.slot("app") == app


@pytest.mark.parametrize("text", ["ferme cette page", "ferme cet onglet", "close this tab"])
def test_close_this_page_closes_active_window(text):
    intent = parse(text)
    assert intent is not None and intent.name == "window_close"
