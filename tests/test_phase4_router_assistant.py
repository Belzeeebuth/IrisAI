import pytest

from iris.config import CustomCommand
from iris.core.assistant import Assistant, State
from iris.core.habits import FollowUp, Routine
from iris.core.prefs import Prefs
from iris.core.router import Router
from iris.core.scheduler import Scheduler
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


class FakeHabits:
    def __init__(self) -> None:
        self.follow = None
        self.routine = None

    def follow_up_for(self, intent, slots):
        return self.follow

    def routine_due(self, now=None):
        return self.routine

    def routines(self):
        return [self.routine] if self.routine else []

    def follow_ups(self):
        return {self.follow.after: self.follow} if self.follow else {}


class FakeVoice:
    def __init__(self, voice_id: str, name: str) -> None:
        self.voice_id = voice_id
        self.name = name


class FakeElevenTTS(ConsoleTTS):
    name = "elevenlabs"

    def __init__(self) -> None:
        super().__init__()
        self._voice_id = "x"

    def voices(self):
        return [FakeVoice("1", "Sarah"), FakeVoice("2", "Léa")]

    def resolve_voice(self, wanted):
        for v in self.voices():
            if v.name.lower() == wanted.lower():
                return v.voice_id
        raise RuntimeError("introuvable")


@pytest.fixture
def world(cfg, phrases, journal, fake_system):
    fake_system.available |= {"hyprctl", "wpctl", "notify-send", "spotify"}
    cfg.commands = [CustomCommand("dev", ["lance mon workspace de dev"], "true")]
    cfg.tts.elevenlabs_voice = "Sarah"
    parser = IntentParser(cfg.commands)
    clock = FakeClock()
    tts = FakeElevenTTS()
    habits = FakeHabits()
    prefs = Prefs(journal)
    scheduler = Scheduler(journal)
    router = Router(
        cfg,
        phrases,
        journal,
        prefs=prefs,
        habits=habits,
        scheduler=scheduler,
        parser=parser,
        tts=tts,
    )
    assistant = Assistant(
        cfg,
        parser,
        router,
        phrases,
        tts,
        wake=TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold),
        journal=journal,
        clock=clock,
    )
    return assistant, tts, clock, fake_system, habits, prefs, scheduler, router


# ---------------------------------------------------------------- automatisations par la voix
def test_automation_create_list_delete(world):
    a, tts, _, _, _, _, scheduler, _ = world
    a.on_utterance("Iris, chaque matin à 9 h, lance spotify")
    assert tts.spoken[-1] == "Programmé : chaque jour à 9 h : ouvrir spotify."
    assert scheduler.exists("open_app", {"app": "spotify"})
    a.on_utterance("Iris, en semaine à 8 h 30 lance mon workspace de dev")
    assert tts.spoken[-1] == "Programmé : en semaine à 8 h 30 : lancer dev."
    a.on_utterance("Iris, quelles sont mes automatisations")
    assert tts.spoken[-1].startswith(
        "Tes automatisations : en semaine à 8 h 30 : lancer dev; chaque jour à 9 h : ouvrir spotify"
    )
    a.on_utterance("Iris, supprime l'automatisation de 9 h")
    assert tts.spoken[-1] == "Supprimé : chaque jour à 9 h : ouvrir spotify."
    assert not scheduler.exists("open_app", {"app": "spotify"})


def test_automation_refuses_confirmation_and_unknown(world):
    a, tts, _, _, _, _, scheduler, _ = world
    a.on_utterance("Iris, chaque soir à 23 h éteins l'ordinateur")
    assert tts.spoken[-1] == "Je ne programme pas une action qui demande une confirmation."
    a.on_utterance("Iris, chaque matin à 9 h blorp zlurg")
    assert "pas compris quoi faire" in tts.spoken[-1]
    assert scheduler.list() == []


def test_reminder_create_and_fire(world, monkeypatch):
    a, tts, clock, fake, _, _, scheduler, router = world
    a.on_utterance("Iris, rappelle-moi de sortir les poubelles dans 1 minutes")
    assert tts.spoken[-1].startswith("Je te le rappellerai aujourd'hui à") and tts.spoken[
        -1
    ].endswith(": sortir les poubelles.")
    auto = scheduler.list()[0]
    assert auto.intent == "reminder_fire" and auto.slots == {"what": "sortir les poubelles"}
    a.on_utterance("Iris, rappelle-moi de boire")
    assert tts.spoken[-1].startswith("Quand veux-tu")
    # le rappel devient dû : on avance la date réelle via monkeypatch de due()
    monkeypatch.setattr(scheduler, "due", lambda now=None: [auto])
    clock.advance(60)
    a.tick()
    assert tts.spoken[-1] == "Rappel : sortir les poubelles."
    assert any(c[0] == "notify-send" for c in fake.calls)
    assert all(x.id != auto.id for x in scheduler.list())


