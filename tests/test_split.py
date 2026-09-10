import pytest

from iris.nlu.intents import IntentParser
from iris.nlu.split import split_commands

parser = IntentParser()


def intent_of(text: str):
    intent = parser.parse(text)
    return intent.name if intent else None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "ouvre le terminal et va sur le workspace 2",
            ["ouvre le terminal", "va sur le workspace 2"],
        ),
        ("monte le son puis ferme firefox", ["monte le son", "ferme firefox"]),
        ("ouvre firefox et spotify", ["ouvre firefox", "ouvre spotify"]),
        ("ouvre le terminal et le navigateur", ["ouvre le terminal", "ouvre le navigateur"]),
        ("cherche riz et poulet sur internet", ["cherche riz et poulet sur internet"]),
        ("dis bonjour et bonne nuit", ["dis bonjour et bonne nuit"]),
        ("monte le son", ["monte le son"]),
        ("open the terminal and then lock the screen", ["open the terminal", "lock the screen"]),
        ("blabla et truc", ["blabla et truc"]),
    ],
)
def test_split(text, expected):
    assert split_commands(text, intent_of) == expected
