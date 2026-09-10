"""Le « cerveau » d'Iris : quand les règles ne suffisent pas, un LLM décide.

Deux usages :
- ``decide(text)`` : phrase non reconnue → le modèle renvoie soit une action Iris (nom d'intention +
  paramètres, exécutée par le routeur comme une commande normale, confirmations comprises), soit
  une réponse à prononcer, soit « rien » (bruit ambiant) ;
- ``converse(text)`` : question ouverte → réponse courte, parlable.

Le prompt système décrit la personnalité (ton, verbosité, profil libre), les capacités, et le
contexte du moment (heure, fenêtre active, workspace, dernières actions). Aucune donnée audio
n'est envoyée : uniquement du texte.
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from iris.config import Config
from iris.llm.client import LLMClient, LLMError

log = logging.getLogger(__name__)

# Intentions exposées au LLM : nom → (description, paramètres)
CAPABILITIES: dict[str, tuple[str, str]] = {
    "open_app": ("ouvrir une application ou une web-app", "app"),
    "close_app": ("fermer une application", "app"),
    "close_all": ("fermer toutes les fenêtres (confirmation demandée)", ""),
    "window_close": ("fermer la fenêtre active", ""),
    "window_fullscreen": ("basculer le plein écran", ""),
    "window_floating": ("basculer le mode flottant", ""),
    "window_move_workspace": ("envoyer la fenêtre active sur un workspace", "n"),
    "workspace_switch": ("aller sur un workspace", "n"),
    "workspace_next": ("workspace suivant", ""),
    "workspace_prev": ("workspace précédent", ""),
    "monitor_move": ("envoyer la fenêtre sur un autre écran", "direction (left|right|up|down)"),
    "monitor_focus": ("passer sur un autre écran", "direction (left|right|up|down)"),
    "volume_set": ("régler le volume en pour cent", "n"),
    "volume_up": ("monter le volume", "n (optionnel)"),
    "volume_down": ("baisser le volume", "n (optionnel)"),
    "volume_mute": ("couper le son", ""),
    "volume_unmute": ("rétablir le son", ""),
    "brightness_set": ("régler la luminosité en pour cent", "n"),
    "brightness_up": ("monter la luminosité", ""),
    "brightness_down": ("baisser la luminosité", ""),
    "media_play_pause": ("lecture / pause de la musique", ""),
    "media_next": ("piste suivante", ""),
    "media_prev": ("piste précédente", ""),
    "theme_next": ("thème Omarchy suivant", ""),
    "theme_set": ("appliquer un thème Omarchy", "name"),
    "night_light": ("basculer le mode nuit", ""),
    "screenshot": ("capture d'écran", ""),
    "lock_screen": ("verrouiller l'écran", ""),
    "suspend": ("mettre en veille (confirmation demandée)", ""),
    "shutdown": ("éteindre (confirmation demandée)", ""),
    "reboot": ("redémarrer (confirmation demandée)", ""),
    "open_url": ("ouvrir un site", "url"),
    "web_search": ("recherche web", "query"),
    "type_text": ("écrire un texte dans la fenêtre active (dictée)", "text"),
    "dictation_start": ("passer en mode dictée continue", ""),
    "bluetooth_on": ("activer le Bluetooth", ""),
    "bluetooth_off": ("désactiver le Bluetooth", ""),
    "bluetooth_connect": ("connecter un appareil Bluetooth", "device"),
    "bluetooth_disconnect": ("déconnecter un appareil Bluetooth", "device"),
    "wifi_on": ("activer le Wi-Fi", ""),
    "wifi_off": ("désactiver le Wi-Fi", ""),
    "airplane_on": ("mode avion", ""),
    "airplane_off": ("quitter le mode avion", ""),
    "battery": ("niveau de batterie", ""),
    "audio_output_switch": ("changer la sortie audio", ""),
    "notifications_read": ("lire les dernières notifications", ""),
    "notifications_dismiss": ("effacer les notifications", ""),
    "dnd_on": ("activer ne pas déranger", ""),
    "dnd_off": ("désactiver ne pas déranger", ""),
    "session_open": ("ouvrir une session de workspaces nommée", "name"),
    "session_save": ("sauvegarder les fenêtres ouvertes comme session", "name"),
    "time": ("donner l'heure", ""),
    "date": ("donner la date", ""),
    "say": ("prononcer un texte", "text"),
    "pause_listening": ("arrêter d'écouter quelques minutes", "minutes"),
    "help": ("lister les capacités", ""),
}

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class Decision:
    kind: str  # "action" | "reply" | "none"
    intent: str = ""
    slots: dict[str, Any] = field(default_factory=dict)
    reply: str = ""


class Brain:
    def __init__(
        self,
        cfg: Config,
        client: LLMClient,
        context_provider: Callable[[], dict[str, str]] | None = None,
        custom_phrases: list[str] | None = None,
        session_names: list[str] | None = None,
    ) -> None:
        self.cfg = cfg
        self.client = client
        self.context_provider = context_provider
        self.custom_phrases = custom_phrases or []
        self.session_names = session_names or []
        self.history: deque[dict[str, str]] = deque(maxlen=max(0, cfg.llm.history_turns) * 2)

    # ------------------------------------------------------------------ prompts
    def persona(self, language: str) -> str:
        a = self.cfg.assistant
        tone = {
            "warm": "chaleureuse et bienveillante",
            "direct": "directe, sans détour",
            "coach": "énergique, motivante",
        }.get(a.tone, "chaleureuse")
        verb = {
            "concise": "en une phrase très courte",
            "normal": "en une ou deux phrases",
            "chatty": "en deux ou trois phrases, avec un peu de chaleur",
        }.get(a.verbosity, "en une ou deux phrases")
        lang = "en français" if language == "fr" else "in English"
        lines = [
            f"Tu es {a.name}, l'assistante vocale intégrée à Omarchy (Linux, Hyprland). Tu es {tone}.",
            f"Tes réponses sont prononcées à voix haute : réponds {lang}, {verb}, sans markdown, sans listes, sans emojis.",
            "Tu tutoies l'utilisateur. Tu ne prétends jamais avoir fait une action que tu n'as pas déclenchée.",
        ]
        if a.personality:
            lines.append(f"Profil de personnalité demandé par l'utilisateur : {a.personality}")
        if self.cfg.llm.system_prompt_extra:
            lines.append(self.cfg.llm.system_prompt_extra)
        return "\n".join(lines)

    def capabilities_block(self) -> str:
        rows = [
            f"- {name}: {desc}" + (f" (paramètres : {params})" if params else "")
            for name, (desc, params) in CAPABILITIES.items()
        ]
        if self.custom_phrases:
            rows.append(
                "- custom: commandes personnalisées de l'utilisateur, déclenchées par ces phrases : "
                + " | ".join(self.custom_phrases[:20])
            )
        if self.session_names:
            rows.append("- session_open: sessions disponibles : " + ", ".join(self.session_names))
        return "\n".join(rows)

    def context_block(self) -> str:
        if not self.cfg.llm.context or self.context_provider is None:
            return ""
        try:
            ctx = self.context_provider()
        except Exception as exc:  # noqa: BLE001
            log.debug("contexte indisponible : %s", exc)
            return ""
        rows = [f"- {k} : {v}" for k, v in ctx.items() if v]
        return "Contexte actuel :\n" + "\n".join(rows) if rows else ""

    def decide_system_prompt(self, language: str) -> str:
        return (
            f"{self.persona(language)}\n\n"
            "L'utilisateur vient de dire une phrase que le moteur de règles n'a pas reconnue. Décide :\n"
            "1. si c'est une demande d'action réalisable avec l'une des capacités ci-dessous → "
            '{"action": "<nom>", "slots": {...}, "say": "<courte confirmation optionnelle>"}\n'
            '2. si c\'est une question ou une conversation → {"reply": "<réponse parlée>"}\n'
            '3. si ce n\'est pas adressé à toi (bruit, conversation entre humains) → {"ignore": true}\n'
            "Réponds UNIQUEMENT avec un objet JSON, sans texte autour.\n\n"
            f"Capacités :\n{self.capabilities_block()}\n\n{self.context_block()}"
        ).strip()

    def chat_system_prompt(self, language: str) -> str:
        return f"{self.persona(language)}\n\n{self.context_block()}".strip()

    # ------------------------------------------------------------------ appels
    def decide(self, text: str, language: str = "fr") -> Decision:
        result = self.client.chat(
            [*self.history, {"role": "user", "content": text}],
            system=self.decide_system_prompt(language),
            max_tokens=min(self.cfg.llm.max_tokens, 300),
            temperature=min(self.cfg.llm.temperature, 0.3),
            json_mode=True,
        )
        decision = parse_decision(result.text)
        log.info(
            "LLM decide (%s, %d+%d tokens) : %s",
            result.model,
            result.input_tokens,
            result.output_tokens,
            decision,
        )
        if decision.kind == "reply":
            self._remember(text, decision.reply)
        elif decision.kind == "action":
            self._remember(text, decision.reply or f"[action {decision.intent}]")
        return decision

    def converse(self, text: str, language: str = "fr") -> str:
        result = self.client.chat(
            [*self.history, {"role": "user", "content": text}],
            system=self.chat_system_prompt(language),
            max_tokens=self.cfg.llm.max_tokens,
            temperature=self.cfg.llm.temperature,
        )
        answer = _strip_markdown(result.text)
        log.info(
            "LLM chat (%s, %d+%d tokens)", result.model, result.input_tokens, result.output_tokens
        )
        self._remember(text, answer)
        return answer

    def _remember(self, user: str, assistant: str) -> None:
        if self.history.maxlen:
            self.history.append({"role": "user", "content": user})
            self.history.append({"role": "assistant", "content": assistant})

    def forget(self) -> None:
        self.history.clear()


def parse_decision(raw: str) -> Decision:
    """Extrait le JSON de la réponse (tolère les ``` et le texte autour)."""
    match = _JSON_BLOCK.search(raw or "")
    if not match:
        text = _strip_markdown(raw)
        return Decision("reply", reply=text) if text else Decision("none")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return Decision("reply", reply=_strip_markdown(raw))
    if not isinstance(data, dict):
        return Decision("none")
    if data.get("ignore"):
        return Decision("none")
    action = data.get("action") or data.get("intent")
    if action:
        slots = data.get("slots") or data.get("parameters") or {}
        if not isinstance(slots, dict):
            slots = {}
        return Decision(
            "action",
            intent=str(action).strip(),
            slots=slots,
            reply=str(data.get("say") or "").strip(),
        )
    reply = data.get("reply") or data.get("say") or data.get("response") or ""
    return Decision("reply", reply=_strip_markdown(str(reply))) if reply else Decision("none")


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text or "", flags=re.DOTALL)
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


__all__ = ["Brain", "Decision", "CAPABILITIES", "parse_decision", "LLMError"]