def test_due_automation_runs_with_prefix(world, monkeypatch):
    a, tts, clock, fake, _, _, scheduler, router = world
    a.on_utterance("Iris, chaque matin à 9 h, lance spotify")
    auto = scheduler.list()[0]
    monkeypatch.setattr(scheduler, "due", lambda now=None: [auto])
    clock.advance(60)
    a.tick()
    assert tts.spoken[-1] == "Comme prévu : spotify est lancé."
    assert ["spotify"] in fake.launched
    assert scheduler.list()[0].last_run is not None


def test_custom_automation_runs_by_name(world, monkeypatch):
    a, tts, clock, fake, _, _, scheduler, router = world
    a.on_utterance("Iris, chaque matin à 9 h lance mon workspace de dev")
    auto = scheduler.list()[0]
    assert auto.intent == "custom" and auto.slots == {"command": "dev"}
    reply = router.run_automation(auto)
    assert reply.ok and reply.text == "dev : c'est fait."


# ---------------------------------------------------------------- suggestions
def test_follow_up_suggestion_accepted(world):
    a, tts, _, fake, habits, prefs, _, _ = world
    habits.follow = FollowUp(
        "open_app|app=spotify", "workspace_switch|n=2", "workspace_switch", {"n": 2}, 4, 1.0
    )
    a.on_utterance("Iris, ouvre spotify")
    assert (
        a.state == State.CONFIRMING and tts.spoken[-1] == "Veux-tu aussi aller sur le workspace 2 ?"
    )
    a.on_utterance("oui")
    assert (
        "hyprctl dispatch workspace 2" in fake.joined_calls() and tts.spoken[-1] == "Workspace 2."
    )


def test_follow_up_suggestion_declined_is_dismissed(world):
    a, tts, _, fake, habits, prefs, _, _ = world
    habits.follow = FollowUp(
        "open_app|app=spotify", "workspace_switch|n=2", "workspace_switch", {"n": 2}, 4, 1.0
    )
    a.on_utterance("Iris, ouvre spotify")
    a.on_utterance("non")
    assert tts.spoken[-1].startswith("D'accord, je ne te le proposerai plus")
    assert prefs.is_dismissed("follow:open_app|app=spotify>workspace_switch|n=2")
    n = len(tts.spoken)
    a.on_utterance("Iris, ouvre spotify")
    assert a.state != State.CONFIRMING and len(tts.spoken) == n + 1  # plus de proposition


def test_follow_up_respects_cooldown_and_quiet_hours(world):
    a, tts, _, _, habits, prefs, _, _ = world
    habits.follow = FollowUp(
        "open_app|app=spotify", "workspace_switch|n=2", "workspace_switch", {"n": 2}, 4, 1.0
    )
    a.cfg.assistant.quiet_hours = "00:00-23:59"
    a.on_utterance("Iris, ouvre spotify")
    assert a.state != State.CONFIRMING
    a.cfg.assistant.quiet_hours = ""
    a.on_utterance("Iris, ouvre spotify")
    assert a.state == State.CONFIRMING
    a.on_utterance("oui")
    a.on_utterance("Iris, ouvre spotify")
    assert a.state != State.CONFIRMING  # même proposition : délai de 24 h


def test_routine_suggestion_creates_automation(world):
    a, tts, clock, _, habits, prefs, scheduler, _ = world
    habits.routine = Routine(
        "open_app|app=spotify", "open_app", {"app": "spotify"}, 9, 0, 4, [0, 1, 2, 3]
    )
    clock.advance(700)
    a.tick()
    assert a.state == State.CONFIRMING
    assert (
        tts.spoken[-1]
        == "Tu fais souvent ouvrir spotify vers 9 h. Veux-tu que je m'en occupe en semaine à 9 h ?"
    )
    a.on_utterance("oui")
    assert (
        scheduler.exists("open_app", {"app": "spotify"})
        and tts.spoken[-1] == "Programmé : en semaine à 9 h : ouvrir spotify."
    )
    clock.advance(700)
    a.tick()
    assert a.state == State.IDLE  # déjà automatisé, plus de proposition


def test_routine_suggestion_declined_and_disabled(world):
    a, tts, clock, _, habits, prefs, scheduler, _ = world
    habits.routine = Routine(
        "open_app|app=spotify", "open_app", {"app": "spotify"}, 9, 0, 4, [5, 6]
    )
    clock.advance(700)
    a.tick()
    a.on_utterance("non")
    assert prefs.is_dismissed("routine:open_app|app=spotify@9:00") and scheduler.list() == []
    a.on_utterance("Iris, arrête de me proposer des trucs")
    assert (
        tts.spoken[-1] == "Je ne ferai plus de suggestions."
        and prefs.get("habits.suggestions") is False
    )
    assert not a._suggestions_allowed()
    a.on_utterance("Iris, quelles sont mes habitudes")
    assert tts.spoken[-1].startswith("Ce que j'ai remarqué : ouvrir spotify vers 9 h (4 fois)")


