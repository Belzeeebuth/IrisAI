"""Formulations des réponses d'Iris, par langue, verbosité et ton.

Une entrée peut être une chaîne, une liste de variantes (tirée au sort), ou un dictionnaire
indexé par ton (« warm » / « direct » / « coach ») ou par verbosité (« concise » / « normal » / « chatty »).
"""

from __future__ import annotations

import random
from typing import Any

TONES = ("warm", "direct", "coach")
VERBOSITY = ("concise", "normal", "chatty")

PHRASES: dict[str, dict[str, Any]] = {
    "fr": {
        "ack": {
            "warm": ["Oui ?", "Je t'écoute.", "Oui, dis-moi."],
            "direct": ["Oui.", "J'écoute."],
            "coach": ["Je suis là. On fait quoi ?", "Oui, on y va ?"],
        },
        "not_understood": {
            "concise": ["Pas compris."],
            "normal": ["Je n'ai pas compris.", "Désolée, je n'ai pas saisi."],
            "chatty": [
                "Hmm, je n'ai pas compris. Tu peux reformuler ?",
                "Désolée, ça m'échappe. Dis « aide » pour connaître mes commandes.",
            ],
        },
        "cancelled": ["Annulé.", "D'accord, j'annule."],
        "confirm_timeout": "Pas de réponse, je laisse tomber.",
        "ok": {
            "concise": ["Ok."],
            "normal": ["D'accord."],
            "chatty": ["D'accord, je suis là si besoin."],
        },
        "done": ["C'est fait.", "Voilà."],
        "error": "Ça n'a pas fonctionné : {reason}",
        "follow_up": {"concise": "", "normal": "", "chatty": " Autre chose ?"},
        # applications
        "app_opened": {
            "concise": "{app}.",
            "normal": "{app} est lancé.",
            "chatty": "C'est parti, {app} est lancé.",
        },
        "app_webapp_opened": "J'ouvre {app}.",
        "app_not_found": "Je ne trouve pas l'application « {app} ».",
        "app_closed": "{app} fermé.",
        "app_closed_many": "{n} fenêtres de {app} fermées.",
        "app_not_running": "{app} ne semble pas ouvert.",
        "confirm_close_all": "Veux-tu vraiment fermer toutes les applications ?",
        "close_all_done": "{n} fenêtres fermées.",
        "close_all_none": "Il n'y avait rien à fermer.",
        # fenêtres / workspaces
        "window_closed": "Fenêtre fermée.",
        "window_fullscreen": "Plein écran basculé.",
        "window_floating": "Mode flottant basculé.",
        "window_moved": "Fenêtre envoyée sur le workspace {n}.",
        "workspace_switched": {
            "concise": "Workspace {n}.",
            "normal": "Workspace {n}.",
            "chatty": "Te voilà sur le workspace {n}.",
        },
        "workspace_next": "Workspace suivant.",
        "workspace_prev": "Workspace précédent.",
        "hyprland_unavailable": "Je n'arrive pas à parler à Hyprland.",
        # audio / écran
        "volume_set": "Volume à {n} pour cent.",
        "volume_changed": "Volume à {n} pour cent.",
        "volume_changed_unknown": "Volume ajusté.",
        "volume_muted": "Son coupé.",
        "volume_unmuted": "Son rétabli.",
        "brightness_set": "Luminosité à {n} pour cent.",
        "brightness_changed": "Luminosité à {n} pour cent.",
        "brightness_changed_unknown": "Luminosité ajustée.",
        # média
        "media_toggled": "Lecture basculée.",
        "media_next": "Piste suivante.",
        "media_prev": "Piste précédente.",
        "media_unavailable": "Aucun lecteur actif.",
        # omarchy
        "theme_next": "Thème changé.",
        "theme_set": "Thème {name} appliqué.",
        "nightlight_toggled": "Mode nuit basculé.",
        "screenshot": "Sélectionne la zone à capturer.",
        "locked": "Écran verrouillé.",
        # alimentation
        "confirm_suspend": "Veux-tu vraiment mettre l'ordinateur en veille ?",
        "confirm_shutdown": "Veux-tu vraiment éteindre l'ordinateur ?",
        "confirm_reboot": "Veux-tu vraiment redémarrer l'ordinateur ?",
        "suspending": "Mise en veille.",
        "shutting_down": "Extinction. À bientôt.",
        "rebooting": "Redémarrage.",
        # web
        "search": "Je cherche « {query} ».",
        "url_opened": "J'ouvre {url}.",
        # social
        "greet": {
            "warm": ["Bonjour ! Que puis-je faire pour toi ?", "Salut ! Je t'écoute."],
            "direct": ["Bonjour.", "Salut."],
            "coach": ["Bonjour ! Prêt à attaquer la journée ?", "Salut ! On commence par quoi ?"],
        },
        "thanks_reply": {
            "warm": ["Avec plaisir.", "Je t'en prie."],
            "direct": ["De rien."],
            "coach": ["Avec plaisir, continue comme ça !"],
        },
        "who_are_you": "Je suis Iris, l'assistante vocale d'Omarchy. Je tourne entièrement sur cette machine.",
        "help": (
            "Je peux ouvrir ou fermer des applications, changer de workspace, régler le volume et la "
            "luminosité, contrôler la musique, changer de thème, verrouiller l'écran, donner l'heure, "
            "chercher sur le web et lancer tes commandes personnalisées. Dis « Hey Iris » puis ta demande."
        ),
        "stop": {"concise": "", "normal": "Ok.", "chatty": "D'accord, j'arrête."},
        "paused": "Je ne t'écoute plus pendant {minutes} minutes. Dis « Hey Iris, reprends » pour me réveiller.",
        "resumed": "Je t'écoute à nouveau.",
        # commandes perso
        "custom_done": {
            "concise": "Fait.",
            "normal": "{name} : c'est fait.",
            "chatty": "{name} : c'est lancé !",
        },
        "custom_failed": "La commande {name} a échoué.",
        "confirm_custom": "Veux-tu vraiment lancer « {name} » ?",
        # agents
        "agent_disabled": "L'agent Claude est désactivé dans ma configuration.",
        "agent_unavailable": "Le CLI Claude Code est introuvable. Installe-le et connecte-toi avec « claude login ».",
        "agent_thinking": "Je demande à Claude, un instant.",
        "agent_failed": "Claude n'a pas répondu : {reason}",
        "agent_answer": "Claude répond : {answer}",
    },
    "en": {
        "ack": {
            "warm": ["Yes?", "I'm listening.", "Go ahead."],
            "direct": ["Yes."],
            "coach": ["I'm here. What are we doing?"],
        },
        "not_understood": {
            "concise": ["Didn't get that."],
            "normal": ["I didn't understand.", "Sorry, I didn't catch that."],
            "chatty": [
                "Hmm, I didn't get that. Could you rephrase?",
                "Sorry, that escaped me. Say “help” to hear my commands.",
            ],
        },
        "cancelled": ["Cancelled.", "Okay, cancelling."],
        "confirm_timeout": "No answer, never mind.",
        "ok": {
            "concise": ["Ok."],
            "normal": ["Alright."],
            "chatty": ["Alright, I'm here if you need me."],
        },
        "done": ["Done.", "There you go."],
        "error": "That didn't work: {reason}",
        "follow_up": {"concise": "", "normal": "", "chatty": " Anything else?"},
        "app_opened": {
            "concise": "{app}.",
            "normal": "{app} launched.",
            "chatty": "Here we go, {app} is launched.",
        },
        "app_webapp_opened": "Opening {app}.",
        "app_not_found": "I can't find the application “{app}”.",
        "app_closed": "{app} closed.",
        "app_closed_many": "{n} {app} windows closed.",
        "app_not_running": "{app} doesn't seem to be open.",
        "confirm_close_all": "Do you really want to close all applications?",
        "close_all_done": "{n} windows closed.",
        "close_all_none": "There was nothing to close.",
        "window_closed": "Window closed.",
        "window_fullscreen": "Fullscreen toggled.",
        "window_floating": "Floating toggled.",
        "window_moved": "Window sent to workspace {n}.",
        "workspace_switched": {
            "concise": "Workspace {n}.",
            "normal": "Workspace {n}.",
            "chatty": "You're on workspace {n}.",
        },
        "workspace_next": "Next workspace.",
        "workspace_prev": "Previous workspace.",
        "hyprland_unavailable": "I can't talk to Hyprland.",
        "volume_set": "Volume at {n} percent.",
        "volume_changed": "Volume at {n} percent.",
        "volume_changed_unknown": "Volume adjusted.",
        "volume_muted": "Muted.",
        "volume_unmuted": "Sound restored.",
        "brightness_set": "Brightness at {n} percent.",
        "brightness_changed": "Brightness at {n} percent.",
        "brightness_changed_unknown": "Brightness adjusted.",
        "media_toggled": "Playback toggled.",
        "media_next": "Next track.",
        "media_prev": "Previous track.",
        "media_unavailable": "No active player.",
        "theme_next": "Theme changed.",
        "theme_set": "Theme {name} applied.",
        "nightlight_toggled": "Night light toggled.",
        "screenshot": "Select the area to capture.",
        "locked": "Screen locked.",
        "confirm_suspend": "Do you really want to suspend the computer?",
        "confirm_shutdown": "Do you really want to shut down the computer?",
        "confirm_reboot": "Do you really want to reboot the computer?",
        "suspending": "Suspending.",
        "shutting_down": "Shutting down. See you.",
        "rebooting": "Rebooting.",
        "search": "Searching for “{query}”.",
        "url_opened": "Opening {url}.",
        "greet": {
            "warm": ["Hello! What can I do for you?"],
            "direct": ["Hello."],
            "coach": ["Hello! Ready to tackle the day?"],
        },
        "thanks_reply": {
            "warm": ["You're welcome."],
            "direct": ["Sure."],
            "coach": ["My pleasure, keep it up!"],
        },
        "who_are_you": "I'm Iris, Omarchy's voice assistant. I run entirely on this machine.",
        "help": (
            "I can open or close applications, switch workspaces, adjust volume and brightness, control "
            "music, change the theme, lock the screen, tell the time, search the web and run your custom "
            "commands. Say “Hey Iris” then your request."
        ),
        "stop": {"concise": "", "normal": "Ok.", "chatty": "Alright, stopping."},
        "paused": "I'll stop listening for {minutes} minutes. Say “Hey Iris, wake up” to resume.",
        "resumed": "I'm listening again.",
        "custom_done": {
            "concise": "Done.",
            "normal": "{name}: done.",
            "chatty": "{name}: launched!",
        },
        "custom_failed": "The command {name} failed.",
        "confirm_custom": "Do you really want to run “{name}”?",
        "agent_disabled": "The Claude agent is disabled in my configuration.",
        "agent_unavailable": "The Claude Code CLI is not available. Install it and sign in with “claude login”.",
        "agent_thinking": "Asking Claude, one moment.",
        "agent_failed": "Claude didn't answer: {reason}",
        "agent_answer": "Claude says: {answer}",
    },
}


class Phrasebook:
    def __init__(
        self,
        lang: str = "fr",
        verbosity: str = "normal",
        tone: str = "warm",
        seed: int | None = None,
    ) -> None:
        self.lang = lang if lang in PHRASES else "fr"
        self.verbosity = verbosity if verbosity in VERBOSITY else "normal"
        self.tone = tone if tone in TONES else "warm"
        self._rng = random.Random(seed)

    def get(self, key: str, **fmt: Any) -> str:
        table = PHRASES[self.lang]
        value = table.get(key)
        if value is None:
            value = PHRASES["fr"].get(key, key)
        text = self._resolve(value)
        try:
            return text.format(**fmt)
        except (KeyError, IndexError):
            return text

    def _resolve(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return self._resolve(self._rng.choice(value)) if value else ""
        if isinstance(value, dict):
            if any(k in TONES for k in value):
                chosen = value.get(self.tone, value.get("warm", next(iter(value.values()))))
            else:
                chosen = value.get(self.verbosity, value.get("normal", next(iter(value.values()))))
            return self._resolve(chosen)
        return str(value)
