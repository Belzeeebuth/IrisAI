"""Préférences apprises à la voix, persistées dans le journal et appliquées au démarrage.

« Sois plus directe », « parle plus vite », « utilise la voix Léa », « parle en anglais »,
« appelle-toi Nova », « quand je dis mes mails, ouvre Thunderbird » : tout cela survit au
redémarrage sans éditer la configuration. La configuration reste la base ; les préférences
la surchargent.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from iris.config import Config
from iris.core.journal import Journal

log = logging.getLogger(__name__)

TONES = ("warm", "direct", "coach", "playful", "pro", "zen")
VERBOSITY = ("concise", "normal", "chatty")

TONE_WORDS = {
    "direct": "direct",
    "directe": "direct",
    "franche": "direct",
    "franc": "direct",
    "cash": "direct",
    "chaleureuse": "warm",
    "chaleureux": "warm",
    "douce": "warm",
    "doux": "warm",
    "gentille": "warm",
    "warm": "warm",
    "friendly": "warm",
    "coach": "coach",
    "motivante": "coach",
    "motivant": "coach",
    "energique": "coach",
    "energetic": "coach",
    "motivating": "coach",
    "joueuse": "playful",
    "joueur": "playful",
    "taquine": "playful",
    "taquin": "playful",
    "drole": "playful",
    "playful": "playful",
    "funny": "playful",
    "fun": "playful",
    "pro": "pro",
    "professionnelle": "pro",
    "professionnel": "pro",
    "serieuse": "pro",
    "serieux": "pro",
    "professional": "pro",
    "serious": "pro",
    "formelle": "pro",
    "formal": "pro",
    "zen": "zen",
    "calme": "zen",
    "posee": "zen",
    "pose": "zen",
    "calm": "zen",
    "relaxed": "zen",
}


class Prefs:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    # ------------------------------------------------------------------ accès brut
    def get(self, key: str, default: Any = None) -> Any:
        return self.journal.get_pref(f"pref.{key}", default)

    def set(self, key: str, value: Any) -> None:
        self.journal.set_pref(f"pref.{key}", value)

    def delete(self, key: str) -> None:
        self.journal.set_pref(f"pref.{key}", None)

    def all(self) -> dict[str, Any]:
        return {
            k[5:]: v
            for k, v in self.journal.all_prefs().items()
            if k.startswith("pref.") and v is not None
        }

    def reset(self) -> int:
        keys = list(self.all())
        for key in keys:
            self.delete(key)
        return len(keys)

    # ------------------------------------------------------------------ application
    def apply(self, cfg: Config) -> list[str]:
        """Surcharge la configuration avec les préférences apprises ; retourne ce qui a été appliqué."""
        applied: list[str] = []
        tone = self.get("style.tone")
        if tone in TONES:
            cfg.assistant.tone = tone
            applied.append(f"ton = {tone}")
        verbosity = self.get("style.verbosity")
        if verbosity in VERBOSITY:
            cfg.assistant.verbosity = verbosity
            applied.append(f"verbosité = {verbosity}")
        language = self.get("style.language")
        if language in ("fr", "en", "auto"):
            cfg.assistant.language = language
            applied.append(f"langue = {language}")
        speed = self.get("voice.speed")
        if isinstance(speed, int | float) and 0.5 <= float(speed) <= 2.0:
            self.set_speed_on(cfg, float(speed))
            applied.append(f"vitesse = {speed}")
        voice = self.get("voice.name")
        if isinstance(voice, dict):
            for backend, name in voice.items():
                self.set_voice_on(cfg, backend, str(name))
                applied.append(f"voix {backend} = {name}")
        extra = self.get("wake.extra_phrases") or []
        for phrase in extra:
            if phrase and phrase not in cfg.wake.phrases:
                cfg.wake.phrases.append(phrase)
                applied.append(f"activation « {phrase} »")
        aliases = self.get("apps.aliases") or {}
        if isinstance(aliases, dict) and aliases:
            cfg.apps.update({str(k): str(v) for k, v in aliases.items()})
            applied.append(f"{len(aliases)} alias")
        if self.get("habits.suggestions") is False:
            cfg.habits.enabled = False
            applied.append("suggestions désactivées")
        return applied

    @staticmethod
    def set_speed_on(cfg: Config, speed: float) -> None:
        speed = max(0.5, min(2.0, speed))
        cfg.tts.elevenlabs_speed = max(0.7, min(1.2, speed))
        cfg.tts.openai_speed = max(0.25, min(4.0, speed))
        cfg.tts.kokoro_speed = speed
        cfg.tts.cartesia_speed = speed
        cfg.tts.piper_length_scale = round(1.0 / speed, 2)

    @staticmethod
    def set_voice_on(cfg: Config, backend: str, name: str) -> None:
        field = {
            "elevenlabs": "elevenlabs_voice",
            "openai": "openai_voice",
            "cartesia": "cartesia_voice",
            "kokoro": "kokoro_voice",
            "piper": "piper_voice",
        }.get(backend)
        if field:
            setattr(cfg.tts, field, name)

    # ------------------------------------------------------------------ suggestions
    def dismiss(self, key: str) -> None:
        dismissed = self.get("suggestions.dismissed") or {}
        dismissed[key] = time.time()
        self.set("suggestions.dismissed", dismissed)

    def is_dismissed(self, key: str) -> bool:
        return key in (self.get("suggestions.dismissed") or {})

    def cooldown_ok(self, key: str, hours: float) -> bool:
        stamps = self.get("suggestions.cooldown") or {}
        last = float(stamps.get(key, 0))
        return time.time() - last >= hours * 3600

    def touch(self, key: str) -> None:
        stamps = self.get("suggestions.cooldown") or {}
        stamps[key] = time.time()
        self.set("suggestions.cooldown", stamps)

    # ------------------------------------------------------------------ alias
    def learn_alias(self, phrase: str, target: str) -> None:
        aliases = self.get("apps.aliases") or {}
        aliases[phrase] = target
        self.set("apps.aliases", aliases)

    def aliases(self) -> dict[str, str]:
        return dict(self.get("apps.aliases") or {})

    def forget_alias(self, phrase: str) -> bool:
        aliases = self.get("apps.aliases") or {}
        if phrase not in aliases:
            return False
        del aliases[phrase]
        self.set("apps.aliases", aliases)
        return True
