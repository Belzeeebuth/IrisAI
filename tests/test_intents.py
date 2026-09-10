import pytest

from iris.config import CustomCommand
from iris.nlu.intents import IntentParser, parse_yes_no


@pytest.fixture(scope="module")
def parser() -> IntentParser:
    return IntentParser([CustomCommand("dev", ["lance mon workspace de dev"], "true")])


CASES = [
    ("Ouvre le terminal", "open_app", {"app": "terminal"}),
    ("lance mon navigateur", "open_app", {"app": "navigateur"}),
    ("lance-moi un terminal", "open_app", {"app": "terminal"}),
    ("ouvre l'application spotify", "open_app", {"app": "spotify"}),
    ("open firefox", "open_app", {"app": "firefox"}),
    ("Peux-tu ouvrir Firefox s'il te plaît ?", "open_app", {"app": "firefox"}),
    ("ferme firefox", "close_app", {"app": "firefox"}),
    ("close the browser", "close_app", {"app": "browser"}),
    ("ferme tout", "close_all", {}),
    ("close all windows", "close_all", {}),
    ("ferme cette fenêtre", "window_close", {}),
    ("ferme la fenêtre active", "window_close", {}),
    ("plein écran", "window_fullscreen", {}),
    ("envoie cette fenêtre sur le workspace 4", "window_move_workspace", {"n": 4}),
    ("va sur le workspace 3", "workspace_switch", {"n": 3}),
    ("workspace 2", "workspace_switch", {"n": 2}),
    ("go to workspace 5", "workspace_switch", {"n": 5}),
    ("bureau trois", "workspace_switch", {"n": 3}),
    ("workspace suivant", "workspace_next", {}),
    ("previous workspace", "workspace_prev", {}),
    ("monte le son", "volume_up", {}),
    ("turn up the volume", "volume_up", {}),
    ("baisse le volume de 20", "volume_down", {"n": 20}),
    ("mets le volume à 50 %", "volume_set", {"n": 50}),
    ("volume 30", "volume_set", {"n": 30}),
    ("set volume to 75", "volume_set", {"n": 75}),
    ("volume à cinquante pour cent", "volume_set", {"n": 50}),
    ("coupe le son", "volume_mute", {}),
    ("éteins le son", "volume_mute", {}),
    ("remets le son", "volume_unmute", {}),
    ("unmute", "volume_unmute", {}),
    ("monte la luminosité", "brightness_up", {}),
    ("luminosité à 40", "brightness_set", {"n": 40}),
    ("baisse la luminosité de 15", "brightness_down", {"n": 15}),
    ("musique suivante", "media_next", {}),
    ("next", "media_next", {}),
    ("pause", "media_play_pause", {}),
    ("mets la musique", "media_play_pause", {}),
    ("piste précédente", "media_prev", {}),
    ("change de thème", "theme_next", {}),
    ("mets le thème tokyo night", "theme_set", {"name": "tokyo night"}),
    ("mode nuit", "night_light", {}),
    ("prends une capture d'écran", "screenshot", {}),
    ("verrouille l'écran", "lock_screen", {}),
    ("lock the screen", "lock_screen", {}),
    ("mets en veille", "suspend", {}),
    ("mets le pc en veille", "suspend", {}),
    ("put the computer to sleep", "suspend", {}),
    ("éteins l'ordinateur", "shutdown", {}),
    ("shut down the computer", "shutdown", {}),
    ("redémarre le pc", "reboot", {}),
    ("quelle heure est-il ?", "time", {}),
    ("dis-moi l'heure", "time", {}),
    ("what time is it", "time", {}),
    ("quel jour sommes-nous", "date", {}),
    ("dis bonjour à tout le monde", "say", {"text": "bonjour a tout le monde"}),
    (
        "cherche des recettes de crêpes sur internet",
        "web_search",
        {"query": "des recettes de crepes"},
    ),
    ("search for cats", "web_search", {"query": "cats"}),
    ("ouvre github.com", "open_url", {"url": "github.com"}),
    ("ouvre github point com", "open_url", {"url": "github.com"}),
    ("ouvre le site lemonde.fr", "open_url", {"url": "lemonde.fr"}),
    ("bonjour", "greet", {}),
    ("merci", "thanks", {}),
    ("qu'est-ce que tu sais faire", "help", {}),
    ("qui es-tu", "who_are_you", {}),
    ("stop", "stop", {}),
    ("mets-toi en pause pendant 10 minutes", "pause_listening", {"minutes": 10}),
    ("reprends l'écoute", "resume_listening", {}),
    ("demande à Claude d'écrire un haiku", "ask_agent", {"prompt": "d'ecrire un haiku"}),
    ("lance mon workspace de dev", "custom", {"command": "dev"}),
    ("lance mon workspace de dev stp", "custom", {"command": "dev"}),
]


@pytest.mark.parametrize(("text", "name", "slots"), CASES, ids=[c[0] for c in CASES])
def test_parse(parser: IntentParser, text: str, name: str, slots: dict) -> None:
    intent = parser.parse(text)
    assert intent is not None, f"non reconnu : {text}"
    assert intent.name == name
    for key, value in slots.items():
        assert intent.slots.get(key) == value


def test_unknown_returns_none(parser: IntentParser) -> None:
    assert parser.parse("blabla incompréhensible xyz") is None
    assert parser.parse("") is None


def test_confirmation_flags(parser: IntentParser) -> None:
    assert parser.parse("ferme tout").requires_confirmation
    assert parser.parse("éteins l'ordinateur").requires_confirmation
    assert not parser.parse("monte le son").requires_confirmation


def test_custom_command_confirm_flag() -> None:
    p = IntentParser([CustomCommand("danger", ["nettoie le disque"], "true", confirm=True)])
    intent = p.parse("nettoie le disque")
    assert intent is not None and intent.name == "custom" and intent.requires_confirmation
    assert intent.command is not None and intent.command.name == "danger"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("oui", True),
        ("Oui, vas-y", True),
        ("yes please", True),
        ("ok", True),
        ("d'accord", True),
        ("non", False),
        ("annule", False),
        ("surtout pas", False),
        ("non merci", False),
        ("cancel", False),
        ("peut-être", None),
        ("", None),
    ],
)
def test_parse_yes_no(text: str, expected) -> None:
    assert parse_yes_no(text) is expected
