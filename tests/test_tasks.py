import time

import pytest

from iris.core.journal import Journal
from iris.core.tasks import Task, TaskManager, human_duration


def wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def manager():
    journal = Journal(":memory:")
    tm = TaskManager(journal, alive=lambda pattern: False, poll_interval=0.05)
    yield tm, journal
    tm.shutdown(cancel=True)
    journal.close()


def test_run_success_and_event(manager):
    tm, journal = manager
    task = tm.run("compilation", "echo ok; echo fin")
    assert task.status == "running" and tm.running() == [task]
    assert wait_until(lambda: task.status != "running")
    assert task.status == "done" and task.returncode == 0 and task.summary() == "ok fin"
    events = tm.events()
    assert len(events) == 1 and events[0].task is task
    assert tm.events() == []
    row = journal.recent_tasks(1)[0]
    assert row["status"] == "done" and row["name"] == "compilation" and "ok" in row["output"]


def test_run_failure(manager):
    tm, _ = manager
    task = tm.run("build", "echo erreur >&2; exit 3")
    assert wait_until(lambda: task.status != "running")
    assert task.status == "failed" and task.returncode == 3 and task.summary() == "erreur"
    assert tm.last_finished() is task


def test_cancel(manager):
    tm, _ = manager
    task = tm.run("longue", "sleep 30")
    assert tm.cancel("longue") is task
    assert task.status == "cancelled" and tm.running() == []
    assert tm.cancel("longue") is None


def test_find_and_status(manager):
    tm, _ = manager
    a = tm.run("compilation du projet", "echo a")
    b = tm.run("tests", "echo b")
    assert tm.find("compilation") is a and tm.find("test") is b and tm.find(str(b.id)) is b
    assert tm.find("inconnu") is None
    assert wait_until(lambda: a.status != "running" and b.status != "running")
    assert tm.last_finished().name in ("compilation du projet", "tests")


def test_missing_cwd(manager):
    tm, _ = manager
    with pytest.raises(RuntimeError, match="dossier"):
        tm.run("x", "true", cwd="/nonexistent/dir")


def test_missing_binary_records_failure(manager):
    tm, _ = manager
    with pytest.raises(RuntimeError, match="impossible de lancer"):
        tm.run("x", ["/nonexistent/binary"])
    assert tm.all()[0].status == "failed"


def test_watch_process(manager):
    tm, _ = manager
    state = {"alive": True}
    tm._alive = lambda pattern: state["alive"]
    task = tm.watch("compilation", "cargo build")
    assert task.kind == "watch" and task.status == "running"
    state["alive"] = False
    assert wait_until(lambda: task.status == "done")
    assert tm.events()[0].task is task
    with pytest.raises(RuntimeError, match="aucun processus"):
        tm.watch("rien")


def test_summary_strips_ansi_and_truncates():
    task = Task(1, "t", "cmd", output="\x1b[32mok\x1b[0m " + "x" * 400)
    summary = task.summary(50)
    assert "\x1b" not in summary and summary.startswith("… ") and len(summary) <= 53


def test_human_duration():
    assert human_duration(5) == "5 secondes" and human_duration(1) == "1 seconde"
    assert human_duration(125) == "2 min 05" and human_duration(3700) == "1 h 01"
    assert human_duration(2, "en") == "2 seconds"
