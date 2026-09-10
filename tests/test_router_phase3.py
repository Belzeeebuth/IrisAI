import time

import pytest

from iris.actions.projects import ProjectResolver
from iris.agents.runner import AgentRunner
from iris.config import AgentsConfig, BackgroundTask
from iris.core.memory import Memory
from iris.core.router import Router
from iris.core.tasks import TaskManager
from iris.nlu.intents import Intent, IntentParser


class StreamBrain:
    def converse_stream(self, text, language="fr"):
        yield "Première phrase."
        yield "Seconde phrase."

    def converse(self, text, language="fr"):
        return "Réponse complète."


@pytest.fixture
def router(cfg, phrases, journal, fake_system, tmp_path):
    fake_system.available |= {"hyprctl", "wtype", "echo"}
    (tmp_path / "code" / "iris").mkdir(parents=True)
    cfg.tasks = [
        BackgroundTask(
            "compilation", ["lance la compilation"], "echo compilé", announce=True, notify=False
        )
    ]
    cfg.agents = AgentsConfig(enabled=True, default="echo", bins={"echo": "echo"})
    tm = TaskManager(journal, alive=lambda p: p == "cargo", poll_interval=0.05)
    projects = ProjectResolver({}, [str(tmp_path / "code")])
    r = Router(
        cfg,
        phrases,
        journal,
        brain=StreamBrain(),
        tasks=tm,
        memory=Memory(journal),
        agents=AgentRunner(cfg.agents, tm, projects),
        projects=projects,
    )
    yield r
    tm.shutdown(cancel=True)


def parse(text: str, **kw) -> Intent:
    intent = IntentParser(task_phrases={"compilation": ["lance la compilation"]}, **kw).parse(text)
    assert intent is not None, text
    return intent


def wait(task, timeout=5.0):
    deadline = time.time() + timeout
    while task.status == "running" and time.time() < deadline:
        time.sleep(0.02)


def test_memory_intents(router):
    assert router.execute(parse("retiens que mon éditeur est Zed")).text == "C'est noté."
    assert (
        router.execute(parse("qu'est-ce que tu sais de moi")).text
        == "Voilà ce que je sais : mon éditeur : Zed."
    )
    assert router.execute(parse("oublie mon éditeur")).text == "Oublié : mon éditeur : Zed."
    assert not router.execute(parse("oublie les licornes")).ok
    assert router.execute(parse("qu'est-ce que tu sais de moi")).text.startswith(
        "Je ne sais encore rien"
    )
    router.execute(parse("retiens que je pars à 18h"))
    assert router.execute(parse("oublie tout")).text == "Mémoire effacée."


def test_task_run_status_result(router):
    reply = router.execute(parse("lance la compilation"))
    assert reply.text == "compilation lancé. Je te préviens quand c'est terminé."
    task = router.tasks.find("compilation")
    wait(task)
    assert (
        router.execute(parse("où en est la compilation")).text
        == "Dernière terminée : compilation, réussie."
    )
    assert router.execute(parse("lis le résultat")).text == "compilation : compilé"
    assert (
        router.execute(parse("mes tâches")).text
        == "Aucune tâche en cours. Dernière terminée : compilation, réussie."
    )
    assert not router.execute(parse("lance la tâche inconnue")).ok


def test_task_watch_and_cancel(router):
    reply = router.execute(parse("surveille cargo"))
    assert reply.text == "Je surveille cargo. Je te préviens quand c'est fini."
    assert router.execute(parse("mes tâches")).text.startswith("En cours : cargo, depuis")
    assert router.execute(parse("annule cargo")).text == "cargo annulé."
    assert not router.execute(parse("surveille rien-du-tout")).ok
    assert not router.execute(parse("annule la compilation")).ok


def test_ask_agent_runs_in_background(router):
    reply = router.execute(parse("lance un agent pour ranger le bureau dans le projet iris"))
    assert reply.text == "Je demande à Echo. Je te préviens quand c'est prêt."
    task = router.tasks.find("Echo")
    assert task is not None and task.kind == "agent" and task.cwd.endswith("/code/iris")
    wait(task)
    assert router.format_task_event(task) == "Echo a terminé : ranger le bureau"
    assert router.execute(parse("qu'a répondu l'agent")).text == f"{task.name} : ranger le bureau"


def test_ask_agent_disabled(router):
    router.agents.cfg.enabled = False
    assert "désactivés" in router.execute(parse("demande à claude de ranger")).text


def test_format_task_event_variants(router):
    from iris.core.tasks import Task

    t = Task(
        1,
        "build",
        "cmd",
        status="done",
        returncode=0,
        started=time.time() - 65,
        finished=time.time(),
    )
    assert router.format_task_event(t) == "build terminé en 1 min 05."
    t.status, t.returncode = "failed", 2
    assert router.format_task_event(t).startswith("build a échoué après 1 min 05, code 2")
    w = Task(2, "cargo", "watch:cargo", kind="watch", status="done")
    assert router.format_task_event(w) == "cargo est terminé."


def test_open_project_and_type_and_enter(router, fake_system, monkeypatch):
    monkeypatch.setenv("TERMINAL", "ghostty")
    fake_system.available |= {"ghostty", "code"}
    assert router.execute(parse("ouvre le projet iris")).text == "Projet iris ouvert."
    assert not router.execute(parse("ouvre le projet zzz")).ok
    assert router.execute(parse("envoie : npm test")).text == "Envoyé."
    assert ["wtype", "--", "npm test"] in fake_system.calls and [
        "wtype",
        "-k",
        "Return",
    ] in fake_system.calls
    reply = router.execute(parse("mode terminal"))
    assert reply.control == "dictate" and reply.data["enter"] is True


def test_ask_llm_streaming_reply(router):
    reply = router.execute(parse("explique-moi les workspaces"))
    assert reply.stream is not None and list(reply.stream) == [
        "Première phrase.",
        "Seconde phrase.",
    ]
    router.cfg.llm.stream = False
    assert router.execute(parse("explique-moi les workspaces")).text == "Réponse complète."


def test_session_resume_without_snapshot(router):
    assert not router.execute(parse("reprends ma session d'hier")).ok


def test_session_resume_with_snapshot(router, fake_system, journal):
    fake_system.available.add("kdenlive")
    journal.set_pref(
        "session.last", [{"exec": "kdenlive", "workspace": 3}, {"exec": "kdenlive", "workspace": 4}]
    )
    reply = router.execute(parse("reprends ma session d'hier"))
    assert reply.ok and "2 applications" in reply.text
