import pytest

from iris.wakeword import TranscriptWake

PHRASES = ["hey iris", "iris", "ok iris", "salut iris", "hé iris"]


@pytest.fixture(scope="module")
def wake() -> TranscriptWake:
    return TranscriptWake(PHRASES, threshold=0.76)


@pytest.mark.parametrize(
    ("text", "remainder"),
    [
        ("Hé Iris, ouvre le terminal.", "ouvre le terminal"),
        ("Hey Iris ouvre le terminal", "ouvre le terminal"),
        ("Iris", ""),
        ("Irisse monte le son", "monte le son"),
        ("Hey Irish, quelle heure est-il ?", "quelle heure est-il"),
        ("ouvre le terminal, Iris", "ouvre le terminal"),
        ("Euh, Iris, dis bonjour", "dis bonjour"),
        ("OK Iris, verrouille l'écran", "verrouille l'écran"),
    ],
)
def test_matches(wake: TranscriptWake, text: str, remainder: str) -> None:
    match = wake.match(text)
    assert match is not None, text
    assert match.remainder == remainder


@pytest.mark.parametrize("text", ["ouvre le terminal", "Il a pris le train", "gris", "", "   "])
def test_no_match(wake: TranscriptWake, text: str) -> None:
    assert wake.match(text) is None


def test_remainder_keeps_original_case_and_accents(wake: TranscriptWake) -> None:
    assert wake.match("Iris, dis Bonjour à Élise").remainder == "dis Bonjour à Élise"


def test_requires_phrases() -> None:
    with pytest.raises(ValueError):
        TranscriptWake([])
