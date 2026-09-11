"""Machine à états d'Iris.

    IDLE ──(mot d'activation)──▶ ACTIVE ──(commande)──▶ exécution ──▶ ACTIVE (enchaînement) ou IDLE
      │                            │
      │ (« Iris, ferme tout »)     │ (intention critique)
      └────────────────────────────┴──▶ CONFIRMING ──(oui/non/délai)──▶ IDLE
    PAUSED    : ignore tout sauf « Hey Iris, reprends »
    DICTATING : chaque phrase est tapée dans la fenêtre active jusqu'à « fin de dictée »

Phrase inconnue : découpage en plusieurs commandes (« … et … »), puis repli sur le LLM
(``brain.decide`` : action Iris, réponse parlée, ou silence). La langue de réponse suit la
langue détectée quand ``assistant.language = "auto"``.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from enum import StrEnum

from iris.actions import hyprland, notify
from iris.audio.playback import play_pcm
from iris.audio.sounds import ack_beep
from iris.config import Config
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook
from iris.core.router import Reply, Router
from iris.nlu.intents import CONFIRM_INTENTS as _CONFIRM
from iris.nlu.intents import Intent, IntentParser, parse_yes_no
from iris.nlu.split import split_commands

log = logging.getLogger(__name__)

# Intentions « fourre-tout » dont l'objet est libre : un mot final ambigu leur appartient rarement.
_GENERIC_INTENTS = {
    "open_app",
    "close_app",
    "web_search",
    "say",
    "type_text",
    "type_and_enter",
    "ask_llm",
}
# Intentions dont la consigne est un texte libre où un nom final compte plus qu'une activation.
_PAYLOAD_INTENTS = {
    "automation_create",
    "reminder_create",
    "open_project",
    "ask_agent",
    "remember",
    "alias_learn",
}


class State(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    CONFIRMING = "confirming"
    PAUSED = "paused"
    DICTATING = "dictating"


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
        brain=None,
        status=None,
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
        self.brain = brain
        self.status = status

        self.state = State.IDLE
        self._deadline = 0.0  # fin de la fenêtre ACTIVE / CONFIRMING / PAUSED
        self._active_kind = "wake"  # "wake" (après « Hey Iris ») | "follow_up" (après une commande)
        self._pending: Intent | None = None
        self._ignore_before = 0.0  # audio capté avant cet instant = notre propre voix
        self._wake_requested = False  # push-to-talk (signal) à traiter dans la boucle
        self._pause_requested = False
        self._dictation_enter = False
        self._pending_events: list = []  # fins de tâches à annoncer quand l'état le permet
        self._last_snapshot = 0.0
        self._snapshots_enabled = False
        self._suggestion_key: str | None = None
        self._last_auto_check = 0.0
        self._last_routine_check = 0.0
        self._quiet_active = False
        self._base_verbosity = phrases.verbosity
        self.running = False
        if hasattr(router, "tts") and getattr(router, "tts", None) is None:
            router.tts = tts
        self._tts_takes_language = "language" in inspect.signature(tts.speak).parameters

    # ================================================================== état / statut
    def _set_state(self, state: State, detail: str = "") -> None:
        self.state = state
        self.on_event("state", state.value)
        if self.status is not None:
            self.status.write(state.value, detail)

    def _status(self, transient: str, detail: str = "") -> None:
        if self.status is not None:
            self.status.write(transient, detail)

    def _restore_status(self) -> None:
        if self.status is not None:
            self.status.write(self.state.value)

    # ================================================================== parole
    def speak(self, text: str) -> None:
        if not text:
            return
        self.on_event("reply", text)
        self._status("speaking", text[:80])
        try:
            if self._tts_takes_language:
                self.tts.speak(text, language=self.p.lang)
            else:
                self.tts.speak(text)
        except Exception as exc:  # noqa: BLE001
            log.error("TTS en échec : %s", exc)
        finally:
            self._restore_status()
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

    # ================================================================== langue
    def set_language(self, detected: str | None) -> None:
        """En mode « auto », répond dans la langue détectée par le STT (fr/en)."""
        if self.cfg.assistant.language != "auto":
            return
        if detected in ("fr", "en") and detected != self.p.lang:
            self.p.lang = detected
            log.debug("Langue de réponse : %s", detected)

    # ================================================================== logique commune
    def handle_text(self, text: str) -> Reply | None:
        """Mode texte : la phrase est une commande (avec ou sans mot d'activation)."""
        text = text.strip()
        if not text:
            return None
        if self.state == State.CONFIRMING:
            return self._handle_confirmation(text)
        if self.state == State.DICTATING:
            return self._handle_dictation(text)
        addressed = False
        if self.wake is not None:
            match = self.wake.match(text)
            if match is not None:
                remainder = self._command_from_match(text, match)
                if not remainder or self._garbled_wake(match, remainder):
                    self._enter_active()
                    return Reply(self.p.get("ack"))
                text, addressed = remainder, True
        return self.process_command(text, addressed=addressed)

    def _command_from_match(self, text: str, match) -> str:
        """Mot d'activation en fin de phrase : « ouvre le projet iris » parle du projet nommé iris.

        On préfère la phrase entière quand le reste n'est pas une commande, ou quand le reste ne donne
        qu'une intention générique (ouvrir/fermer une application, recherche…) alors que la phrase
        entière donne une intention précise (projet, session…).
        """
        if match.position != "suffix" or not match.remainder:
            return match.remainder
        rest = self.parser.parse(match.remainder)
        full = self.parser.parse(text)
        if full is None:
            return match.remainder
        if rest is None:
            return text
        if rest.name in _GENERIC_INTENTS and full.name not in _GENERIC_INTENTS:
            return text
        if full.name in _PAYLOAD_INTENTS:
            return text  # « chaque matin ouvre le projet iris » : le mot final fait partie de la consigne
        return match.remainder

    def _garbled_wake(self, match, command: str) -> bool:
        """« Heille Iris » : Whisper a écorché le « hey », ce n'est pas une commande.

        Un mot unique placé AVANT le nom d'activation et qui ne correspond à aucune
        intention est presque toujours un « hey » mal transcrit — « heille », « heide »,
        « hurt », « hel »… La liste des mots parasites ne les rattrape pas, elle exige
        une correspondance exacte. Mieux vaut s'activer, et biper pour le dire, que
        d'exécuter du bruit avant de se taire.
        """
        return (
            match is not None
            and match.position == "suffix"
            and len(command.split()) == 1
            and self.parser.parse(command) is None
        )

    def process_command(self, text: str, *, addressed: bool = False) -> Reply | None:
        """addressed : la phrase portait le mot d'activation, elle nous était adressée."""
        parts = split_commands(text, self._intent_name_of)
        if len(parts) > 1:
            reply = None
            for part in parts:
                reply = self._process_single(part, addressed)
                if self.state == State.CONFIRMING:
                    break  # une confirmation en attente suspend la suite
            return reply
        return self._process_single(text, addressed)

    def _intent_name_of(self, text: str) -> str | None:
        intent = self.parser.parse(text)
        return intent.name if intent else None

    def _process_single(self, text: str, addressed: bool = False) -> Reply | None:
        intent = self.parser.parse(text)
        self.on_event("intent", intent.name if intent else "?")
        if intent is None:
            return self._fallback(text, addressed)
        return self._run_intent(intent)

    def _run_intent(self, intent: Intent) -> Reply:
        question = self.router.confirmation_question(intent)
        if question:
            self._pending = intent
            self._suggestion_key = None  # une vraie confirmation, pas une suggestion
            self._set_state(State.CONFIRMING, intent.name)
            self._deadline = self.clock() + self.cfg.assistant.confirm_timeout_s
            self.speak(question)
            return Reply(question, data={"pending": intent.name})
        return self._execute(intent)

    def _fallback(self, text: str, addressed: bool = False) -> Reply | None:
        """Phrase non reconnue : LLM si disponible, sinon « je n'ai pas compris »."""
        if self.brain is not None and self.cfg.llm.fallback_nlu:
            self._status("thinking", text[:80])
            failure = None
            try:
                decision = self.brain.decide(text, self.p.lang)
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM indisponible : %s", exc)
                decision, failure = None, exc
            finally:
                self._restore_status()
            if failure is not None:
                # Le modèle n'a pas répondu : le dire, plutôt que laisser croire
                # qu'on n'a pas compris la phrase.
                reply = Reply(self.p.get("llm_unreachable"), ok=False)
                self.speak(reply.text)
                self._after_reply(reply)
                return reply
            if decision is not None:
                if decision.kind == "action":
                    intent = self.router.intent_from_decision(decision)
                    if intent is None:
                        reply = Reply(self.p.get("llm_unknown_action"), ok=False)
                    else:
                        intent.text = text
                        return self._run_intent(intent)
                elif decision.kind == "reply" and decision.reply:
                    reply = Reply(decision.reply, data={"llm": True})
                    if self.journal is not None:
                        self.journal.log_action("ask_llm", {}, text, True, decision.reply[:200])
                elif addressed:
                    # Le modèle préfère se taire, mais on nous a appelée par notre nom :
                    # un bip dit « j'ai entendu, redis-moi », là où le silence laisse
                    # croire que le micro est mort.
                    self._enter_active()
                    return None
                else:
                    self._set_state(State.IDLE)
                    return None
                self.speak(reply.text)
                self._after_reply(reply)
                return reply
        reply = Reply(self.p.get("not_understood"), ok=False)
        self.speak(reply.text)
        self._after_reply(reply)
        return reply

    def _execute(self, intent: Intent) -> Reply:
        reply = self.router.execute(intent)
        if reply.stream is not None:
            return self._execute_stream(intent, reply)
        text = reply.text
        if reply.ok and reply.keep_listening and reply.control is None:
            text += self.p.get("follow_up")
        self.speak(text)
        self._apply_control(reply)
        if reply.control is None and not self._maybe_follow_up(intent, reply):
            self._after_reply(reply)
        return reply

    def _execute_stream(self, intent: Intent, reply: Reply) -> Reply:
        """Réponse LLM en streaming : chaque phrase est prononcée dès qu'elle est complète."""
        spoken: list[str] = []
        self._status("thinking", intent.text[:80])
        try:
            for sentence in reply.stream:
                if sentence:
                    spoken.append(sentence)
                    self.speak(sentence)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM en streaming : %s", exc)
            if not spoken:
                self.speak(self.p.get("llm_failed", reason=str(exc)))
                reply.ok = False
        finally:
            self._restore_status()
        reply.text = " ".join(spoken)
        if not spoken and reply.ok:
            self.speak(self.p.get("not_understood"))
            reply.ok = False
        if self.journal is not None:
            self.journal.log_action(
                intent.name, intent.slots, intent.text, reply.ok, reply.text[:500]
            )
        self._after_reply(reply)
        return reply

    def _apply_control(self, reply: Reply) -> None:
        if reply.control == "stop":
            self._pending = None
            self._set_state(State.IDLE)
        elif reply.control == "pause":
            minutes = int(reply.data.get("minutes", 10))
            self._set_state(State.PAUSED, f"{minutes} min")
            self._deadline = self.clock() + minutes * 60
        elif reply.control == "resume":
            self._set_state(State.IDLE)
        elif reply.control == "dictate":
            self._dictation_enter = bool(reply.data.get("enter"))
            self._set_state(State.DICTATING, "terminal" if self._dictation_enter else "")
        elif reply.control == "dictate_stop":
            self._set_state(State.IDLE)
        elif reply.control == "wake_reload":
            self._reload_wake()
            self._set_state(State.IDLE)
        elif reply.control == "language":
            self._set_state(State.IDLE)

    def _after_reply(self, reply: Reply) -> None:
        window = self.cfg.assistant.follow_up_window_s
        if reply.keep_listening and window > 0 and self.wake is not None:
            self._active_kind = "follow_up"
            self._deadline = self.clock() + window
            self._set_state(State.ACTIVE)
        else:
            self._set_state(State.IDLE)

    def _enter_active(self) -> None:
        self._active_kind = "wake"
        self._deadline = self.clock() + self.cfg.assistant.active_window_s
        self._set_state(State.ACTIVE)
        self._ack()

    def _handle_confirmation(self, text: str) -> Reply:
        answer = parse_yes_no(text)
        pending = self._pending
        if answer is True and pending is not None:
            self._pending = None
            self._suggestion_key = None
            self._set_state(State.IDLE)
            return self._execute(pending)
        if answer is False:
            self._pending = None
            self._set_state(State.IDLE)
            if self._suggestion_key:
                key, self._suggestion_key = self._suggestion_key, None
                if getattr(self.router, "prefs", None) is not None:
                    self.router.prefs.dismiss(key)
                reply = Reply(self.p.get("suggestion_declined"))
            else:
                reply = Reply(self.p.get("cancelled"))
            self.speak(reply.text)
            return reply
        # réponse incompréhensible : on redemande une fois, puis on annule au délai
        question = self.router.confirmation_question(pending) if pending else None
        reply = Reply(question or self.p.get("not_understood"), ok=False)
        self.speak(reply.text)
        return reply

    def _handle_dictation(self, text: str) -> Reply | None:
        """En dictée : « fin de dictée » arrête, tout le reste est tapé tel quel."""
        candidate = text
        if self.wake is not None:
            match = self.wake.match(text)
            if match is not None and match.remainder:
                candidate = match.remainder
        intent = self.parser.parse(candidate)
        if intent is not None and intent.name in ("dictation_stop", "stop"):
            reply = self.router.execute(Intent("dictation_stop", text=text))
            self.speak(reply.text)
            self._apply_control(reply)
            return reply
        name = "type_and_enter" if self._dictation_enter else "type_text"
        reply = self.router.execute(Intent(name, {"text": text}, text=text))
        if not reply.ok:
            self.speak(reply.text)
        return reply

    # ================================================================== voix
    def on_utterance(self, text: str, language: str | None = None) -> None:
        """Reçoit chaque phrase transcrite et applique la machine à états."""
        text = text.strip()
        if not text:
            return
        self.tick()
        self.set_language(language)
        self.on_event("heard", text)
        log.info("Entendu [%s] : %s", self.state.value, text)

        if self.state == State.CONFIRMING:
            self._handle_confirmation(text)
            self._journal(text, wake=False, handled=True)
            return

        if self.state == State.DICTATING:
            self._handle_dictation(text)
            self._journal(text, wake=False, handled=True)
            return

        match = self.wake.match(text) if self.wake is not None else None

        if self.state == State.PAUSED:
            if match is not None and self._intent_name_of(match.remainder) == "resume_listening":
                self._set_state(State.IDLE)
                self.speak(self.p.get("resumed"))
            return

        if self.state == State.ACTIVE:
            command = self._command_from_match(text, match) if match is not None else text
            if not command or self._garbled_wake(match, command):
                self._enter_active()
                return
            if (
                match is None
                and self._active_kind == "follow_up"
                and self.parser.parse(command) is None
            ):
                # fenêtre d'enchaînement : une phrase inconnue est sûrement du bruit ambiant → silence
                self._set_state(State.IDLE)
                self._journal(text, wake=False, handled=False)
                return
            self.process_command(command, addressed=match is not None)
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
        command = self._command_from_match(text, match)
        if not command or self._garbled_wake(match, command):
            self._enter_active()
        else:
            self.process_command(command, addressed=True)
        self._journal(text, wake=True, handled=True)

    def on_wake_detected(self) -> None:
        """Détecteur audio (openWakeWord) ou push-to-talk : passe en écoute active."""
        if self.state in (State.IDLE, State.ACTIVE):
            self._enter_active()
        elif self.state == State.PAUSED:
            self._set_state(State.IDLE)
            self.speak(self.p.get("resumed"))

    def request_wake(self) -> None:
        """Appelable depuis un gestionnaire de signal : traité au prochain tour de boucle."""
        self._wake_requested = True

    def request_toggle_pause(self) -> None:
        self._pause_requested = True

    def tick(self) -> None:
        """Applique les délais d'expiration et les demandes externes (à appeler régulièrement)."""
        if self._wake_requested:
            self._wake_requested = False
            self.on_wake_detected()
        if self._pause_requested:
            self._pause_requested = False
            if self.state == State.PAUSED:
                self._set_state(State.IDLE)
                self.speak(self.p.get("resumed"))
            else:
                reply = self.router.execute(
                    Intent("pause_listening", {"minutes": 30}, text="signal")
                )
                self.speak(reply.text)
                self._apply_control(reply)
        now = self.clock()
        if self.state == State.ACTIVE and now > self._deadline:
            self._set_state(State.IDLE)
        elif self.state == State.CONFIRMING and now > self._deadline:
            self._pending = None
            self._suggestion_key = (
                None  # une suggestion sans réponse sera reproposée après le délai
            )
            self._set_state(State.IDLE)
            self.speak(self.p.get("confirm_timeout"))
        elif self.state == State.PAUSED and now > self._deadline:
            self._set_state(State.IDLE)
        self._announce_tasks()
        self._maybe_snapshot()
        self._apply_quiet_hours()
        self._check_automations()
        self._maybe_suggest_routine()

    # ================================================================== phase 4 : proactivité
    def quiet_now(self) -> bool:
        spec = (self.cfg.assistant.quiet_hours or "").strip()
        if not spec or "-" not in spec:
            return False
        try:
            start_s, end_s = spec.split("-", 1)
            sh, sm = (int(x) for x in start_s.strip().split(":"))
            eh, em = (int(x) for x in end_s.strip().split(":"))
        except ValueError:
            return False
        now = time.localtime()
        minutes = now.tm_hour * 60 + now.tm_min
        start, end = sh * 60 + sm, eh * 60 + em
        return start <= minutes < end if start <= end else minutes >= start or minutes < end

    def _apply_quiet_hours(self) -> None:
        quiet = self.quiet_now()
        if quiet and not self._quiet_active:
            self._quiet_active = True
            self._base_verbosity = self.p.verbosity
            self.p.verbosity = "concise"
        elif not quiet and self._quiet_active:
            self._quiet_active = False
            self.p.verbosity = self._base_verbosity

    def _suggestions_allowed(self) -> bool:
        return (
            self.cfg.habits.enabled
            and getattr(self.router, "habits", None) is not None
            and getattr(self.router, "prefs", None) is not None
            and not self.quiet_now()
        )

    def _maybe_follow_up(self, intent: Intent, reply: Reply) -> bool:
        """Après une action : « Veux-tu aussi … ? » si elle est presque toujours suivie d'une autre."""
        if not (self._suggestions_allowed() and self.cfg.habits.suggest_follow_ups and reply.ok):
            return False
        if intent.text.startswith(("automation:", "suggestion", "routine")):
            return False
        try:
            follow = self.router.habits.follow_up_for(intent.name, intent.slots)
        except Exception as exc:  # noqa: BLE001
            log.debug("habitudes indisponibles : %s", exc)
            return False
        if follow is None:
            return False
        key = f"follow:{follow.after}>{follow.key}"
        prefs = self.router.prefs
        if prefs.is_dismissed(key) or not prefs.cooldown_ok(key, self.cfg.habits.cooldown_hours):
            return False
        scheduler = getattr(self.router, "scheduler", None)
        if scheduler is not None and scheduler.exists(follow.intent, follow.slots):
            return False
        from iris.core.habits import describe

        prefs.touch(key)
        self._pending = Intent(
            follow.intent,
            dict(follow.slots),
            text="suggestion",
            requires_confirmation=follow.intent in _CONFIRM,
        )
        self._suggestion_key = key
        self._set_state(State.CONFIRMING, "suggestion")
        self._deadline = self.clock() + self.cfg.assistant.confirm_timeout_s
        self.speak(
            self.p.get(
                "follow_up_question", action=describe(follow.intent, follow.slots, self.p.lang)
            )
        )
        return True

    def _maybe_suggest_routine(self) -> None:
        """Dans un moment calme : « Tu fais souvent X vers 9 h, je m'en occupe automatiquement ? »"""
        if (
            self.state != State.IDLE
            or not self._suggestions_allowed()
            or not self.cfg.habits.suggest_routines
        ):
            return
        if self.clock() - self._last_routine_check < 600:
            return
        self._last_routine_check = self.clock()
        prefs = self.router.prefs
        if not prefs.cooldown_ok("routine", self.cfg.habits.cooldown_hours):
            return
        try:
            routine = self.router.habits.routine_due()
        except Exception as exc:  # noqa: BLE001
            log.debug("routines indisponibles : %s", exc)
            return
        if routine is None:
            return
        key = f"routine:{routine.key}@{routine.hour}:{routine.minute:02d}"
        if prefs.is_dismissed(key) or routine.intent in _CONFIRM:
            return
        scheduler = getattr(self.router, "scheduler", None)
        if scheduler is None or scheduler.exists(routine.intent, routine.slots):
            return
        from iris.core.habits import describe
        from iris.core.scheduler import Schedule

        days = (0, 1, 2, 3, 4) if routine.weekdays_only else ()
        schedule = Schedule("weekly" if days else "daily", routine.hour, routine.minute, days)
        prefs.touch("routine")
        prefs.touch(key)
        self._pending = Intent(
            "automation_add",
            {
                "intent": routine.intent,
                "slots": routine.slots,
                "hour": routine.hour,
                "minute": routine.minute,
                "days": list(days),
            },
            text="routine",
        )
        self._suggestion_key = key
        self._set_state(State.CONFIRMING, "routine")
        self._deadline = self.clock() + self.cfg.assistant.confirm_timeout_s * 2
        t = f"{routine.hour} h {routine.minute:02d}" if routine.minute else f"{routine.hour} h"
        self.speak(
            self.p.get(
                "routine_question",
                action=describe(routine.intent, routine.slots, self.p.lang),
                time=t,
                schedule=schedule.describe(self.p.lang),
            )
        )

    def _check_automations(self) -> None:
        scheduler = getattr(self.router, "scheduler", None)
        if (
            scheduler is None
            or not self.cfg.automations.enabled
            or self.state not in (State.IDLE, State.ACTIVE)
        ):
            return
        if self.clock() - self._last_auto_check < max(5, self.cfg.automations.check_interval_s):
            return
        self._last_auto_check = self.clock()
        try:
            due = scheduler.due()
        except Exception as exc:  # noqa: BLE001
            log.debug("automatisations indisponibles : %s", exc)
            return
        for auto in due:
            log.info("Automatisation : %s (%s)", auto.name, auto.intent)
            reply = self.router.run_automation(auto)
            scheduler.mark_run(auto)
            prefix = (
                ""
                if auto.intent == "reminder_fire" or not self.cfg.automations.announce
                else self.p.get("automation_running")
            )
            if not reply.ok:
                log.warning("Automatisation %s : %s", auto.name, reply.text)
            if reply.text:
                self.speak(prefix + reply.text)
            if reply.data.get("notify") and self.cfg.system.notify:
                notify.send(
                    self.cfg.assistant.name,
                    reply.text,
                    urgency="critical" if reply.data.get("urgent") else "normal",
                )
            self.on_event("automation", auto.name)

    def _reload_wake(self) -> None:
        if self.wake is None:
            return
        try:
            from iris.wakeword.transcript import TranscriptWake

            self.wake = TranscriptWake(self.cfg.wake.phrases, self.cfg.wake.fuzzy_threshold)
        except Exception as exc:  # noqa: BLE001
            log.warning("mots d'activation non rechargés : %s", exc)

    # ================================================================== tâches en arrière-plan
    def _announce_tasks(self) -> None:
        tasks = getattr(self.router, "tasks", None)
        if tasks is not None:
            self._pending_events.extend(tasks.events())
        if not self._pending_events or self.state not in (State.IDLE, State.ACTIVE):
            return
        events, self._pending_events = self._pending_events, []
        for event in events:
            task = event.task
            text = self.router.format_task_event(task)
            self.on_event("task", text)
            if task.notify and self.cfg.system.notify:
                notify.send(
                    self.cfg.assistant.name,
                    text
                    if task.kind != "agent"
                    else f"{task.meta.get('label', 'Agent')} : {task.summary(1500)}",
                    urgency="normal" if task.ok else "critical",
                )
            if task.announce:
                self.speak(text)

    # ================================================================== reprise de session
    def _maybe_snapshot(self, force: bool = False) -> None:
        if not self._snapshots_enabled or not self.cfg.memory.enabled:
            return
        interval = max(1, self.cfg.memory.snapshot_interval_min) * 60
        if not force and self.clock() - self._last_snapshot < interval:
            return
        self._last_snapshot = self.clock()
        if not hyprland.available():
            return
        try:
            self.router.sessions.save("last")
        except Exception as exc:  # noqa: BLE001
            log.debug("instantané de session non pris : %s", exc)

    def maybe_suggest_resume(self) -> bool:
        """Au démarrage (opt-in) : propose de rouvrir la session précédente."""
        if not (
            self.cfg.assistant.resume_prompt
            and self.cfg.memory.enabled
            and self.journal is not None
        ):
            return False
        session = self.router.sessions.find("last")
        updated = self.journal.pref_updated("session.last")
        if session is None or updated is None or len(session.apps) < 2:
            return False
        if time.time() - updated < self.cfg.memory.resume_min_age_min * 60:
            return False
        apps = ", ".join(sorted({a.exec.split()[0].rsplit("/", 1)[-1] for a in session.apps}))
        self._pending = Intent("session_resume", text="startup")
        self._set_state(State.CONFIRMING, "reprise")
        self._deadline = self.clock() + self.cfg.assistant.confirm_timeout_s * 2
        self.speak(self.p.get("resume_question", apps=apps))
        return True

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
        self._set_state(State.IDLE)
        self._snapshots_enabled = True
        self._last_snapshot = self.clock()
        log.info("Iris écoute (mot d'activation : %s)", self.cfg.wake.backend)
        self.maybe_suggest_resume()
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
                self._status("thinking", "transcription")
                try:
                    text = self.stt.transcribe(utterance, sample_rate, self.cfg.stt_language)
                except Exception as exc:  # noqa: BLE001
                    log.error("Transcription impossible : %s", exc)
                    self._restore_status()
                    continue
                self._restore_status()
                log.debug(
                    "STT %.2fs (%.1fs d'audio) : %r",
                    time.monotonic() - started,
                    len(utterance) / sample_rate,
                    text,
                )
                if text:
                    self.on_utterance(text, getattr(self.stt, "last_language", None))
        finally:
            self.running = False
            self._maybe_snapshot(force=True)
            tasks = getattr(self.router, "tasks", None)
            if tasks is not None:
                tasks.shutdown()
            if self.status is not None:
                self.status.write("off")

    def stop(self) -> None:
        self.running = False
