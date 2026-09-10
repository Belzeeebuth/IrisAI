"""Routeur : intention → action → réponse.

Chaque intention a un gestionnaire ``_h_<nom>``. Les erreurs sont capturées et transformées
en réponse parlée ; chaque exécution est tracée dans le journal.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from iris.actions import audio_ctl, brightness, clock, hyprland, media, notify, omarchy, power, web
from iris.actions.apps import AppResolver
from iris.config import Config
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.nlu.intents import Intent

log = logging.getLogger(__name__)


@dataclass
class Reply:
    text: str
    ok: bool = True
    keep_listening: bool = True  # garder la fenêtre d'enchaînement après la réponse
    data: dict[str, Any] = field(default_factory=dict)
    control: str | None = None  # "stop" | "pause" | "resume" — instructions pour l'assistant

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
    ) -> None:
        self.cfg = cfg
        self.p = phrases
        self.journal = journal
        self.apps = apps or AppResolver(
            cfg.apps, cfg.system.terminal, cfg.system.browser, cfg.system.editor
        )
        self.agent = agent
        self.lang = phrases.lang

    # ------------------------------------------------------------------ API
    def confirmation_question(self, intent: Intent) -> str | None:
        if not intent.requires_confirmation:
            return None
        if intent.name == "custom" and intent.command:
            return self.p.get("confirm_custom", name=intent.command.name)
        return (
            self.p.get(f"confirm_{intent.name}")
            if intent.name in ("close_all", "suspend", "shutdown", "reboot")
            else self.p.get("confirm_custom", name=intent.name)
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
        if self.journal is not None:
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

    # ------------------------------------------------------------------ fenêtres / workspaces
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

    # ------------------------------------------------------------------ agents
    def _h_ask_agent(self, intent: Intent) -> Reply:
        if self.agent is None or not getattr(self.agent, "enabled", False):
            return Reply(self.p.get("agent_disabled"), ok=False)
        if not self.agent.available():
            return Reply(self.p.get("agent_unavailable"), ok=False)
        prompt = str(intent.slot("prompt", ""))
        try:
            answer = self.agent.ask(prompt)
        except Exception as exc:  # noqa: BLE001
            return Reply(self.p.get("agent_failed", reason=str(exc)), ok=False)
        return Reply(
            self.p.get("agent_answer", answer=answer), data={"notify": True, "answer": answer}
        )
