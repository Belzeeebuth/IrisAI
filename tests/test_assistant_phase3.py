import time

import pytest

from iris.agents.runner import AgentRunner
from iris.config import AgentsConfig, BackgroundTask
from iris.core.assistant import Assistant, State
from iris.core.memory import Memory
from iris.core.router import Router
from iris.core.tasks import TaskManager
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


class StreamBrain:
    def __init__(self) -> None:
        self.fail = False

    def converse_stream(self, text, language="fr"):
        if self.fail:
            raise RuntimeError("réseau")
        yield "Première phrase."
        yield "Seconde phrase."

    def decide(self, text, language="fr"):
        from iris.llm.brain import Decision

        return Decision("none")


@pytest.fixture
def world(cfg, phrases, journal, fake_system, tmp_path):
    fake_system.available |= {"hyprctl", "wpctl", "wtype", "notify-send", "echo"}
    fake_system.outputs["hyprctl -j clients"] = (
        '[{"address": "0x1", "class": "kdenlive", "workspace": {"id": 3}}, {"address": "0x2", "class": "ghostty", "workspace": {"id": 1}}]'
    )
    fake_system.available |= {"kdenlive", "ghostty"}
    cfg.llm.enabled = True
    cfg.tasks = [
        BackgroundTask(
            "compilation", ["lance la compilation"], "echo fini", announce=True, notify=True
        )
    ]
    cfg.agents = AgentsConfig(enabled=True, default="echo", bins={"echo": "echo"})
    clock = FakeClock()
    tts = ConsoleTTS()
    tm = TaskManager(journal, alive=lambda p: False, poll_interval=0.05)
    brain = StreamBrain()
    router = Router(
        cfg,
        phrases,
        journal,
        brain=brain,
        tasks=tm,
        memory=Memory(journal),
        agents=AgentRunner(cfg.agents, tm),
    )
    parser = IntentParser(cfg.commands, task_phrases={t.name: t.phrases for t in cfg.tasks})
    assistant = Assistant(
        cfg,
        parser,
        router,
        phrases,
        tts,
        wake=TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold),
        journal=journal,
        clock=clock,
        brain=brain,
    )
    yield assistant, tts, clock, fake_system, tm, journal
    tm.shutdown(cancel=True)


def wait_finished(tm, timeout=5.0):
    deadline = time.time() + timeout
    while any(t.status == "running" for t in tm.all()) and time.time() < deadline:
        time.sleep(0.02)


def test_task_announced_when_finished(world):
    a, tts, clock, fake, tm, _ = world
    a.on_utterance("Iris, lance la compilation")
    assert tts.spoken[-1].startswith("compilation lancé")
    wait_finished(tm)
    a.tick()
    assert tts.spoken[-1] == "compilation terminé en 0 seconde."
    assert any(c[0] == "notify-send" for c in fake.calls)


def test_task_announcement_deferred_during_confirmation(world):
    a, tts, clock, fake, tm, _ = world
    fake.outputs["hyprctl -j clients"] = "[]"
    a.on_utterance("Iris, ferme tout")
    assert a.state == State.CONFIRMING
    tm.run("compilation", "echo fini")
    wait_finished(tm)
    a.tick()
    assert not any("terminé en" in s for s in tts.spoken)  # pas pendant la confirmation
    a.on_utterance("non")
    a.tick()
    assert tts.spoken[-1] == "compilation terminé en 0 seconde."


def test_agent_answer_announced(world):
    a, tts, clock, fake, tm, _ = world
    a.on_utterance("Iris, lance un agent pour dire bonjour")
    assert tts.spoken[-1] == "Je demande à Echo. Je te préviens quand c'est prêt."
    wait_finished(tm)
    a.tick()
    assert tts.spoken[-1] == "Echo a terminé : dire bonjour"


def test_streaming_reply_spoken_per_sentence(world):
    a, tts, _, _, _, journal = world
    a.on_utterance("Iris, explique-moi les workspaces")
    assert tts.spoken[-2:] == ["Première phrase.", "Seconde phrase."]
    assert (
        journal.recent(1)[0].intent == "ask_llm"
        and journal.recent(1)[0].result == "Première phrase. Seconde phrase."
    )


def test_streaming_failure_is_spoken(world):
    a, tts, _, _, _, _ = world
    a.brain.fail = True
    a.on_utterance("Iris, explique-moi les workspaces")
    assert tts.spoken[-1].startswith("Le modèle n'a pas répondu")


def test_dictation_terminal_mode_presses_enter(world):
    a, tts, _, fake, _, _ = world
    a.on_utterance("Iris, mode terminal")
    assert a.state == State.DICTATING and "Mode terminal" in tts.spoken[-1]
    a.on_utterance("npm test")
    assert ["wtype", "--", "npm test"] in fake.calls and ["wtype", "-k", "Return"] in fake.calls
    a.on_utterance("fin de dictée")
    assert a.state == State.IDLE


def test_memory_roundtrip_by_voice(world):
    a, tts, _, _, _, _ = world
    a.on_utterance("Iris, retiens que mon éditeur est Zed")
    a.on_utterance("Iris, qu'est-ce que tu sais de moi")
    assert tts.spoken[-1] == "Voilà ce que je sais : mon éditeur : Zed."


def test_snapshot_on_tick_and_resume_suggestion(world, monkeypatch):
    a, tts, clock, fake, tm, journal = world
    a._snapshots_enabled = True
    a._last_snapshot = clock() - 11 * 60
    a.tick()
    saved = journal.get_pref("session.last")
    assert saved == [{"exec": "kdenlive", "workspace": 3}, {"exec": "ghostty", "workspace": 1}]
    # proposition de reprise au démarrage : instantané assez ancien
    a.cfg.assistant.resume_prompt = True
    monkeypatch.setattr(journal, "pref_updated", lambda key: time.time() - 2 * 3600)
    assert a.maybe_suggest_resume() is True
    assert (
        a.state == State.CONFIRMING
        and tts.spoken[-1] == "Veux-tu reprendre ta session précédente : ghostty, kdenlive ?"
    )
    a.on_utterance("oui")
    assert "2 applications" in tts.spoken[-1]
    assert ["kdenlive"] in fake.launched and ["ghostty"] in fake.launched


def test_resume_suggestion_skipped_when_recent_or_disabled(world, monkeypatch):
    a, tts, clock, fake, tm, journal = world
    journal.set_pref("session.last", [{"exec": "a", "workspace": 1}, {"exec": "b", "workspace": 2}])
    assert a.maybe_suggest_resume() is False  # resume_prompt = false
    a.cfg.assistant.resume_prompt = True
    assert a.maybe_suggest_resume() is False  # trop récent
    assert a.state == State.IDLE


def test_suffix_wake_word_ambiguity(world, tmp_path, monkeypatch):
    a, tts, _, fake, _, _ = world
    fake.outputs["hyprctl -j clients"] = "[]"
    a.on_utterance("ferme tout iris")
    assert a.state == State.CONFIRMING  # « iris » = activation, « ferme tout » = commande
    a.on_utterance("non")
    a.on_utterance("cherche iris")
    assert tts.spoken[-1] == "Je cherche « iris »."
