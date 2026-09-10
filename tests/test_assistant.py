import pytest

from iris.core.assistant import Assistant, State
from iris.core.router import Router
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


@pytest.fixture
def world(cfg, phrases, journal, fake_system):
    fake_system.available |= {"hyprctl", "wpctl"}
    fake_system.outputs["hyprctl -j clients"] = '[{"address": "0x1", "class": "x"}]'
    clock = FakeClock()
    tts = ConsoleTTS()
    assistant = Assistant(
        cfg,
        IntentParser(cfg.commands),
        Router(cfg, phrases, journal),
        phrases,
        tts,
        wake=TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold),
        journal=journal,
        clock=clock,
    )
    return assistant, tts, clock, fake_system, journal


def test_wake_word_alone_enters_active_then_command(world):
    a, tts, clock, fake, _ = world
    a.on_utterance("Hey Iris")
    assert a.state == State.ACTIVE
    assert tts.spoken[-1] == "Oui ?" or tts.spoken[-1] in {"Je t'écoute.", "Oui, dis-moi."}
    a.on_utterance("va sur le workspace 2")
    assert "hyprctl dispatch workspace 2" in fake.joined_calls()
    assert tts.spoken[-1] == "Workspace 2."
    assert a.state == State.ACTIVE  # fenêtre d'enchaînement


def test_wake_word_with_command_in_one_utterance(world):
    a, tts, _, fake, _ = world
    a.on_utterance("Iris, mets le volume à 30")
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 30%" in fake.joined_calls()
    assert tts.spoken[-1] == "Volume à 30 pour cent."


def test_utterance_without_wake_word_is_ignored_when_idle(world):
    a, tts, _, fake, journal = world
    a.on_utterance("mets le volume à 30")
    assert tts.spoken == [] and fake.calls == []
    assert a.state == State.IDLE


def test_active_window_expires(world):
    a, tts, clock, _, _ = world
    a.on_utterance("Hey Iris")
    clock.advance(a.cfg.assistant.active_window_s + 1)
    a.on_utterance("mets le volume à 30")  # trop tard : ignoré
    assert a.state == State.IDLE
    assert len(tts.spoken) == 1


def test_follow_up_window_allows_chaining_then_expires(world):
    a, tts, clock, fake, _ = world
    a.on_utterance("Iris, volume 10")
    clock.advance(2)
    a.on_utterance("volume 20")
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 20%" in fake.joined_calls()
    clock.advance(a.cfg.assistant.follow_up_window_s + 1)
    a.on_utterance("volume 30")
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 30%" not in fake.joined_calls()


def test_confirmation_yes(world):
    a, tts, _, fake, _ = world
    a.on_utterance("Iris, ferme tout")
    assert a.state == State.CONFIRMING
    assert tts.spoken[-1] == "Veux-tu vraiment fermer toutes les applications ?"
    a.on_utterance("oui")
    assert "hyprctl dispatch closewindow address:0x1" in fake.joined_calls()
    assert tts.spoken[-1] == "1 fenêtres fermées."


def test_confirmation_no(world):
    a, tts, _, fake, _ = world
    a.on_utterance("Iris, éteins l'ordinateur")
    a.on_utterance("non")
    assert a.state == State.IDLE
    assert tts.spoken[-1] in {"Annulé.", "D'accord, j'annule."}
    assert not any("poweroff" in c for c in fake.joined_calls())


def test_confirmation_unclear_then_timeout(world):
    a, tts, clock, fake, _ = world
    a.on_utterance("Iris, redémarre le pc")
    a.on_utterance("peut-être")
    assert a.state == State.CONFIRMING
    assert tts.spoken[-1] == "Veux-tu vraiment redémarrer l'ordinateur ?"
    clock.advance(a.cfg.assistant.confirm_timeout_s + 1)
    a.tick()
    assert a.state == State.IDLE
    assert tts.spoken[-1] == "Pas de réponse, je laisse tomber."
    assert not any("reboot" in c for c in fake.joined_calls())


def test_pause_and_resume(world):
    a, tts, clock, fake, _ = world
    a.on_utterance("Iris, mets-toi en pause pendant 1 minutes")
    assert a.state == State.PAUSED
    a.on_utterance("Iris, volume 50")
    assert not any("50%" in c for c in fake.joined_calls())
    a.on_utterance("Hey Iris, reprends l'écoute")
    assert a.state == State.IDLE
    assert tts.spoken[-1] == "Je t'écoute à nouveau."
    a.on_utterance("Iris, mets-toi en pause")
    clock.advance(11 * 60)
    a.tick()
    assert a.state == State.IDLE


def test_follow_up_ignores_unknown_noise_silently(world):
    a, tts, _, _, _ = world
    a.on_utterance("Iris, volume 10")
    spoken = len(tts.spoken)
    a.on_utterance("et alors il m'a dit que non")  # conversation ambiante
    assert len(tts.spoken) == spoken and a.state == State.IDLE
    a.on_utterance("Hey Iris")
    a.on_utterance("et alors il m'a dit que non")  # après « Hey Iris » explicite : on répond
    assert len(tts.spoken) == spoken + 2


def test_stop_returns_to_idle(world):
    a, tts, _, _, _ = world
    a.on_utterance("Hey Iris")
    a.on_utterance("stop")
    assert a.state == State.IDLE


def test_not_understood(world):
    a, tts, _, _, _ = world
    a.on_utterance("Iris, blorp zlurg")
    assert tts.spoken[-1] in {"Je n'ai pas compris.", "Désolée, je n'ai pas saisi."}


def test_handle_text_mode(world):
    a, tts, _, fake, _ = world
    reply = a.handle_text("volume 45")  # sans mot d'activation en mode texte
    assert reply is not None and reply.ok
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 45%" in fake.joined_calls()
    reply = a.handle_text("Hey Iris")
    assert a.state == State.ACTIVE and reply is not None


def test_transcripts_journaled_when_enabled(world):
    a, _, _, _, journal = world
    a.on_utterance("Iris, quelle heure est-il")
    a.on_utterance("bruit sans activation")
    rows = journal._db.execute("SELECT text, wake, handled FROM utterances ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [
        ("Iris, quelle heure est-il", 1, 1),
        ("bruit sans activation", 0, 0),
    ]


def test_audio_wake_detection_enters_active(world):
    a, tts, _, _, _ = world
    a.on_wake_detected()
    assert a.state == State.ACTIVE
