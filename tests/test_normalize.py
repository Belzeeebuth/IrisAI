import pytest

from iris.nlu.normalize import canonical, normalize, strip_politeness
from iris.nlu.numbers import words_to_digits


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mets le volume à cinquante pour cent", "mets le volume a 50%"),
        ("Ouvre un terminal", "ouvre un terminal"),
        ("Va sur le workspace vingt-cinq", "va sur le workspace 25"),
        ("volume à quatre-vingt-dix", "volume a 90"),
        ("soixante et onze", "71"),
        ("quatre-vingts", "80"),
        ("set volume to seventy five percent", "set volume to 75%"),
        ("ouvre github point com", "ouvre github.com"),
        ("Hé Iris, dis-moi l’heure !", "he iris dis moi l'heure"),
        ("ouvre github.com.", "ouvre github.com"),
        ("Cent", "100"),
        ("one hundred and five", "105"),
        ("il y a une pomme", "il y a une pomme"),
    ],
)
def test_canonical(text: str, expected: str) -> None:
    assert canonical(text) == expected


def test_normalize_keeps_apostrophes_and_strips_accents() -> None:
    assert normalize("L’écran s'éteint, non ?") == "l'ecran s'eteint non"


def test_words_to_digits_ignores_lone_articles() -> None:
    assert words_to_digits("ouvre un fichier et une image") == "ouvre un fichier et une image"
    assert words_to_digits("vingt et un") == "21"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("peux tu ouvrir firefox s'il te plait", "ouvrir firefox"),
        ("est ce que tu peux monter le son stp", "monter le son"),
        ("can you lock the screen please", "lock the screen"),
        ("monte le son", "monte le son"),
    ],
)
def test_strip_politeness(text: str, expected: str) -> None:
    assert strip_politeness(text) == expected
