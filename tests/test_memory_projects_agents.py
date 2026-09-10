from pathlib import Path

import pytest

from iris.actions.apps import AppResolver
from iris.actions.projects import ProjectResolver
from iris.agents.runner import PRESETS, AgentRunner
from iris.config import AgentsConfig
from iris.core.journal import Journal
from iris.core.memory import Memory
from iris.core.tasks import TaskManager


# ---------------------------------------------------------------- mémoire
@pytest.fixture
def memory():
    journal = Journal(":memory:")
    yield Memory(journal)
    journal.close()


def test_remember_key_value_and_free_text(memory):
    fact = memory.remember("mon éditeur est Zed")
    assert (fact.key, fact.value) == (
        "mon éditeur",
        "Zed",
    ) and fact.sentence() == "mon éditeur : Zed"
    free = memory.remember("je pars à 18h")
    assert free.key.startswith("fact:") and free.sentence() == "je pars à 18h"
    memory.remember("mon éditeur est Helix")  # même clé → mise à jour
    assert [f.sentence() for f in memory.facts()] == ["je pars à 18h", "mon éditeur : Helix"]
    block = memory.facts_block()
    assert block.startswith("Ce que tu sais") and "- mon éditeur : Helix" in block


def test_forget(memory):
    memory.remember("mon éditeur est Zed")
    memory.remember("je préfère le thème tokyo night")
    assert memory.forget("thème").sentence() == "je préfère le thème tokyo night"
    assert memory.forget("licorne") is None
    assert memory.forget_all() == 1 and memory.facts() == [] and memory.facts_block() == ""


def test_chat_history_persists(memory):
    memory.add_turn("user", "salut")
    memory.add_turn("assistant", "Bonjour !")
    assert memory.history(6) == [
        {"role": "user", "content": "salut"},
        {"role": "assistant", "content": "Bonjour !"},
    ]
    memory.clear_history()
    assert memory.history(6) == []


# ---------------------------------------------------------------- projets
@pytest.fixture
def workspace(tmp_path: Path):
    for name in ("cnvs-clone", "iris", "notes-perso", ".cache"):
        (tmp_path / "code" / name).mkdir(parents=True)
    (tmp_path / "ailleurs" / "site-web").mkdir(parents=True)
    return tmp_path


def test_project_resolution(workspace):
    resolver = ProjectResolver(
        {"site": str(workspace / "ailleurs" / "site-web")},
        [str(workspace / "code"), "/nonexistent"],
    )
    names = resolver.candidates()
    assert set(names) == {"site", "cnvs clone", "iris", "notes perso"}
    assert resolver.resolve("cnvs clone") == workspace / "code" / "cnvs-clone"
    assert resolver.resolve("cnvs-clone") == workspace / "code" / "cnvs-clone"
    assert resolver.resolve("cnvs") == workspace / "code" / "cnvs-clone"  # partiel
    assert resolver.resolve("site") == workspace / "ailleurs" / "site-web"
    assert resolver.resolve(str(workspace / "ailleurs")) == workspace / "ailleurs"  # chemin direct
    assert resolver.resolve("zzz") is None


def test_project_open_launches_editor_and_terminal(workspace, fake_system, monkeypatch):
    monkeypatch.setenv("TERMINAL", "ghostty")
    fake_system.available |= {"ghostty", "code"}
    resolver = ProjectResolver({}, [str(workspace / "code")], AppResolver())
    name, path = resolver.open("iris")
    assert name == "iris" and path == workspace / "code" / "iris"
    assert ["code", str(path)] in fake_system.launched
    assert ["ghostty", f"--working-directory={path}"] in fake_system.launched


def test_project_terminal_fallback_sh(workspace, fake_system, monkeypatch):
    monkeypatch.setenv("TERMINAL", "xterm")
    fake_system.available.add("xterm")
    resolver = ProjectResolver({}, [str(workspace / "code")], AppResolver())
    argv = resolver.terminal_argv(workspace / "code" / "iris")
    assert argv[:2] == ["sh", "-c"] and "exec xterm" in argv[2]
    with pytest.raises(RuntimeError, match="introuvable"):
        resolver.open("inconnu")


# ---------------------------------------------------------------- agents
@pytest.fixture
def runner(fake_system, workspace):
    fake_system.available |= {"claude", "opencode", "echo"}
    cfg = AgentsConfig(enabled=True, default="claude", bins={"echo": "echo"})
    tm = TaskManager(alive=lambda p: False)
    yield AgentRunner(cfg, tm, ProjectResolver({}, [str(workspace / "code")])), tm, cfg
    tm.shutdown(cancel=True)


def test_agent_specs(runner):
    r, _, _ = runner
    assert r.spec("claude", "corrige").argv == [
        "claude",
        "-p",
        "corrige",
        "--output-format",
        "text",
    ]
    assert r.spec("opencode", "refactore").argv == ["opencode", "run", "refactore"]
    assert r.spec(None, "x").name == "claude" and r.spec("l'agent", "x").name == "claude"
    assert r.available("claude") and not r.available("codex")
    with pytest.raises(RuntimeError, match="inconnu"):
        r.spec("hal9000", "x")
    with pytest.raises(RuntimeError, match="introuvable"):
        r.spec("codex", "x")
    assert set(PRESETS) >= {"claude", "opencode", "codex", "gemini"}


def test_split_project(runner):
    r, _, _ = runner
    assert r.split_project("corrige les tests dans le projet cnvs-clone") == (
        "corrige les tests",
        "cnvs-clone",
    )
    assert r.split_project("écris un readme in project iris") == ("écris un readme", "iris")
    assert r.split_project("corrige les tests") == ("corrige les tests", None)


def test_agent_run_resolves_project_and_completes(runner, workspace):
    r, tm, cfg = runner
    cfg.default = "echo"
    task = r.run(None, "bonjour agent dans le projet iris")
    assert task.kind == "agent" and task.cwd == str(workspace / "code" / "iris")
    assert task.meta["label"] == "Echo" and task.meta["prompt"] == "bonjour agent"
    import time

    deadline = time.time() + 5
    while task.status == "running" and time.time() < deadline:
        time.sleep(0.02)
    assert task.status == "done" and task.summary() == "bonjour agent"
    with pytest.raises(RuntimeError, match="projet introuvable"):
        r.run("echo", "x dans le projet zzz")


def test_agent_disabled_and_legacy_flag():
    cfg = AgentsConfig()
    r = AgentRunner(cfg, TaskManager())
    assert not r.enabled
    with pytest.raises(RuntimeError, match="désactivés"):
        r.run("claude", "x")
    assert AgentRunner(AgentsConfig(claude_code_enabled=True), TaskManager()).enabled
