"""Assemblage des composants d'Iris à partir de la configuration."""

from __future__ import annotations

import logging

from iris import paths
from iris.agents.claude_code import ClaudeCodeAgent
from iris.config import Config
from iris.core.assistant import Assistant
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.core.router import Router
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
    """Détecteur textuel (transcript) ; None si wake.backend = none ou openwakeword (audio)."""
    if cfg.wake.backend in ("transcript", "openwakeword"):
        from iris.wakeword.transcript import TranscriptWake

        # Même en mode openwakeword, le texte « Iris, … » reste reconnu dans la transcription.
        return TranscriptWake(cfg.wake.phrases, cfg.wake.fuzzy_threshold)
    return None


def build_assistant(
    cfg: Config,
    *,
    text_mode: bool = False,
    speak: bool = True,
    with_stt: bool = False,
    on_event=None,
) -> Assistant:
    phrases = Phrasebook(cfg.assistant.language, cfg.assistant.verbosity, cfg.assistant.tone)
    journal = build_journal(cfg)
    agent = ClaudeCodeAgent(cfg.agents)
    router = Router(cfg, phrases, journal, agent=agent)
    parser = IntentParser(cfg.commands)
    tts = build_tts(cfg, prefer_console=not speak)
    stt = None
    if with_stt:
        from iris.stt.factory import build_stt

        stt = build_stt(cfg)
    wake = None if text_mode and cfg.wake.backend == "none" else build_wake(cfg)
    return Assistant(
        cfg, parser, router, phrases, tts, stt=stt, wake=wake, journal=journal, on_event=on_event
    )
