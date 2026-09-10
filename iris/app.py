"""Assemblage des composants d'Iris à partir de la configuration."""

from __future__ import annotations

import logging
from datetime import datetime

from iris import paths
from iris.actions import devices, hyprland
from iris.actions.apps import AppResolver
from iris.actions.sessions import SessionManager
from iris.agents.claude_code import ClaudeCodeAgent
from iris.config import Config
from iris.core.assistant import Assistant
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.core.router import Router
from iris.core.status import StatusWriter
from iris.nlu.intents import IntentParser
from iris.tts.factory import build_tts

log = logging.getLogger(__name__)


def build_journal(cfg: Config, in_memory: bool = False) -> Journal:
    path = ":memory:" if in_memory else paths.db_file()
    return Journal(
        path,
        store_transcripts=cfg.privacy.store_transcripts,
        journal_actions=cfg.privacy.journal_actions,
    )


def build_wake(cfg: Config):
    """Détecteur textuel (transcript) ; None si wake.backend = none."""
    if cfg.wake.backend in ("transcript", "openwakeword"):
        from iris.wakeword.transcript import TranscriptWake

        # Même en mode openwakeword, le texte « Iris, … » reste reconnu dans la transcription.
        return TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold)
    return None


def build_brain(
    cfg: Config, journal: Journal | None, phrases_for_custom: list[str], session_names: list[str]
):
    """Cerveau LLM si activé et correctement configuré, sinon None (avec un avertissement)."""
    if not cfg.llm.enabled:
        return None
    from iris.llm import Brain, LLMError, build_client

    try:
        client = build_client(cfg.llm, cfg.privacy.allow_cloud)
    except LLMError as exc:
        log.warning("LLM désactivé : %s", exc)
        return None

    def context() -> dict[str, str]:
        ctx: dict[str, str] = {"heure": datetime.now().strftime("%A %d %B %Y, %H:%M")}
        if hyprland.available():
            try:
                win = hyprland.active_window()
                if win:
                    ctx["fenêtre active"] = (
                        f"{win.get('class', '')} — {str(win.get('title', ''))[:80]}"
                    )
                ws = hyprland.current_workspace()
                if ws is not None:
                    ctx["workspace"] = str(ws)
            except RuntimeError:
                pass
        battery = devices.battery()
        if battery is not None:
            ctx["batterie"] = f"{battery[0]} % ({battery[1]})"
        if journal is not None:
            recent = journal.recent(3)
            if recent:
                ctx["dernières actions"] = " ; ".join(
                    f"{r.intent} → {r.result[:40]}" for r in recent
                )
        return ctx

    log.info("LLM : %s (%s, api %s)", cfg.llm.provider, cfg.llm.model, client.api)
    return Brain(
        cfg,
        client,
        context_provider=context,
        custom_phrases=phrases_for_custom,
        session_names=session_names,
    )


def build_assistant(
    cfg: Config,
    *,
    text_mode: bool = False,
    speak: bool = True,
    with_stt: bool = False,
    with_status: bool = False,
    on_event=None,
) -> Assistant:
    phrases = Phrasebook(cfg.reply_language, cfg.assistant.verbosity, cfg.assistant.tone)
    journal = build_journal(cfg)
    apps = AppResolver(cfg.apps, cfg.system.terminal, cfg.system.browser, cfg.system.editor)
    sessions = SessionManager(cfg.sessions, journal, apps)
    custom_phrases = [p for c in cfg.commands for p in c.phrases]
    brain = build_brain(cfg, journal, custom_phrases, sessions.names())
    agent = ClaudeCodeAgent(cfg.agents)
    router = Router(cfg, phrases, journal, apps=apps, agent=agent, brain=brain, sessions=sessions)
    parser = IntentParser(cfg.commands, session_phrases={s.name: s.phrases for s in cfg.sessions})
    tts = build_tts(cfg, prefer_console=not speak)
    stt = None
    if with_stt:
        from iris.stt.factory import build_stt

        stt = build_stt(cfg)
    wake = None if text_mode and cfg.wake.backend == "none" else build_wake(cfg)
    status = (
        StatusWriter(cfg.system.status_file or None, cfg.system.waybar_signal)
        if with_status
        else None
    )
    return Assistant(
        cfg,
        parser,
        router,
        phrases,
        tts,
        stt=stt,
        wake=wake,
        journal=journal,
        on_event=on_event,
        brain=brain,
        status=status,
    )
