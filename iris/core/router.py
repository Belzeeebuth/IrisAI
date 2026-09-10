"""Routeur : intention → action → réponse.

Chaque intention a un gestionnaire ``_h_<nom>``. Les erreurs sont capturées et transformées
en réponse parlée ; chaque exécution est tracée dans le journal. Le LLM (``brain``) peut
proposer une action : ``intent_from_decision`` la convertit en intention ordinaire, qui repasse
par les mêmes confirmations et gestionnaires.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from iris.actions import (
    audio_ctl,
    brightness,
    clock,
    devices,
    hyprland,
    media,
    monitors,
    notifications,
    notify,
    omarchy,
    power,
    typing,
    web,
)
from iris.actions.apps import AppResolver
from iris.actions.projects import ProjectResolver
from iris.actions.sessions import SessionManager
from iris.config import Config
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.core.tasks import Task, TaskManager, human_duration
from iris.nlu.intents import CONFIRM_INTENTS, Intent
from iris.nlu.normalize import canonical

log = logging.getLogger(__name__)


@dataclass
class Reply:
    text: str
    ok: bool = True
    keep_listening: bool = True  # garder la fenêtre d'enchaînement après la réponse
    data: dict[str, Any] = field(default_factory=dict)
    control: str | None = None  # "stop" | "pause" | "resume" | "dictate" | "dictate_stop"
    stream: Any = None  # itérateur de phrases (réponse LLM en streaming)

    def __str__(self) -> str:
        return self.text


class Router:
    def __init__(
        self,
        cfg: Config,
        phrases: Phrasebook,
        journal: Journal | None = None,
        apps: AppResolver | None = None,
        agent=None,
        brain=None,
        sessions: SessionManager | None = None,
        tasks: TaskManager | None = None,
        memory=None,
        agents=None,
        projects: ProjectResolver | None = None,
    ) -> None:
        self.cfg = cfg
        self.p = phrases
        self.journal = journal
        self.apps = apps or AppResolver(
            cfg.apps, cfg.system.terminal, cfg.system.browser, cfg.system.editor
        )
        self.agent = agent
        self.brain = brain
        self.sessions = sessions or SessionManager(cfg.sessions, journal, self.apps)
        self.tasks = tasks or TaskManager(journal)
        self.memory = memory
        self.agents = agents
        self.projects = projects or ProjectResolver(
            cfg.projects, cfg.system.project_dirs, self.apps
        )
        self.background = {canonical(t.name): t for t in cfg.tasks}

    @property
    def lang(self) -> str:
        return self.p.lang

    # ------------------------------------------------------------------ API
    def knows(self, intent_name: str) -> bool:
        return hasattr(self, f"_h_{intent_name}")

    def confirmation_question(self, intent: Intent) -> str | None:
        if not intent.requires_confirmation:
            return None
        if intent.name == "custom" and intent.command:
            return self.p.get("confirm_custom", name=intent.command.name)
        if intent.name in ("close_all", "suspend", "shutdown", "reboot"):
            return self.p.get(f"confirm_{intent.name}")
        return self.p.get("confirm_custom", name=intent.name)

    def intent_from_decision(self, decision) -> Intent | None:
        """Intention ordinaire construite depuis une décision du LLM (None si inconnue)."""
        name = decision.intent
        if not name or not self.knows(name) or name in ("custom", "ask_llm", "ask_agent"):
            return None
        slots = dict(decision.slots)
        if "n" in slots:
            try:
                slots["n"] = int(slots["n"])
            except (TypeError, ValueError):
                del slots["n"]
        return Intent(
            name,
            slots,
            confidence=0.6,
            text=decision.reply or "",
            requires_confirmation=name in CONFIRM_INTENTS,
        )

    def execute(self, intent: Intent) -> Reply:
        handler = getattr(self, f"_h_{intent.name}", None)
        started = time.monotonic()
        if handler is None:
            reply = Reply(self.p.get("not_understood"), ok=False)
        else:
            try:
                reply = handler(intent)
            except RuntimeError as exc:  # erreur attendue (outil absent, Hyprland injoignable…)
                log.warning("Intention %s : %s", intent.name, exc)
                reply = Reply(self.p.get("error", reason=str(exc)), ok=False)
            except Exception as exc:  # noqa: BLE001 - toute erreur devient une réponse
                log.exception("Échec inattendu de l'intention %s", intent.name)
                reply = Reply(self.p.get("error", reason=str(exc)), ok=False)
        duration_ms = int((time.monotonic() - started) * 1000)
        if self.journal is not None and reply.stream is None:
            self.journal.log_action(
                intent.name, intent.slots, intent.text, reply.ok, reply.text, duration_ms
            )
        if self.cfg.system.notify and reply.data.get("notify"):
            notify.send(self.cfg.assistant.name, reply.text)
        return reply

    # ------------------------------------------------------------------ helpers
    def _launcher(self) -> str:
        return self.cfg.system.launcher

    def _hypr(self) -> None:
        if not hyprland.available():
            raise RuntimeError(self.p.get("hyprland_unavailable"))

    def _plural(self, n: int) -> str:
        return "s" if n > 1 else ""

    # ------------------------------------------------------------------ social / contrôle
    def _h_greet(self, intent: Intent) -> Reply:
        return Reply(self.p.get("greet"))

    def _h_thanks(self, intent: Intent) -> Reply:
        return Reply(self.p.get("thanks_reply"), keep_listening=False)

    def _h_who_are_you(self, intent: Intent) -> Reply:
        return Reply(self.p.get("who_are_you"))

    def _h_help(self, intent: Intent) -> Reply:
        return Reply(self.p.get("help"))

    def _h_stop(self, intent: Intent) -> Reply:
        return Reply(self.p.get("stop"), keep_listening=False, control="stop")

    def _h_pause_listening(self, intent: Intent) -> Reply:
        minutes = int(intent.slot("minutes") or 10)
        return Reply(
            self.p.get("paused", minutes=minutes),
            keep_listening=False,
            control="pause",
            data={"minutes": minutes},
        )

    def _h_resume_listening(self, intent: Intent) -> Reply:
        return Reply(self.p.get("resumed"), control="resume")

    def _h_time(self, intent: Intent) -> Reply:
        return Reply(clock.say_time(lang=self.lang))

    def _h_date(self, intent: Intent) -> Reply:
        return Reply(clock.say_date(lang=self.lang))

    def _h_say(self, intent: Intent) -> Reply:
        return Reply(str(intent.slot("text", "")))

    # ------------------------------------------------------------------ dictée
    def _h_type_text(self, intent: Intent) -> Reply:
        text = str(intent.slot("text", ""))
        tool = typing.type_text(text, self.cfg.system.typing_tool)
        key = "typed_clipboard" if tool == "clipboard" else "typed"
        return Reply(self.p.get(key), data={"tool": tool})

    def _h_dictation_start(self, intent: Intent) -> Reply:
        if typing.available_tool(self.cfg.system.typing_tool) is None:
            raise RuntimeError("aucun outil de saisie (installe wtype)")
        return Reply(self.p.get("dictation_started"), keep_listening=False, control="dictate")

    def _h_dictation_start_enter(self, intent: Intent) -> Reply:
        if typing.available_tool(self.cfg.system.typing_tool) is None:
            raise RuntimeError("aucun outil de saisie (installe wtype)")
        return Reply(
            self.p.get("dictation_started_enter"),
            keep_listening=False,
            control="dictate",
            data={"enter": True},
        )

    def _h_type_and_enter(self, intent: Intent) -> Reply:
        text = str(intent.slot("text", ""))
        tool = typing.type_text(text, self.cfg.system.typing_tool, press_enter=True)
        return Reply(
            self.p.get("typed_clipboard") if tool == "clipboard" else self.p.get("typed_enter"),
            data={"tool": tool},
        )

    def _h_dictation_stop(self, intent: Intent) -> Reply:
        return Reply(self.p.get("dictation_stopped"), keep_listening=False, control="dictate_stop")

    # ------------------------------------------------------------------ applications
    def _h_open_app(self, intent: Intent) -> Reply:
        name = str(intent.slot("app", ""))
        app = self.apps.open(str(intent.slot("app_raw") or name), self._launcher())
        if app is None:
            return Reply(self.p.get("app_not_found", app=name), ok=False)
        key = "app_webapp_opened" if app.webapp else "app_opened"
        return Reply(self.p.get(key, app=app.label))

    def _h_close_app(self, intent: Intent) -> Reply:
        name = str(intent.slot("app", ""))
        _app, closed = self.apps.close(str(intent.slot("app_raw") or name))
        label = name
        if closed == 0:
            return Reply(self.p.get("app_not_running", app=label), ok=False)
        if closed == 1:
            return Reply(self.p.get("app_closed", app=label))
        return Reply(self.p.get("app_closed_many", app=label, n=closed))

    def _h_close_all(self, intent: Intent) -> Reply:
        self._hypr()
        n = hyprland.close_all_windows()
        return Reply(self.p.get("close_all_done", n=n) if n else self.p.get("close_all_none"))

    # ------------------------------------------------------------------ fenêtres / workspaces / écrans
    def _h_window_close(self, intent: Intent) -> Reply:
        self._hypr()
        hyprland.close_active_window()
        return Reply(self.p.get("window_closed"))

    def _h_window_fullscreen(self, intent: Intent) -> Reply:
        self._hypr()
        hyprland.toggle_fullscreen()
        return Reply(self.p.get("window_fullscreen"))

    def _h_window_floating(self, intent: Intent) -> Reply:
        self._hypr()
        hyprland.toggle_floating()
        return Reply(self.p.get("window_floating"))

    def _h_window_move_workspace(self, intent: Intent) -> Reply:
        self._hypr()
        n = int(intent.slot("n"))
        hyprland.move_active_to_workspace(n)
        return Reply(self.p.get("window_moved", n=n))

    def _h_workspace_switch(self, intent: Intent) -> Reply:
        self._hypr()
        n = int(intent.slot("n"))
        hyprland.switch_workspace(n)
        return Reply(self.p.get("workspace_switched", n=n))

    def _h_workspace_next(self, intent: Intent) -> Reply:
        self._hypr()
        hyprland.workspace_relative(+1)
        return Reply(self.p.get("workspace_next"))

    def _h_workspace_prev(self, intent: Intent) -> Reply:
        self._hypr()
        hyprland.workspace_relative(-1)
        return Reply(self.p.get("workspace_prev"))

    def _direction_word(self, direction: str) -> str:
        key = monitors.DIRECTIONS.get(direction.lower(), "")
        canonical_key = {
            "l": "left",
            "r": "right",
            "u": "up",
            "d": "down",
            "+1": "next",
            "-1": "prev",
        }.get(key, direction)
        return self.p.get(canonical_key)

    def _h_monitor_move(self, intent: Intent) -> Reply:
        self._hypr()
        direction = str(intent.slot("direction", "right"))
        monitors.move_window_to_monitor(direction)
        return Reply(self.p.get("monitor_moved", direction=self._direction_word(direction)))

    def _h_monitor_focus(self, intent: Intent) -> Reply:
        self._hypr()
        direction = str(intent.slot("direction", "right"))
        monitors.focus_monitor(direction)
        return Reply(self.p.get("monitor_focused", direction=self._direction_word(direction)))

    # ------------------------------------------------------------------ volume / luminosité
    def _h_volume_set(self, intent: Intent) -> Reply:
        n = audio_ctl.set_volume(int(intent.slot("n")))
        return Reply(self.p.get("volume_set", n=n))

    def _h_volume_up(self, intent: Intent) -> Reply:
        step = int(intent.slot("n") or self.cfg.system.volume_step)
        n = audio_ctl.change_volume(+step)
        return Reply(
            self.p.get("volume_changed", n=n) if n >= 0 else self.p.get("volume_changed_unknown")
        )

    def _h_volume_down(self, intent: Intent) -> Reply:
        step = int(intent.slot("n") or self.cfg.system.volume_step)
        n = audio_ctl.change_volume(-step)
        return Reply(
            self.p.get("volume_changed", n=n) if n >= 0 else self.p.get("volume_changed_unknown")
        )

    def _h_volume_mute(self, intent: Intent) -> Reply:
        audio_ctl.set_mute(True)
        return Reply(self.p.get("volume_muted"))

    def _h_volume_unmute(self, intent: Intent) -> Reply:
        audio_ctl.set_mute(False)
        return Reply(self.p.get("volume_unmuted"))

    def _h_brightness_set(self, intent: Intent) -> Reply:
        n = brightness.set_brightness(int(intent.slot("n")))
        return Reply(self.p.get("brightness_set", n=n))

    def _h_brightness_up(self, intent: Intent) -> Reply:
        step = int(intent.slot("n") or self.cfg.system.brightness_step)
        n = brightness.change_brightness(+step)
        return Reply(
            self.p.get("brightness_changed", n=n)
            if n >= 0
            else self.p.get("brightness_changed_unknown")
        )

    def _h_brightness_down(self, intent: Intent) -> Reply:
        step = int(intent.slot("n") or self.cfg.system.brightness_step)
        n = brightness.change_brightness(-step)
        return Reply(
            self.p.get("brightness_changed", n=n)
            if n >= 0
            else self.p.get("brightness_changed_unknown")
        )

    # ------------------------------------------------------------------ média
    def _h_media_play_pause(self, intent: Intent) -> Reply:
        media.play_pause()
        return Reply(self.p.get("media_toggled"))

    def _h_media_next(self, intent: Intent) -> Reply:
        media.next_track()
        title = media.now_playing()
        return Reply(f"{self.p.get('media_next')} {title}".strip())

    def _h_media_prev(self, intent: Intent) -> Reply:
        media.previous_track()
        return Reply(self.p.get("media_prev"))

    # ------------------------------------------------------------------ Omarchy
    def _h_theme_next(self, intent: Intent) -> Reply:
        omarchy.theme_next()
        return Reply(self.p.get("theme_next"))

    def _h_theme_set(self, intent: Intent) -> Reply:
        chosen = omarchy.theme_set(str(intent.slot("name", "")))
        return Reply(self.p.get("theme_set", name=chosen.replace("-", " ")))

    def _h_night_light(self, intent: Intent) -> Reply:
        omarchy.toggle_nightlight()
        return Reply(self.p.get("nightlight_toggled"))

    def _h_screenshot(self, intent: Intent) -> Reply:
        omarchy.screenshot()
        return Reply(self.p.get("screenshot"), keep_listening=False)

    def _h_lock_screen(self, intent: Intent) -> Reply:
        omarchy.lock_screen()
        return Reply(self.p.get("locked"), keep_listening=False)

    # ------------------------------------------------------------------ périphériques
    def _h_bluetooth_on(self, intent: Intent) -> Reply:
        devices.bluetooth_power(True)
        return Reply(self.p.get("bluetooth_on"))

    def _h_bluetooth_off(self, intent: Intent) -> Reply:
        devices.bluetooth_power(False)
        return Reply(self.p.get("bluetooth_off"))

    def _bt_query(self, intent: Intent) -> str:
        raw = str(intent.slot("device_raw") or intent.slot("device") or "")
        aliases = {k.lower(): v for k, v in self.cfg.bluetooth.items()}
        from iris.nlu.normalize import canonical

        for candidate in (raw, str(intent.slot("device", ""))):
            if canonical(candidate) in {canonical(k) for k in aliases}:
                return candidate
        return str(intent.slot("device") or raw)

    def _h_bluetooth_connect(self, intent: Intent) -> Reply:
        name = devices.bluetooth_connect(self._bt_query(intent), self.cfg.bluetooth)
        return Reply(self.p.get("bluetooth_connected", device=name))

    def _h_bluetooth_disconnect(self, intent: Intent) -> Reply:
        name = devices.bluetooth_disconnect(self._bt_query(intent), self.cfg.bluetooth)
        return Reply(self.p.get("bluetooth_disconnected", device=name))

    def _h_wifi_on(self, intent: Intent) -> Reply:
        devices.wifi_power(True)
        return Reply(self.p.get("wifi_on"))

    def _h_wifi_off(self, intent: Intent) -> Reply:
        devices.wifi_power(False)
        return Reply(self.p.get("wifi_off"))

    def _h_airplane_on(self, intent: Intent) -> Reply:
        devices.airplane_mode(True)
        return Reply(self.p.get("airplane_on"))

    def _h_airplane_off(self, intent: Intent) -> Reply:
        devices.airplane_mode(False)
        return Reply(self.p.get("airplane_off"))

    def _h_battery(self, intent: Intent) -> Reply:
        info = devices.battery()
        if info is None:
            return Reply(self.p.get("battery_none"), ok=False)
        percent, status = info
        suffix = self.p.get("battery_charging") if status.lower() == "charging" else ""
        return Reply(self.p.get("battery", n=percent, status=suffix))

    def _h_audio_output_switch(self, intent: Intent) -> Reply:
        name = devices.switch_audio_output()
        return Reply(self.p.get("audio_output_switched", name=name))

    # ------------------------------------------------------------------ notifications
    def _h_notifications_read(self, intent: Intent) -> Reply:
        items = notifications.history(limit=5)
        return Reply(notifications.summarize(items, self.lang))

    def _h_notifications_dismiss(self, intent: Intent) -> Reply:
        notifications.dismiss_all()
        return Reply(self.p.get("notifications_dismissed"))

    def _h_dnd_on(self, intent: Intent) -> Reply:
        notifications.do_not_disturb(True)
        return Reply(self.p.get("dnd_on"))

    def _h_dnd_off(self, intent: Intent) -> Reply:
        notifications.do_not_disturb(False)
        return Reply(self.p.get("dnd_off"))

    # ------------------------------------------------------------------ sessions
    def _h_session_open(self, intent: Intent) -> Reply:
        name, n = self.sessions.open(str(intent.slot("name", "")), self._launcher())
        return Reply(self.p.get("session_opened", name=name, n=n, s=self._plural(n)))

    def _h_session_save(self, intent: Intent) -> Reply:
        name = str(intent.slot("name", ""))
        n = self.sessions.save(name)
        return Reply(self.p.get("session_saved", name=name, n=n, s=self._plural(n)))

    def _h_session_resume(self, intent: Intent) -> Reply:
        if self.sessions.find("last") is None:
            return Reply(self.p.get("resume_none"), ok=False)
        name, n = self.sessions.open("last", self._launcher())
        return Reply(
            self.p.get(
                "session_opened",
                name="précédente" if self.lang == "fr" else "previous",
                n=n,
                s=self._plural(n),
            )
        )

    # ------------------------------------------------------------------ projets
    def _h_open_project(self, intent: Intent) -> Reply:
        name = str(intent.slot("name", ""))
        try:
            label, _path = self.projects.open(name, self._launcher())
        except RuntimeError as exc:
            if "introuvable" in str(exc):
                return Reply(self.p.get("project_not_found", name=name), ok=False)
            raise
        return Reply(self.p.get("project_opened", name=label))

    # ------------------------------------------------------------------ mémoire
    def _memory(self):
        if self.memory is None:
            raise RuntimeError("mémoire désactivée (memory.enabled = false)")
        return self.memory

    def _h_remember(self, intent: Intent) -> Reply:
        fact = str(intent.slot("fact", "")).strip()
        if not fact:
            return Reply(self.p.get("not_understood"), ok=False)
        self._memory().remember(fact)
        return Reply(self.p.get("remembered"))

    def _h_forget(self, intent: Intent) -> Reply:
        removed = self._memory().forget(str(intent.slot("fact", "")))
        if removed is None:
            return Reply(self.p.get("forget_none"), ok=False)
        return Reply(self.p.get("forgotten", fact=removed.sentence()))

    def _h_forget_all(self, intent: Intent) -> Reply:
        self._memory().forget_all()
        if self.brain is not None and hasattr(self.brain, "forget"):
            self.brain.forget()
        return Reply(self.p.get("forgot_all"))

    def _h_recall(self, intent: Intent) -> Reply:
        facts = self._memory().facts()
        if not facts:
            return Reply(self.p.get("recall_none"))
        listed = "; ".join(f.sentence() for f in facts[-8:])
        return Reply(self.p.get("recall_intro") + listed + ".")

    # ------------------------------------------------------------------ tâches
    def _background_task(self, name: str):
        q = canonical(name)
        if q in self.background:
            return self.background[q]
        for key, task in self.background.items():
            if q in key or key in q:
                return task
        return None

    def _h_task_run(self, intent: Intent) -> Reply:
        name = str(intent.slot("name", ""))
        spec = self._background_task(name)
        if spec is None:
            return Reply(self.p.get("task_not_found", name=name), ok=False)
        task = self.tasks.run(
            spec.name, spec.exec, cwd=spec.cwd or None, announce=spec.announce, notify=spec.notify
        )
        return Reply(self.p.get("task_started", name=spec.name), data={"task_id": task.id})

    def _h_task_watch(self, intent: Intent) -> Reply:
        name = str(intent.slot("name", ""))
        spec = self._background_task(name)
        if spec is not None:
            task = self.tasks.run(
                spec.name,
                spec.exec,
                cwd=spec.cwd or None,
                announce=spec.announce,
                notify=spec.notify,
            )
            return Reply(self.p.get("task_started", name=spec.name), data={"task_id": task.id})
        task = self.tasks.watch(name)
        return Reply(self.p.get("task_watch_started", name=name), data={"task_id": task.id})

    def _h_task_status(self, intent: Intent) -> Reply:
        name = intent.slot("name")
        if name:
            task = self.tasks.find(str(name))
            if task is None:
                return Reply(self.p.get("task_not_found", name=str(name)), ok=False)
            if task.status == "running":
                return Reply(
                    self.p.get(
                        "task_status_running",
                        items=self.p.get(
                            "task_status_one",
                            name=task.name,
                            duration=human_duration(task.duration_s, self.lang),
                        ),
                    )
                )
            return Reply(
                self.p.get(
                    "task_last",
                    name=task.name,
                    status=self.p.get(f"status_{task.status}"),
                ).strip()
            )
        running = self.tasks.running()
        text = ""
        if running:
            items = ", ".join(
                self.p.get(
                    "task_status_one", name=t.name, duration=human_duration(t.duration_s, self.lang)
                )
                for t in running
            )
            text = self.p.get("task_status_running", items=items)
        else:
            text = self.p.get("task_none_running")
        last = self.tasks.last_finished()
        if last is not None:
            text += self.p.get(
                "task_last", name=last.name, status=self.p.get(f"status_{last.status}")
            )
        return Reply(text)

    def _h_task_cancel(self, intent: Intent) -> Reply:
        name = str(intent.slot("name", ""))
        task = self.tasks.cancel(name)
        if task is None:
            return Reply(self.p.get("task_not_found", name=name), ok=False)
        return Reply(self.p.get("task_cancelled", name=task.name))

    def _h_task_result(self, intent: Intent) -> Reply:
        agent = intent.slot("agent") or intent.slot("agent2")
        name = intent.slot("name")
        task = (
            self.tasks.find(str(name))
            if name
            else self.tasks.last_finished("agent" if agent else None)
        )
        if task is None or task.status == "running":
            return Reply(self.p.get("task_result_none"), ok=False)
        summary = task.summary(300) or ("(aucune sortie)" if self.lang == "fr" else "(no output)")
        return Reply(
            self.p.get("task_result", name=task.name, summary=summary),
            data={"notify": True, "answer": task.summary(2000)},
        )

    def format_task_event(self, task: Task) -> str:
        """Phrase d'annonce à la fin d'une tâche (utilisée par l'assistant)."""
        duration = human_duration(task.duration_s, self.lang)
        if task.kind == "agent":
            label = task.meta.get("label", "l'agent")
            summary = task.summary(300) or (
                "terminé sans réponse" if self.lang == "fr" else "finished without output"
            )
            return self.p.get(
                "agent_done" if task.ok else "agent_failed", agent=label, summary=summary
            )
        if task.kind == "watch":
            return self.p.get("task_watch_done", name=task.name)
        if task.ok:
            return self.p.get("task_done", name=task.name, duration=duration)
        return self.p.get("task_failed", name=task.name, duration=duration, code=task.returncode)

    # ------------------------------------------------------------------ alimentation
    def _h_suspend(self, intent: Intent) -> Reply:
        power.suspend()
        return Reply(self.p.get("suspending"), keep_listening=False)

    def _h_shutdown(self, intent: Intent) -> Reply:
        power.poweroff()
        return Reply(self.p.get("shutting_down"), keep_listening=False)

    def _h_reboot(self, intent: Intent) -> Reply:
        power.reboot()
        return Reply(self.p.get("rebooting"), keep_listening=False)

    # ------------------------------------------------------------------ web
    def _h_open_url(self, intent: Intent) -> Reply:
        url = web.open_url(str(intent.slot("url", "")), self._launcher())
        spoken = url.removeprefix("https://").removeprefix("http://").rstrip("/")
        return Reply(self.p.get("url_opened", url=spoken))

    def _h_web_search(self, intent: Intent) -> Reply:
        query = str(intent.slot("query", ""))
        web.search(query, self.cfg.system.search_url, self._launcher())
        return Reply(self.p.get("search", query=query))

    # ------------------------------------------------------------------ commandes perso
    def _h_custom(self, intent: Intent) -> Reply:
        command = intent.command
        assert command is not None
        if command.wait:
            proc = subprocess.run(
                command.exec, shell=True, capture_output=True, text=True, timeout=120
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip()[-200:] or f"code {proc.returncode}")
        else:
            subprocess.Popen(
                command.exec,
                shell=True,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return Reply(command.reply or self.p.get("custom_done", name=command.name))

    # ------------------------------------------------------------------ IA
    def _h_ask_llm(self, intent: Intent) -> Reply:
        if self.brain is None:
            return Reply(self.p.get("llm_disabled"), ok=False)
        question = intent.text or str(intent.slot("prompt", ""))
        if self.cfg.llm.stream and hasattr(self.brain, "converse_stream"):
            return Reply(
                "",
                stream=self.brain.converse_stream(question, self.lang),
                data={"question": question},
            )
        try:
            answer = self.brain.converse(question, self.lang)
        except Exception as exc:  # noqa: BLE001
            return Reply(self.p.get("llm_failed", reason=str(exc)), ok=False)
        return Reply(answer or self.p.get("not_understood"), data={"answer": answer})

    def _h_ask_agent(self, intent: Intent) -> Reply:
        if self.agents is None or not getattr(self.agents, "enabled", False):
            return Reply(self.p.get("agents_disabled"), ok=False)
        name = str(intent.slot("agent") or intent.slot("agent2") or "")
        prompt = str(intent.slot("prompt", "")).strip()
        if not prompt:
            return Reply(self.p.get("not_understood"), ok=False)
        task = self.agents.run(name, prompt)
        label = task.meta.get("label", name or "l'agent")
        return Reply(self.p.get("agent_started", agent=label), data={"task_id": task.id})