# ---------------------------------------------------------------- style, voix, langue, activation, alias
def test_style_and_voice_controls_persist(world):
    a, tts, _, _, _, prefs, _, router = world
    a.on_utterance("Iris, sois plus directe")
    assert (
        tts.spoken[-1] == "D'accord, je serai plus directe."
        and a.p.tone == "direct"
        and prefs.get("style.tone") == "direct"
    )
    a.on_utterance("Iris, sois plus concise")
    assert a.p.verbosity == "concise" and prefs.get("style.verbosity") == "concise"
    a.on_utterance("Iris, parle plus vite")
    assert prefs.get("voice.speed") == 1.12 and a.cfg.tts.elevenlabs_speed == 1.12
    a.on_utterance("Iris, vitesse normale")
    assert prefs.get("voice.speed") == 1.0
    a.on_utterance("Iris, utilise la voix Léa")
    assert (
        tts.spoken[-1] == "Nouvelle voix : Léa."
        and a.cfg.tts.elevenlabs_voice == "Léa"
        and prefs.get("voice.name") == {"elevenlabs": "Léa"}
    )
    a.on_utterance("Iris, change de voix")
    assert a.cfg.tts.elevenlabs_voice == "Sarah"
    a.on_utterance("Iris, utilise la voix Zorglub")
    assert tts.spoken[-1].startswith("Je ne trouve pas cette voix")


def test_language_switch_and_wake_add(world):
    a, tts, _, _, _, prefs, _, _ = world
    a.on_utterance("Iris, parle en anglais")
    assert (
        tts.spoken[-1] == "Okay, I'll answer in English."
        and a.p.lang == "en"
        and a.cfg.stt.language == "en"
    )
    a.on_utterance("Iris, what time is it")
    assert tts.spoken[-1].startswith("It is")
    a.on_utterance("Iris, speak french")
    assert a.p.lang == "fr"
    a.on_utterance("Iris, appelle-toi Nova")
    assert tts.spoken[-1] == "Tu peux aussi m'appeler Nova." and "nova" in a.cfg.wake.phrases
    assert prefs.get("wake.extra_phrases") == ["hey nova", "nova"]
    a.on_utterance("Hey Nova, quelle heure est-il")
    assert tts.spoken[-1].startswith("Il est")


def test_alias_learn_applies_immediately(world, fake_system):
    a, tts, _, fake, _, prefs, _, router = world
    fake.available.add("thunderbird")
    a.on_utterance("Iris, quand je dis mes mails, ouvre thunderbird")
    assert tts.spoken[-1] == "D'accord : quand tu dis « mes mails », j'ouvre thunderbird."
    a.on_utterance("Iris, ouvre mes mails")
    assert ["thunderbird"] in fake.launched
    a.on_utterance("Iris, mes alias")
    assert tts.spoken[-1] == "Tes alias : mes mails → thunderbird."


def test_alias_learn_resolves_builtin_alias_target(world, fake_system):
    a, tts, _, fake, _, prefs, _, router = world
    fake.available.add("chromium")
    a.on_utterance("Iris, quand je dis mon site, ouvre le navigateur")
    assert tts.spoken[-1] == "D'accord : quand tu dis « mon site », j'ouvre le navigateur."
    browser = router.apps.resolve("le navigateur")
    assert browser is not None and browser.argv
    assert prefs.aliases()["mon site"] == " ".join(browser.argv)
    a.on_utterance("Iris, ouvre mon site")
    assert fake.launched[-1] == browser.argv
    a.on_utterance("Iris, quand je dis mes vidéos, ouvre youtube")
    assert prefs.aliases()["mes vidéos"].startswith("webapp:")


def test_quiet_hours_make_replies_concise(world):
    a, tts, _, _, _, _, _, _ = world
    a.cfg.assistant.quiet_hours = "00:00-23:59"
    a.tick()
    assert a.p.verbosity == "concise" and a._quiet_active
    a.cfg.assistant.quiet_hours = ""
    a.tick()
    assert a.p.verbosity == "normal" and not a._quiet_active
    a.cfg.assistant.quiet_hours = "n'importe quoi"
    assert a.quiet_now() is False


def test_phrase_overrides_from_config(world):
    a, tts, _, _, _, _, _, _ = world
    a.p.overrides = {"ack": ["Oui chef ?"]}
    a.cfg.assistant.ack_sound = False  # sinon un bip remplace la phrase
    a.on_utterance("Hey Iris")
    assert tts.spoken[-1] == "Oui chef ?"


def test_suggestion_timeout_does_not_leak_into_next_confirmation(world):
    a, tts, clock, fake, habits, prefs, _, _ = world
    habits.follow = FollowUp("open_app|app=spotify", "dnd_on", "dnd_on", {}, 4, 0.8)
    a.on_utterance("Iris, ouvre spotify")
    assert a.state == State.CONFIRMING and tts.spoken[-1].startswith("Veux-tu aussi")
    clock.advance(a.cfg.assistant.confirm_timeout_s + 1)
    a.tick()
    assert a.state == State.IDLE
    # une vraie confirmation, refusée : c'est « Annulé », pas « je ne te le proposerai plus »
    a.on_utterance("Iris, éteins l'ordinateur")
    assert a.state == State.CONFIRMING
    a.on_utterance("non")
    assert tts.spoken[-1] in ("Annulé.", "D'accord, j'annule.")
    assert not prefs.is_dismissed("follow:open_app|app=spotify>dnd_on")
