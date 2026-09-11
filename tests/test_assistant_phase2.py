import pytest

from iris.core.assistant import Assistant, State
from iris.core.router import Router
from iris.core.status import StatusWriter
from iris.llm.brain import Decision
from iris.nlu.intents import IntentParser
from iris.tts.console import ConsoleTTS
from iris.wakeword import TranscriptWake


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class FakeBrain:
    def __init__(self) -> None:
        self.decision = Decision("none")
        self.asked: list[str] = []

    def decide(self, text: str, language: str = "fr") -> Decision:
        self.asked.append(text)
        return self.decision

    def converse(self, text: str, language: str = "fr") -> str:
        return "Réponse."


class LangTTS(ConsoleTTS):
    def __init__(self) -> None:
        super().__init__()
        self.langs: list[str] = []

    def speak(self, text: str, language: str | None = None) -> bool:
        self.langs.append(language or "")
        return super().speak(text)


@pytest.fixture
def world(cfg, phrases, journal, fake_system, tmp_path):
    fake_system.available |= {"hyprctl", "wpctl", "wtype"}
    cfg.llm.enabled = True
    clock = FakeClock()
    tts = LangTTS()
    brain = FakeBrain()
    status = StatusWriter(tmp_path / "state.json")
    router = Router(cfg, phrases, journal, brain=brain)
    assistant = Assistant(
        cfg,
        IntentParser(cfg.commands),
        router,
        phrases,
        tts,
        wake=TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold),
        journal=journal,
        clock=clock,
        brain=brain,
        status=status,
    )
    return assistant, tts, clock, fake_system, brain, status


def test_dictation_mode(world):
    a, tts, _, fake, _, _ = world
    a.on_utterance("Iris, mode dictée")
    assert a.state == State.DICTATING and tts.spoken[-1].startswith("Mode dictée")
    a.on_utterance("Bonjour à tous, voici le compte rendu.")
    assert ["wtype", "--", "Bonjour à tous, voici le compte rendu."] in fake.calls
    assert len(tts.spoken) == 1  # silencieuse pendant la dictée
    a.on_utterance("Iris, fin de dictée")
    assert a.state == State.IDLE and tts.spoken[-1] == "Fin de dictée."


def test_multi_command(world):
    a, tts, _, fake, _, _ = world
    a.on_utterance("Iris, monte le son et va sur le workspace 2")
    calls = fake.joined_calls()
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+" in calls
    assert "hyprctl dispatch workspace 2" in calls
    assert tts.spoken[-1] == "Workspace 2."


def test_multi_command_stops_at_confirmation(world):
    a, tts, _, fake, _, _ = world
    fake.outputs["hyprctl -j clients"] = "[]"
    a.on_utterance("Iris, ferme tout et monte le son")
    assert a.state == State.CONFIRMING
    assert not any("set-volume" in c for c in fake.joined_calls())


def test_llm_fallback_action(world):
    a, tts, _, fake, brain, _ = world
    brain.decision = Decision("action", "volume_set", {"n": 35}, "Ok.")
    a.on_utterance("Iris, c'est beaucoup trop silencieux ici")
    assert brain.asked
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 35%" in fake.joined_calls()
    assert tts.spoken[-1] == "Volume à 35 pour cent."


def test_llm_fallback_reply_and_none(world):
    a, tts, _, fake, brain, _ = world
    brain.decision = Decision(
        "reply", reply="Le ciel est bleu à cause de la diffusion de Rayleigh."
    )
    a.on_utterance("Iris, bidule machin pourquoi bleu ciel")
    assert tts.spoken[-1].startswith("Le ciel est bleu")
    # Le modèle préfère se taire, mais on l'a appelée par son nom : elle accuse réception
    # et garde la fenêtre ouverte, là où le silence total laissait croire à un micro mort.
    brain.decision = Decision("none")
    n = len(tts.spoken)
    a.on_utterance("Iris, gnagnagna")
    assert len(tts.spoken) == n + 1 and a.state == State.ACTIVE


def test_llm_silencieux_sans_notre_nom_reste_silencieux(world):
    """Du bruit pendant la fenêtre d'écoute : on se taît, sans bip parasite."""
    a, tts, _, _, brain, _ = world
    a.on_utterance("Hey Iris")
    brain.decision = Decision("none")
    n = len(tts.spoken)
    a.on_utterance("gnagnagna")
    assert len(tts.spoken) == n and a.state == State.IDLE


def test_llm_fallback_action_requires_confirmation(world):
    a, tts, _, fake, brain, _ = world
    brain.decision = Decision("action", "shutdown", {}, "")
    a.on_utterance("Iris, on coupe la machine")
    assert (
        a.state == State.CONFIRMING and tts.spoken[-1] == "Veux-tu vraiment éteindre l'ordinateur ?"
    )
    a.on_utterance("non")
    assert not any("poweroff" in c for c in fake.joined_calls())


def test_llm_fallback_unknown_action(world):
    a, tts, _, _, brain, _ = world
    brain.decision = Decision("action", "format_disk", {})
    a.on_utterance("Iris, formate tout")
    assert "ne connais pas" in tts.spoken[-1]


def test_llm_unavailable_le_dit(world):
    """Modèle injoignable : le dire, et non laisser croire qu'on n'a pas compris la phrase."""
    a, tts, _, _, brain, _ = world

    def boom(text, language="fr"):
        raise RuntimeError("réseau")

    brain.decide = boom
    a.on_utterance("Iris, gnagnagna")
    assert tts.spoken[-1] == "Je n'arrive pas à joindre le modèle."


def test_language_auto_switches_replies(world):
    a, tts, _, _, _, _ = world
    a.cfg.assistant.language = "auto"
    a.on_utterance("Iris, what time is it", language="en")
    assert a.p.lang == "en" and tts.spoken[-1].startswith("It is") and tts.langs[-1] == "en"
    a.on_utterance("Iris, quelle heure est-il", language="fr")
    assert a.p.lang == "fr" and tts.spoken[-1].startswith("Il est")


def test_language_fixed_ignores_detection(world):
    a, tts, _, _, _, _ = world
    a.on_utterance("Iris, what time is it", language="en")
    assert a.p.lang == "fr" and tts.spoken[-1].startswith("Il est")


def test_status_file_follows_state(world):
    a, _, _, _, _, status = world
    a.on_utterance("Hey Iris")
    assert StatusWriter.read(status.path)["state"] == "active"
    a.on_utterance("mets-toi en pause")
    assert StatusWriter.read(status.path)["state"] == "paused"


def test_push_to_talk_and_pause_signals(world):
    a, tts, _, _, _, _ = world
    a.request_wake()
    a.tick()
    assert a.state == State.ACTIVE
    a.request_toggle_pause()
    a.tick()
    assert a.state == State.PAUSED
    a.request_toggle_pause()
    a.tick()
    assert a.state == State.IDLE and tts.spoken[-1] == "Je t'écoute à nouveau."
