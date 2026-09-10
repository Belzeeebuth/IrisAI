"""Machine à états d'Iris.

    IDLE ──(mot d'activation)──▶ ACTIVE ──(commande)──▶ exécution ──▶ ACTIVE (enchaînement) ou IDLE
      │                            │
      │ (« Iris, ferme tout »)     │ (intention critique)
      └────────────────────────────┴──▶ CONFIRMING ──(oui/non/délai)──▶ IDLE
    PAUSED : ignore tout sauf « Hey Iris, reprends »

La boucle vocale (``run_forever``) enchaîne capture → VAD → STT → ``on_utterance``.
Le mode texte (``handle_text``) court-circuite l'audio ; les deux partagent la même logique.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import StrEnum

from iris.audio.playback import play_pcm
from iris.audio.sounds import ack_beep
from iris.config import Config
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.core.router import Reply, Router
from iris.nlu.intents import Intent, IntentParser, parse_yes_no

log = logging.getLogger(__name__)


class State(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    CONFIRMING = "confirming"
    PAUSED = "paused"


class Assistant:
    def __init__(
        self,
        cfg: Config,
        parser: IntentParser,
        router: Router,
        phrases: Phrasebook,
        tts,
        stt=None,
        wake=None,
        journal: Journal | None = None,
        clock: Callable[[], float] = time.monotonic,
        on_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.parser = parser
        self.router = router
        self.p = phrases
        self.tts = tts
        self.stt = stt
        self.wake = wake
        self.journal = journal
        self.clock = clock
        self.on_event = on_event or (lambda kind, text: None)

        self.state = State.IDLE
        self._deadline = 0.0  # fin de la fenêtre ACTIVE / CONFIRMING / PAUSED
        self._active_kind = "wake"  # "wake" (après « Hey Iris ») | "follow_up" (après une commande)
        self._pending: Intent | None = None
        self._ignore_before = 0.0  # audio capté avant cet instant = notre propre voix
        self.running = False

    # ================================================================== parole
    def speak(self, text: str) -> None:
        if not text:
            return
        self.on_event("reply", text)
        try:
            self.tts.speak(text)
        except Exception as exc:  # noqa: BLE001
            log.error("TTS en échec : %s", exc)
        self._ignore_before = self.clock() + 0.3

    def _ack(self) -> None:
        if self.cfg.assistant.ack_sound and getattr(self.tts, "name", "") not in (
            "console",
            "none",
        ):
            play_pcm(ack_beep(), 22050, player=self.cfg.audio.player)
        else:
            self.speak(self.p.get("ack"))
        self._ignore_before = self.clock() + 0.2

    # ================================================================== logique commune
    def handle_text(self, text: str) -> Reply | None:
        """Mode texte : la phrase est une commande (avec ou sans mot d'activation)."""
        text = text.strip()
        if not text:
            return None
        if self.state == State.CONFIRMING:
            return self._handle_confirmation(text)
        if self.wake is not None:
            match = self.wake.match(text)
            if match is not None:
                text = match.remainder
                if not text:
                    self._enter_active()
                    return Reply(self.p.get("ack"))
        return self.process_command(text)

    def process_command(self, text: str) -> Reply | None:
        intent = self.parser.parse(text)
        self.on_event("intent", intent.name if intent else "?")
        if intent is None:
            reply = Reply(self.p.get("not_understood"), ok=False)
            self.speak(reply.text)
            self._after_reply(reply)
            return reply

        question = self.router.confirmation_question(intent)
        if question:
            self._pending = intent
            self.state = State.CONFIRMING
            self._deadline = self.clock() + self.cfg.assistant.confirm_timeout_s
            self.speak(question)
            return Reply(question, data={"pending": intent.name})

        return self._execute(intent)

    def _execute(self, intent: Intent) -> Reply:
        reply = self.router.execute(intent)
        text = reply.text
        if reply.ok and reply.keep_listening and reply.control is None:
            text += self.p.get("follow_up")
        self.speak(text)
        self._apply_control(reply)
        if reply.control is None:
            self._after_reply(reply)
        return reply

    def _apply_control(self, reply: Reply) -> None:
        if reply.control == "stop":
            self._pending = None
            self.state = State.IDLE
        elif reply.control == "pause":
            minutes = int(reply.data.get("minutes", 10))
            self.state = State.PAUSED
            self._deadline = self.clock() + minutes * 60
        elif reply.control == "resume":
            self.state = State.IDLE

    def _after_reply(self, reply: Reply) -> None:
        window = self.cfg.assistant.follow_up_window_s
        if reply.keep_listening and window > 0 and self.wake is not None:
            self.state = State.ACTIVE
            self._active_kind = "follow_up"
            self._deadline = self.clock() + window
        else:
            self.state = State.IDLE

    def _enter_active(self) -> None:
        self.state = State.ACTIVE
        self._active_kind = "wake"
        self._deadline = self.clock() + self.cfg.assistant.active_window_s
        self._ack()

    def _handle_confirmation(self, text: str) -> Reply:
        answer = parse_yes_no(text)
        pending = self._pending
        if answer is True and pending is not None:
            self._pending = None
            self.state = State.IDLE
            return self._execute(pending)
        if answer is False:
            self._pending = None
            self.state = State.IDLE
            reply = Reply(self.p.get("cancelled"))
            self.speak(reply.text)
            return reply
        # réponse incompréhensible : on redemande une fois, puis on annule au délai
        question = self.router.confirmation_question(pending) if pending else None
        reply = Reply(question or self.p.get("not_understood"), ok=False)
        self.speak(reply.text)
        return reply

    # ================================================================== voix
    def on_utterance(self, text: str) -> None:
        """Reçoit chaque phrase transcrite et applique la machine à états."""
        text = text.strip()
        if not text:
            return
        self.tick()
        self.on_event("heard", text)
        log.info("Entendu [%s] : %s", self.state.value, text)

        if self.state == State.CONFIRMING:
            self._handle_confirmation(text)
            self._journal(text, wake=False, handled=True)
            return

        match = self.wake.match(text) if self.wake is not None else None

        if self.state == State.PAUSED:
            if (
                match is not None
                and self.parser.parse(match.remainder) is not None
                and self.parser.parse(match.remainder).name == "resume_listening"
            ):
                self.state = State.IDLE
                self.speak(self.p.get("resumed"))
            return

        if self.state == State.ACTIVE:
            command = match.remainder if match is not None else text
            if not command:
                self._enter_active()
                return
            if (
                match is None
                and self._active_kind == "follow_up"
                and self.parser.parse(command) is None
            ):
                # fenêtre d'enchaînement : une phrase inconnue est sûrement du bruit ambiant → silence
                self.state = State.IDLE
                self._journal(text, wake=False, handled=False)
                return
            self.process_command(command)
            self._journal(text, wake=match is not None, handled=True)
            return

        # IDLE
        if self.wake is None:
            self.process_command(text)
            self._journal(text, wake=False, handled=True)
            return
        if match is None:
            self._journal(text, wake=False, handled=False)
            return
        if not match.remainder:
            self._enter_active()
        else:
            self.process_command(match.remainder)
        self._journal(text, wake=True, handled=True)

    def on_wake_detected(self) -> None:
        """Appelé par un détecteur audio (openWakeWord) : passe en écoute active."""
        if self.state in (State.IDLE, State.ACTIVE):
            self._enter_active()
        elif self.state == State.PAUSED:
            self.state = State.IDLE
            self.speak(self.p.get("resumed"))

    def tick(self) -> None:
        """Applique les délais d'expiration (à appeler régulièrement)."""
        now = self.clock()
        if self.state == State.ACTIVE and now > self._deadline:
            self.state = State.IDLE
            self.on_event("state", "idle")
        elif self.state == State.CONFIRMING and now > self._deadline:
            self._pending = None
            self.state = State.IDLE
            self.speak(self.p.get("confirm_timeout"))
        elif self.state == State.PAUSED and now > self._deadline:
            self.state = State.IDLE

    def _journal(self, text: str, wake: bool, handled: bool) -> None:
        if self.journal is not None:
            self.journal.log_utterance(text, wake, handled)

    # ================================================================== boucle principale
    def run_forever(self, capture, segmenter, audio_wake=None) -> None:
        """capture : ``AudioCapture`` démarré ; segmenter : ``VadSegmenter`` ; audio_wake : openWakeWord (optionnel)."""
        if self.stt is None:
            raise RuntimeError("Aucun moteur STT configuré")
        self.running = True
        sample_rate = self.cfg.audio.sample_rate
        log.info("Iris écoute (mot d'activation : %s)", self.cfg.wake.backend)
        try:
            for ts, frame in capture.frames():
                if not self.running:
                    break
                self.tick()
                if ts < self._ignore_before:
                    segmenter.reset()
                    continue
                if audio_wake is not None and self.state in (State.IDLE, State.PAUSED):
                    if audio_wake.process(frame):
                        segmenter.reset()
                        self.on_wake_detected()
                    continue
                utterance = segmenter.push(frame)
                if utterance is None:
                    continue
                started = time.monotonic()
                try:
                    text = self.stt.transcribe(utterance, sample_rate, self.cfg.stt_language)
                except Exception as exc:  # noqa: BLE001
                    log.error("Transcription impossible : %s", exc)
                    continue
                log.debug(
                    "STT %.2fs (%.1fs d'audio) : %r",
                    time.monotonic() - started,
                    len(utterance) / sample_rate,
                    text,
                )
                if text:
                    self.on_utterance(text)
        finally:
            self.running = False

    def stop(self) -> None:
        self.running = False
