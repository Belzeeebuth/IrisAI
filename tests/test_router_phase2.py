import json

import pytest

from iris.actions import devices
from iris.config import Session, SessionApp
from iris.core.router import Router
from iris.llm.brain import Decision
from iris.nlu.intents import Intent, IntentParser


class FakeBrain:
    def __init__(self, answer: str = "Réponse du modèle.") -> None:
        self.answer = answer
        self.questions: list[str] = []

    def converse(self, text: str, language: str = "fr") -> str:
        self.questions.append(text)
        return self.answer


@pytest.fixture
def router(cfg, phrases, journal, fake_system):
    fake_system.available |= {"hyprctl", "wtype", "bluetoothctl", "rfkill", "makoctl", "wpctl"}
    cfg.bluetooth = {"mes écouteurs": "WH-1000XM5"}
    cfg.sessions = [Session("video", ["ma session vidéo"], [SessionApp("kdenlive", 3)])]
    return Router(cfg, phrases, journal, brain=FakeBrain())


def parse(text: str, sessions=None) -> Intent:
    intent = IntentParser(session_phrases=sessions).parse(text)
    assert intent is not None, text
    return intent


def test_type_text_and_dictation(router, fake_system):
    reply = router.execute(parse("écris : bonjour à tous"))
    assert reply.ok and reply.text == "C'est écrit."
    assert ["wtype", "--", "bonjour à tous"] in fake_system.calls
    assert router.execute(parse("mode dictée")).control == "dictate"
    assert router.execute(parse("fin de dictée")).control == "dictate_stop"


def test_dictation_requires_tool(router, fake_system):
    fake_system.available.discard("wtype")
    reply = router.execute(parse("mode dictée"))
    assert not reply.ok and "wtype" in reply.text


def test_monitors(router, fake_system):
    assert (
        router.execute(parse("envoie cette fenêtre sur l'écran de droite")).text
        == "Fenêtre envoyée sur l'écran de droite."
    )
    assert router.execute(parse("va sur l'écran de gauche")).text == "Écran de gauche."
    assert "hyprctl dispatch movewindow mon:r" in fake_system.joined_calls()
    assert "hyprctl dispatch focusmonitor l" in fake_system.joined_calls()


def test_bluetooth(router, fake_system):
    fake_system.outputs["bluetoothctl devices"] = "Device AC:12:2F:00:11:22 WH-1000XM5\n"
    fake_system.outputs["bluetoothctl connect"] = "Connection successful"
    assert router.execute(parse("active le bluetooth")).text == "Bluetooth activé."
    assert router.execute(parse("connecte mes écouteurs")).text == "WH-1000XM5 connecté."
    assert "bluetoothctl connect AC:12:2F:00:11:22" in fake_system.joined_calls()
    assert router.execute(parse("déconnecte mes écouteurs")).text == "WH-1000XM5 déconnecté."
    assert not router.execute(parse("déconnecte le grille-pain")).ok


def test_wifi_airplane_battery(router, fake_system, monkeypatch):
    assert router.execute(parse("coupe le wifi")).text == "Wi-Fi désactivé."
    assert router.execute(parse("mode avion")).text == "Mode avion activé."
    monkeypatch.setattr(devices, "battery", lambda: (64, "Discharging"))
    assert router.execute(parse("niveau de batterie")).text == "Batterie à 64 pour cent."
    monkeypatch.setattr(devices, "battery", lambda: (90, "Charging"))
    assert router.execute(parse("batterie")).text == "Batterie à 90 pour cent, en charge."
    monkeypatch.setattr(devices, "battery", lambda: None)
    assert not router.execute(parse("batterie")).ok


def test_notifications(router, fake_system):
    fake_system.outputs["makoctl history"] = json.dumps(
        {
            "data": [
                [
                    {
                        "app-name": {"data": "Signal"},
                        "summary": {"data": "Alice"},
                        "body": {"data": "Salut"},
                    }
                ]
            ]
        }
    )
    assert (
        router.execute(parse("lis mes notifications")).text
        == "1 notification : Signal : Alice, Salut."
    )
    assert router.execute(parse("efface les notifications")).text == "Notifications effacées."
    assert router.execute(parse("ne pas déranger")).text == "Mode ne pas déranger activé."
    assert "makoctl mode -a do-not-disturb" in fake_system.joined_calls()


def test_sessions(router, fake_system):
    fake_system.available.add("kdenlive")
    reply = router.execute(parse("ouvre ma session vidéo", {"video": ["ma session vidéo"]}))
    assert reply.text == "Session video ouverte, 1 application lancée."
    fake_system.outputs["hyprctl -j clients"] = json.dumps(
        [
            {"class": "kdenlive", "workspace": {"id": 3}},
            {"class": "kdenlive", "workspace": {"id": 5}},
        ]
    )
    assert (
        router.execute(parse("sauvegarde la session sous montage")).text
        == "Session montage enregistrée avec 2 applications."
    )


def test_ask_llm(router, journal):
    reply = router.execute(parse("pourquoi le ciel est bleu"))
    assert reply.ok and reply.text == "Réponse du modèle."
    assert router.brain.questions == ["pourquoi le ciel est bleu"]
    router.brain = None
    assert "modèle de langage" in router.execute(parse("explique-moi les workspaces")).text


def test_intent_from_decision(router):
    intent = router.intent_from_decision(Decision("action", "volume_set", {"n": "40"}, "Volume."))
    assert intent is not None and intent.slots == {"n": 40} and not intent.requires_confirmation
    assert router.intent_from_decision(Decision("action", "shutdown")).requires_confirmation
    assert router.intent_from_decision(Decision("action", "rm_rf")) is None
    assert router.intent_from_decision(Decision("action", "custom")) is None
    assert router.intent_from_decision(Decision("action", "volume_set", {"n": "abc"})).slots == {}
