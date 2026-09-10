"""Tâches en arrière-plan : commandes longues, agents IA, surveillance de processus.

``TaskManager.run()`` lance une commande détachée de la boucle vocale, capture la fin de sa
sortie, et publie un événement à sa fin (consommé par l'assistant → annonce vocale +
notification). ``watch()`` surveille un processus existant (``pgrep -f``) jusqu'à sa fin.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from iris.actions import system
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass
class Task:
    id: int
    name: str
    command: str
    kind: str = "shell"  # shell | agent | watch
    cwd: str | None = None
    started: float = field(default_factory=time.time)
    finished: float | None = None
    returncode: int | None = None
    status: str = "running"  # running | done | failed | cancelled
    output: str = ""  # queue de la sortie (stdout + stderr)
    announce: bool = True
    notify: bool = True
    meta: dict = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return (self.finished or time.time()) - self.started

    @property
    def ok(self) -> bool:
        return self.status == "done"

    def summary(self, max_chars: int = 300) -> str:
        """Résumé prononçable de la sortie (fin du texte, sans codes ANSI)."""
        text = _ANSI.sub("", self.output).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) <= max_chars:
            return text
        return "… " + text[-max_chars:]


@dataclass
class TaskEvent:
    task: Task
    kind: str = "finished"


def human_duration(seconds: float, lang: str = "fr") -> str:
    seconds = int(seconds)
    if seconds < 60:
        return (
            f"{seconds} seconde{'s' if seconds > 1 else ''}"
            if lang == "fr"
            else f"{seconds} second{'s' if seconds != 1 else ''}"
        )
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {sec:02d}" if lang == "fr" else f"{minutes} min {sec:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d}"


class TaskManager:
    def __init__(
        self,
        journal=None,
        max_output: int = 4000,
        alive: Callable[[str], bool] | None = None,
        poll_interval: float = 2.0,
    ) -> None:
        self.journal = journal
        self.max_output = max_output
        self._alive = alive or _pgrep_alive
        self.poll_interval = poll_interval
        self._tasks: dict[int, Task] = {}
        self._procs: dict[int, subprocess.Popen] = {}
        self._events: queue.Queue[TaskEvent] = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 1
        self._stop = threading.Event()

    # ------------------------------------------------------------------ lancement
    def run(
        self,
        name: str,
        command: str | list[str],
        *,
        cwd: str | Path | None = None,
        kind: str = "shell",
        announce: bool = True,
        notify: bool = True,
        env: dict[str, str] | None = None,
        meta: dict | None = None,
    ) -> Task:
        display = command if isinstance(command, str) else " ".join(shlex.quote(c) for c in command)
        workdir = str(Path(cwd).expanduser()) if cwd else None
        if workdir and not Path(workdir).is_dir():
            raise RuntimeError(f"dossier introuvable : {workdir}")
        task = self._new_task(name, display, kind, workdir, announce, notify, meta or {})
        try:
            proc = subprocess.Popen(
                command,
                shell=isinstance(command, str),
                cwd=workdir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, **env} if env else None,
                start_new_session=True,
                text=True,
                errors="replace",
            )
        except (FileNotFoundError, OSError) as exc:
            task.status = "failed"
            task.finished = time.time()
            task.output = str(exc)
            self._record(task, finished=True)
            raise RuntimeError(f"impossible de lancer « {name} » : {exc}") from exc
        with self._lock:
            self._procs[task.id] = proc
        self._record(task)
        threading.Thread(
            target=self._reader, args=(task, proc), name=f"iris-task-{task.id}", daemon=True
        ).start()
        log.info("Tâche %d « %s » lancée : %s", task.id, name, display)
        return task

    def watch(
        self, name: str, pattern: str | None = None, *, announce: bool = True, notify: bool = True
    ) -> Task:
        pattern = pattern or name
        if not self._alive(pattern):
            raise RuntimeError(f"aucun processus « {pattern} » en cours")
        task = self._new_task(
            name, f"watch:{pattern}", "watch", None, announce, notify, {"pattern": pattern}
        )
        self._record(task)
        threading.Thread(
            target=self._watcher, args=(task, pattern), name=f"iris-watch-{task.id}", daemon=True
        ).start()
        return task

    # ------------------------------------------------------------------ consultation
    def running(self) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == "running"]

    def all(self) -> list[Task]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.id)

    def find(self, query: str, running_only: bool = False) -> Task | None:
        q = canonical(query)
        candidates = self.running() if running_only else self.all()
        if not candidates:
            return None
        if q.isdigit():
            return next((t for t in candidates if t.id == int(q)), None)
        best: tuple[float, Task] | None = None
        for task in candidates:
            name = canonical(task.name)
            score = (
                1.0
                if name == q
                else (0.9 if q in name or name in q else SequenceMatcher(None, q, name).ratio())
            )
            if score >= 0.6 and (
                best is None or score > best[0] or (score == best[0] and task.id > best[1].id)
            ):
                best = (score, task)
        return best[1] if best else None

    def last_finished(self, kind: str | None = None) -> Task | None:
        done = [t for t in self.all() if t.status != "running" and (kind is None or t.kind == kind)]
        return max(done, key=lambda t: t.finished or 0) if done else None

    def events(self) -> list[TaskEvent]:
        drained: list[TaskEvent] = []
        while True:
            try:
                drained.append(self._events.get_nowait())
            except queue.Empty:
                return drained

    # ------------------------------------------------------------------ contrôle
    def cancel(self, query: str) -> Task | None:
        task = self.find(query, running_only=True)
        if task is None:
            return None
        with self._lock:
            proc = self._procs.get(task.id)
        if proc is not None:
            try:
                os.killpg(proc.pid, 15)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, 9)
                except OSError:
                    proc.kill()
        task.status = "cancelled"
        task.finished = time.time()
        self._record(task, finished=True)
        return task

    def shutdown(self, cancel: bool = False) -> None:
        """Arrête les surveillances ; les commandes lancées continuent (sauf ``cancel=True``)."""
        self._stop.set()
        if cancel:
            for task in self.running():
                if task.kind != "watch":
                    self.cancel(str(task.id))

    # ------------------------------------------------------------------ interne
    def _new_task(self, name, display, kind, workdir, announce, notify, meta) -> Task:
        with self._lock:
            task = Task(
                self._next_id,
                name,
                display,
                kind,
                workdir,
                announce=announce,
                notify=notify,
                meta=meta,
            )
            self._next_id += 1
            self._tasks[task.id] = task
        return task

    def _reader(self, task: Task, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        chunks: list[str] = []
        size = 0
        try:
            for line in proc.stdout:
                chunks.append(line)
                size += len(line)
                while size > self.max_output * 2 and chunks:
                    size -= len(chunks.pop(0))
        except (OSError, ValueError):
            pass
        returncode = proc.wait()
        if task.status == "cancelled":
            return
        task.output = "".join(chunks)[-self.max_output :]
        task.returncode = returncode
        task.finished = time.time()
        task.status = "done" if returncode == 0 else "failed"
        with self._lock:
            self._procs.pop(task.id, None)
        self._record(task, finished=True)
        log.info(
            "Tâche %d « %s » terminée (%s, code %s, %.0fs)",
            task.id,
            task.name,
            task.status,
            returncode,
            task.duration_s,
        )
        self._events.put(TaskEvent(task))

    def _watcher(self, task: Task, pattern: str) -> None:
        while not self._stop.is_set() and task.status == "running":
            time.sleep(self.poll_interval)
            if not self._alive(pattern):
                task.finished = time.time()
                task.status = "done"
                task.returncode = 0
                self._record(task, finished=True)
                self._events.put(TaskEvent(task))
                return

    def _record(self, task: Task, finished: bool = False) -> None:
        if self.journal is None:
            return
        try:
            if finished:
                self.journal.finish_task(
                    task.id,
                    task.status,
                    task.returncode,
                    task.finished or time.time(),
                    task.summary(800),
                )
            else:
                self.journal.start_task(task.id, task.name, task.command, task.kind, task.started)
        except Exception as exc:  # noqa: BLE001
            log.debug("journal tâches : %s", exc)


def _pgrep_alive(pattern: str) -> bool:
    if not system.which("pgrep"):
        return False
    res = system.run(["pgrep", "-f", "--", pattern], timeout=5)
    # exclut notre propre pgrep et le processus iris qui contient le motif dans ses arguments
    pids = [p for p in res.out.split() if p.isdigit() and int(p) != os.getpid()]
    return bool(pids)
