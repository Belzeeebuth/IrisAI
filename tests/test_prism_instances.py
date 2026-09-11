"""Instances Prism Launcher : « lance l'instance Astraworld »."""

from __future__ import annotations

import pytest

from iris.actions import prism
from iris.core.router import Router
from iris.nlu.intents import Intent, IntentParser

parse = IntentParser([]).parse

INSTANCES = {
    "Astraworld": "Astraworld",
    "Oasis 2.0": "Oasis 2.0",
    "OptiFine for Fabric": "OptiFine for Fabric",
    "vieux-dossier": "",  # instance.cfg sans « name= » : le dossier fait foi
}


@pytest.fixture
def prism_home(fake_system, tmp_path, monkeypatch):
    root = tmp_path / "PrismLauncher" / "instances"
    for folder, name in INSTANCES.items():
        d = root / folder
        d.mkdir(parents=True)
        body = "[General]\nInstanceType=OneSix\n" + (f"name={name}\n" if name else "")
        (d / "instance.cfg").write_text(body, encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    fake_system.available.add(prism.LAUNCHER)
    return fake_system


def test_instances_lues_depuis_le_disque(prism_home):
    assert prism.available()
    assert [i.name for i in prism.instances()] == [
        "Astraworld",
        "Oasis 2.0",
        "OptiFine for Fabric",
        "vieux-dossier",  # repli sur le nom du dossier
    ]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Astraworld", "Astraworld"),
        ("astra world", "Astraworld"),  # ce que la voix donne
        ("oasis 2.0", "Oasis 2.0"),
        ("optifine", "OptiFine for Fabric"),
        ("vieux dossier", "vieux-dossier"),
    ],
)
def test_resolution_tolerante(prism_home, query, expected):
    found = prism.resolve(query)
    assert found is not None and found.ident == expected


@pytest.mark.parametrize("query", ["", "machin truc", "qwertyuiop"])
def test_rien_plutot_quune_mauvaise_partie(prism_home, query):
    assert prism.resolve(query) is None


@pytest.mark.parametrize(
    ("text", "instance"),
    [
        ("lance l'instance Astra World", "astra world"),
        ("ouvre l'instance oasis 2.0", "oasis 2.0"),
        ("lance la partie waylandcraft", "waylandcraft"),
        ("launch the world astraworld", "astraworld"),
    ],
)
def test_intention_reconnue(text, instance):
    intent = parse(text)
    assert intent is not None and intent.name == "open_instance"
    assert intent.slot("instance") == instance


def test_une_application_reste_une_application():
    """Sans le mot « instance », on parle toujours d'une application."""
    intent = parse("lance prism launcher")
    assert intent is not None and intent.name == "open_app"


def test_routeur_lance_linstance(prism_home, cfg, phrases):
    router = Router(cfg, phrases)
    reply = router.execute(Intent("open_instance", {"instance": "astra world"}))
    assert reply.ok and "Astraworld" in reply.text
    assert prism_home.launched[-1] == ["prismlauncher", "--launch", "Astraworld"]


def test_routeur_liste_les_parties_connues(prism_home, cfg, phrases):
    router = Router(cfg, phrases)
    reply = router.execute(Intent("open_instance", {"instance": "nawak"}))
    assert not reply.ok
    assert "Astraworld" in reply.text and "Oasis 2.0" in reply.text
    assert not prism_home.launched
