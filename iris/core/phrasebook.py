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
        "agent_answer": "Claude répond : {answer}",
        # phase 2
        "typed": {"concise": "Écrit.", "normal": "C'est écrit.", "chatty": "Voilà, c'est écrit."},
        "typed_clipboard": "Texte copié dans le presse-papiers, colle-le avec Contrôle V.",
        "dictation_started": "Mode dictée. Je tape tout ce que tu dis. Dis « fin de dictée » pour arrêter.",
        "dictation_stopped": "Fin de dictée.",
        "monitor_moved": "Fenêtre envoyée sur l'écran de {direction}.",
        "monitor_focused": "Écran de {direction}.",
        "bluetooth_on": "Bluetooth activé.",
        "bluetooth_off": "Bluetooth désactivé.",
        "bluetooth_connected": "{device} connecté.",
        "bluetooth_disconnected": "{device} déconnecté.",
        "wifi_on": "Wi-Fi activé.",
        "wifi_off": "Wi-Fi désactivé.",
        "airplane_on": "Mode avion activé.",
        "airplane_off": "Mode avion désactivé.",
        "battery": "Batterie à {n} pour cent{status}.",
        "battery_charging": ", en charge",
        "battery_none": "Je ne détecte pas de batterie.",
        "audio_output_switched": "Sortie audio : {name}.",
        "notifications_dismissed": "Notifications effacées.",
        "dnd_on": "Mode ne pas déranger activé.",
        "dnd_off": "Mode ne pas déranger désactivé.",
        "session_opened": "Session {name} ouverte, {n} application{s} lancée{s}.",
        "session_saved": "Session {name} enregistrée avec {n} application{s}.",
        "llm_disabled": "Je n'ai pas de modèle de langage configuré. Active la section llm de ma configuration.",
        "llm_failed": "Le modèle n'a pas répondu : {reason}",
        "llm_unknown_action": "Le modèle propose une action que je ne connais pas.",
        "left": "gauche",
        "right": "droite",
        "up": "haut",
        "down": "bas",
        "next": "suivant",
        "prev": "précédent",
        # phase 3
        "typed_enter": {"concise": "Envoyé.", "normal": "Envoyé.", "chatty": "C'est envoyé."},
        "dictation_started_enter": "Mode terminal : je tape et je valide chaque phrase. Dis « fin de dictée » pour arrêter.",
        "project_opened": "Projet {name} ouvert.",
        "project_not_found": "Je ne trouve pas le projet {name}.",
        "remembered": {
            "concise": "Noté.",
            "normal": "C'est noté.",
            "chatty": "C'est noté, je m'en souviendrai.",
        },
        "forgotten": "Oublié : {fact}.",
        "forget_none": "Je ne trouve rien qui ressemble à ça dans ma mémoire.",
        "forgot_all": "Mémoire effacée.",
        "recall_intro": "Voilà ce que je sais : ",
        "recall_none": "Je ne sais encore rien de toi. Dis « retiens que … » pour m'apprendre quelque chose.",
        "task_started": "{name} lancé. Je te préviens quand c'est terminé.",
        "task_watch_started": "Je surveille {name}. Je te préviens quand c'est fini.",
        "task_done": "{name} terminé en {duration}.",
        "task_failed": "{name} a échoué après {duration}, code {code}.",
        "task_cancelled": "{name} annulé.",
        "task_watch_done": "{name} est terminé.",
        "task_not_found": "Je ne trouve pas de tâche « {name} ».",
        "task_none_running": "Aucune tâche en cours.",
        "task_status_running": "En cours : {items}.",
        "task_status_one": "{name}, depuis {duration}",
        "task_last": " Dernière terminée : {name}, {status}.",
        "task_result": "{name} : {summary}",
        "task_result_none": "Aucun résultat à lire pour l'instant.",
        "agent_started": "Je demande à {agent}. Je te préviens quand c'est prêt.",
        "agent_done": "{agent} a terminé : {summary}",
        "agent_failed": "{agent} a échoué : {summary}",
        "agents_disabled": "Les agents sont désactivés dans ma configuration (agents.enabled).",
        "resume_question": "Veux-tu reprendre ta session précédente : {apps} ?",
        "resume_none": "Je n'ai pas de session précédente à reprendre.",
        "status_done": "réussie",
        "status_failed": "en échec",
        "status_cancelled": "annulée",
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
        "agent_answer": "Claude says: {answer}",
        # phase 2
        "typed": {
            "concise": "Typed.",
            "normal": "Done, it's typed.",
            "chatty": "There you go, it's typed.",
        },
        "typed_clipboard": "Text copied to the clipboard, paste it with Control V.",
        "dictation_started": "Dictation mode. I'll type everything you say. Say “stop dictation” to end.",
        "dictation_stopped": "Dictation ended.",
        "monitor_moved": "Window sent to the {direction} monitor.",
        "monitor_focused": "{direction} monitor.",
        "bluetooth_on": "Bluetooth on.",
        "bluetooth_off": "Bluetooth off.",
        "bluetooth_connected": "{device} connected.",
        "bluetooth_disconnected": "{device} disconnected.",
        "wifi_on": "Wi-Fi on.",
        "wifi_off": "Wi-Fi off.",
        "airplane_on": "Airplane mode on.",
        "airplane_off": "Airplane mode off.",
        "battery": "Battery at {n} percent{status}.",
        "battery_charging": ", charging",
        "battery_none": "I can't detect a battery.",
        "audio_output_switched": "Audio output: {name}.",
        "notifications_dismissed": "Notifications cleared.",
        "dnd_on": "Do not disturb on.",
        "dnd_off": "Do not disturb off.",
        "session_opened": "Session {name} opened, {n} application{s} launched.",
        "session_saved": "Session {name} saved with {n} application{s}.",
        "llm_disabled": "I don't have a language model configured. Enable the llm section of my configuration.",
        "llm_failed": "The model didn't answer: {reason}",
        "llm_unknown_action": "The model suggested an action I don't know.",
        "left": "left",
        "right": "right",
        "up": "up",
        "down": "down",
        "next": "next",
        "prev": "previous",
        # phase 3
        "typed_enter": {"concise": "Sent.", "normal": "Sent.", "chatty": "It's sent."},
        "dictation_started_enter": "Terminal mode: I type and submit each sentence. Say “stop dictation” to end.",
        "project_opened": "Project {name} opened.",
        "project_not_found": "I can't find the project {name}.",
        "remembered": {
            "concise": "Noted.",
            "normal": "Noted.",
            "chatty": "Noted, I'll remember that.",
        },
        "forgotten": "Forgotten: {fact}.",
        "forget_none": "I can't find anything like that in my memory.",
        "forgot_all": "Memory cleared.",
        "recall_intro": "Here's what I know: ",
        "recall_none": "I don't know anything about you yet. Say “remember that…” to teach me.",
        "task_started": "{name} started. I'll let you know when it's done.",
        "task_watch_started": "Watching {name}. I'll tell you when it finishes.",
        "task_done": "{name} finished in {duration}.",
        "task_failed": "{name} failed after {duration}, exit code {code}.",
        "task_cancelled": "{name} cancelled.",
        "task_watch_done": "{name} has finished.",
        "task_not_found": "I can't find a task called “{name}”.",
        "task_none_running": "No task is running.",
        "task_status_running": "Running: {items}.",
        "task_status_one": "{name}, for {duration}",
        "task_last": " Last finished: {name}, {status}.",
        "task_result": "{name}: {summary}",
        "task_result_none": "Nothing to read yet.",
        "agent_started": "Asking {agent}. I'll tell you when it's ready.",
        "agent_done": "{agent} is done: {summary}",
        "agent_failed": "{agent} failed: {summary}",
        "agents_disabled": "Agents are disabled in my configuration (agents.enabled).",
        "resume_question": "Do you want to resume your previous session: {apps}?",
        "resume_none": "I have no previous session to resume.",
        "status_done": "succeeded",
        "status_failed": "failed",
        "status_cancelled": "cancelled",
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
