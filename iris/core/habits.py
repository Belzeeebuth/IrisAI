"""Apprentissage des habitudes à partir du journal des actions.

- **enchaînements** : « après *ouvrir le terminal*, tu vas presque toujours sur le workspace 2 »
  → « Veux-tu aussi aller sur le workspace 2 ? » ;
- **routines horaires** : « tu lances Spotify vers 9 h la plupart des matins »
  → « Veux-tu que je le fasse automatiquement chaque jour à 9 h ? ».

Tout est calculé localement depuis SQLite ; rien n'est envoyé nulle part.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from iris.core.journal import Journal

# Intentions qui ont un sens répété ou programmé.
AUTOMATABLE = {
    "open_app",
    "open_url",
    "open_project",
    "workspace_switch",
    "session_open",
    "custom",
    "task_run",
    "theme_set",
    "theme_next",
    "volume_set",
    "brightness_set",
    "media_play_pause",
    "bluetooth_connect",
    "dnd_on",
    "dnd_off",
    "night_light",
    "lock_screen",
    "notifications_read",
    "say",
}
SLOT_KEYS = ("app", "url", "name", "n", "command", "text", "device")


def intent_key(intent: str, slots: dict[str, Any] | None) -> str:
    slots = slots or {}
    parts = [f"{k}={str(slots[k]).lower()}" for k in SLOT_KEYS if k in slots]
    return intent + ("|" + "&".join(parts) if parts else "")


def key_to_intent(key: str) -> tuple[str, dict[str, Any]]:
    intent, _, rest = key.partition("|")
    slots: dict[str, Any] = {}
    for part in rest.split("&") if rest else []:
        k, _, v = part.partition("=")
        slots[k] = int(v) if v.isdigit() else v
    return intent, slots


@dataclass
class Routine:
    key: str
    intent: str
    slots: dict[str, Any]
    hour: int
    minute: int
    count: int
    days: list[int] = field(default_factory=list)  # 0 = lundi

    @property
    def weekdays_only(self) -> bool:
        return bool(self.days) and all(d < 5 for d in self.days)


@dataclass
class FollowUp:
    after: str
    key: str
    intent: str
    slots: dict[str, Any]
    count: int
    ratio: float


DESCRIPTIONS = {
    "fr": {
        "open_app": "ouvrir {app}",
        "open_url": "ouvrir {url}",
        "open_project": "ouvrir le projet {name}",
        "workspace_switch": "aller sur le workspace {n}",
        "session_open": "ouvrir la session {name}",
        "custom": "lancer {command}",
        "task_run": "lancer {name}",
        "theme_set": "appliquer le thème {name}",
        "theme_next": "changer de thème",
        "volume_set": "mettre le volume à {n} pour cent",
        "brightness_set": "mettre la luminosité à {n} pour cent",
        "media_play_pause": "lancer la musique",
        "bluetooth_connect": "connecter {device}",
        "dnd_on": "activer ne pas déranger",
        "dnd_off": "désactiver ne pas déranger",
        "night_light": "basculer le mode nuit",
        "lock_screen": "verrouiller l'écran",
        "notifications_read": "lire les notifications",
        "say": "dire « {text} »",
    },
    "en": {
        "open_app": "open {app}",
        "open_url": "open {url}",
        "open_project": "open the project {name}",
        "workspace_switch": "go to workspace {n}",
        "session_open": "open the session {name}",
        "custom": "run {command}",
        "task_run": "run {name}",
        "theme_set": "apply the theme {name}",
        "theme_next": "switch theme",
        "volume_set": "set the volume to {n} percent",
        "brightness_set": "set the brightness to {n} percent",
        "media_play_pause": "play music",
        "bluetooth_connect": "connect {device}",
        "dnd_on": "turn on do not disturb",
        "dnd_off": "turn off do not disturb",
        "night_light": "toggle night light",
        "lock_screen": "lock the screen",
        "notifications_read": "read notifications",
        "say": "say “{text}”",
    },
}


def describe(intent: str, slots: dict[str, Any] | None, lang: str = "fr") -> str:
    table = DESCRIPTIONS.get(lang, DESCRIPTIONS["fr"])
    template = table.get(intent)
    slots = {k: str(v) for k, v in (slots or {}).items()}
    if template is None:
        return intent.replace("_", " ")
    try:
        return template.format(**slots)
    except KeyError:
        return template.split(" {")[0]


class Habits:
    def __init__(self, journal: Journal, window_days: int = 14, min_occurrences: int = 3) -> None:
        self.journal = journal
        self.window_days = window_days
        self.min_occurrences = min_occurrences

    def _rows(self) -> list[tuple[float, str, dict[str, Any]]]:
        since = time.time() - self.window_days * 86400
        rows = []
        for ts, intent, slots_json, ok in self.journal.actions_since(since):
            if not ok or intent not in AUTOMATABLE:
                continue
            try:
                slots = json.loads(slots_json or "{}")
            except json.JSONDecodeError:
                slots = {}
            rows.append((float(ts), intent, slots))
        return rows

    # ------------------------------------------------------------------ routines horaires
    def routines(self, bin_minutes: int = 30) -> list[Routine]:
        buckets: dict[tuple[str, int], list[tuple[float, datetime]]] = defaultdict(list)
        for ts, intent, slots in self._rows():
            when = datetime.fromtimestamp(ts)
            slot = (when.hour * 60 + when.minute + bin_minutes // 2) // bin_minutes
            buckets[(intent_key(intent, slots), slot)].append((ts, when))
        result: list[Routine] = []
        for (key, slot), items in buckets.items():
            days = {when.date() for _, when in items}
            if len(days) < self.min_occurrences:
                continue
            minutes = slot * bin_minutes
            intent, slots = key_to_intent(key)
            weekdays = sorted({when.weekday() for _, when in items})
            result.append(
                Routine(key, intent, slots, minutes // 60 % 24, minutes % 60, len(days), weekdays)
            )
        result.sort(key=lambda r: (-r.count, r.hour, r.minute))
        return result

    def routine_due(self, now: datetime | None = None, tolerance_min: int = 30) -> Routine | None:
        now = now or datetime.now()
        minutes_now = now.hour * 60 + now.minute
        for routine in self.routines():
            if abs(routine.hour * 60 + routine.minute - minutes_now) <= tolerance_min:
                if routine.weekdays_only and now.weekday() >= 5:
                    continue
                return routine
        return None

    # ------------------------------------------------------------------ enchaînements
    def follow_ups(self, window_s: float = 120.0) -> dict[str, FollowUp]:
        rows = sorted(self._rows(), key=lambda r: r[0])
        pairs: dict[str, Counter] = defaultdict(Counter)
        totals: Counter = Counter()
        for i, (ts, intent, slots) in enumerate(rows):
            key = intent_key(intent, slots)
            totals[key] += 1
            for ts2, intent2, slots2 in rows[i + 1 : i + 4]:
                if ts2 - ts > window_s:
                    break
                key2 = intent_key(intent2, slots2)
                if key2 != key:
                    pairs[key][key2] += 1
                    break
        result: dict[str, FollowUp] = {}
        for key, counter in pairs.items():
            next_key, count = counter.most_common(1)[0]
            ratio = count / max(1, totals[key])
            if count >= self.min_occurrences and ratio >= 0.5:
                intent, slots = key_to_intent(next_key)
                result[key] = FollowUp(key, next_key, intent, slots, count, ratio)
        return result

    def follow_up_for(self, intent: str, slots: dict[str, Any] | None) -> FollowUp | None:
        return self.follow_ups().get(intent_key(intent, slots))
