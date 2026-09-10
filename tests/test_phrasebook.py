from iris.core.phrasebook import PHRASES, Phrasebook


def test_tone_and_verbosity_resolution() -> None:
    warm = Phrasebook("fr", "normal", "warm", seed=0)
    direct = Phrasebook("fr", "concise", "direct", seed=0)
    assert warm.get("ack") in {"Oui ?", "Je t'écoute.", "Oui, dis-moi."}
    assert direct.get("ack") in {"Oui.", "J'écoute."}
    assert direct.get("not_understood") == "Pas compris."
    assert warm.get("workspace_switched", n=3) == "Workspace 3."


def test_english_and_fallback() -> None:
    en = Phrasebook("en", "chatty", "coach", seed=0)
    assert en.get("workspace_switched", n=2) == "You're on workspace 2."
    assert en.get("follow_up") == " Anything else?"
    assert Phrasebook("xx").lang == "fr"
    assert Phrasebook("fr").get("clé inexistante") == "clé inexistante"


def test_every_french_key_exists_in_english() -> None:
    missing = set(PHRASES["fr"]) - set(PHRASES["en"])
    assert not missing, missing


def test_missing_format_key_does_not_crash() -> None:
    assert Phrasebook("fr").get("volume_set") == "Volume à {n} pour cent."
