"""Automatisations et rappels : « chaque matin à 9 h, lance mon workspace de dev »,
« rappelle-moi de sortir les poubelles à 20 h », « dans 10 minutes, rappelle-moi … ».

Les automatisations vivent dans SQLite et sont exécutées par le démon Iris (vérification toutes
les ``automations.check_interval_s`` secondes). Une action programmée passe par le routeur comme
une commande vocale ; les actions qui exigent une confirmation ne sont pas programmables.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from iris.core.journal import Journal
from iris.nlu.normalize import canonical

DAY_NAMES = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
DAY_LABELS = {
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_DAY_ALT = "|".join(DAY_NAMES)
_TIME = (
    r"(?P<hour>\d{1,2})\s*(?:h(?:eures?)?|:)?\s*(?P<minute>\d{2})?(?:\s*(?P<ampm>am|pm|du matin|du soir))?"
    r"|(?P<special>midi|minuit|noon|midnight)"
)
_AT_TIME = re.compile(rf"\b(?:a|at|vers|around)\s+(?:{_TIME})\b")
_PERIOD = re.compile(
    r"\b(?:(?P<each>chaque|tous les|toutes les|every|on)\s+"
    r"(?P<what>jours? de (?:la )?semaine|jours? ouvres|week ends?|weekends?|weekdays?|"
    r"matins?|soirs?|jours?|nuits?|midis?|days?|mornings?|evenings?|nights?|semaine|"
    rf"(?:{_DAY_ALT})s?)|(?P<weekday>en semaine|le week end|les week ends|on weekdays|on weekends))\b"
)
_IN = re.compile(
    r"\b(?:dans|in)\s+(?P<n>\d+)\s*(?P<unit>minutes?|min|heures?|h|hours?|secondes?|seconds?|sec|s)\b"
)
_ONCE_DAY = re.compile(
    r"\b(?P<day>demain|tomorrow|ce soir|tonight|this evening|ce matin|this morning|cet apres midi|this afternoon|aujourd'hui|today)\b"
)
_FILLERS = re.compile(r"^(?:de |d'|to |,|et |and |que |that |puis |then )+|(?:,|\s+et|\s+and)+$")


@dataclass
class Schedule:
    kind: str  # daily | weekly | once
    hour: int = 9
    minute: int = 0
    days: tuple[int, ...] = ()  # weekly : 0 = lundi
    once_at: float | None = None  # once : timestamp

    def describe(self, lang: str = "fr") -> str:
        t = f"{self.hour} h {self.minute:02d}" if self.minute else f"{self.hour} h"
        if lang == "en":
            t = f"{self.hour}:{self.minute:02d}"
        if self.kind == "once":
            when = datetime.fromtimestamp(self.once_at or time.time())
            today = datetime.now().date()
            if when.date() == today:
                return (
                    f"aujourd'hui à {when.hour} h {when.minute:02d}"
                    if lang == "fr"
                    else f"today at {when.hour}:{when.minute:02d}"
                )
            if when.date() == today + timedelta(days=1):
                return (
                    f"demain à {when.hour} h {when.minute:02d}"
                    if lang == "fr"
                    else f"tomorrow at {when.hour}:{when.minute:02d}"
                )
            return (
                when.strftime("%d/%m à %H:%M") if lang == "fr" else when.strftime("%m/%d at %H:%M")
            )
        if self.kind == "daily":
            return f"chaque jour à {t}" if lang == "fr" else f"every day at {t}"
        days = sorted(self.days)
        if days == [0, 1, 2, 3, 4]:
            return f"en semaine à {t}" if lang == "fr" else f"on weekdays at {t}"
        if days == [5, 6]:
            return f"le week-end à {t}" if lang == "fr" else f"on weekends at {t}"
        labels = DAY_LABELS.get(lang, DAY_LABELS["fr"])
        names = ", ".join(labels[d] for d in days)
        return f"chaque {names} à {t}" if lang == "fr" else f"every {names} at {t}"


def _parse_time_match(m: re.Match) -> tuple[int, int] | None:
    g = m.groupdict()
    if g.get("special"):
        return (12, 0) if g["special"] in ("midi", "noon") else (0, 0)
    if g.get("hour") is None:
        return None
    hour = int(g["hour"])
    minute = int(g["minute"] or 0)
    ampm = g.get("ampm")
    if ampm in ("pm", "du soir") and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def parse_schedule(text: str, now: datetime | None = None) -> tuple[Schedule, str] | None:
    """Extrait (horaire, texte de l'action) d'une phrase canonique. None si aucun horaire."""
    now = now or datetime.now()
    canon = canonical(text)
    spans: list[tuple[int, int]] = []

    time_match = _AT_TIME.search(canon)
    hm = _parse_time_match(time_match) if time_match else None
    if time_match and hm is not None:
        spans.append(time_match.span())

    period = _PERIOD.search(canon)
    schedule: Schedule | None = None
    if period:
        spans.append(period.span())
        what = (period.group("what") or period.group("weekday") or "").strip()
        what = re.sub(
            r"s\b", "", what
        )  # pluriels : « jours de semaine » → « jour de semaine », « mondays » → « monday »
        what = {"week end": "weekend", "on weekday": "on weekday", "on weekend": "on weekend"}.get(
            what, what
        )
        hour, minute = hm or (9, 0)
        if what in ("matin", "morning"):
            hour, minute = hm or (9, 0)
            schedule = Schedule("daily", hour, minute)
        elif what in ("soir", "evening", "nuit", "night"):
            hour, minute = hm or (20, 0)
            schedule = Schedule("daily", hour, minute)
        elif what in ("midi",):
            schedule = Schedule("daily", *(hm or (12, 0)))
        elif what in ("jour", "day", "aujourd'hui"):
            schedule = Schedule("daily", hour, minute)
        elif what in (
            "weekday",
            "jour de semaine",
            "jour de la semaine",
            "jour ouvre",
            "semaine",
            "en semaine",
            "on weekday",
        ):
            schedule = Schedule("weekly", hour, minute, (0, 1, 2, 3, 4))
        elif what in ("weekend", "week end", "le week end", "les week end", "on weekend"):
            schedule = Schedule("weekly", hour, minute, (5, 6))
        else:
            day = DAY_NAMES.get(what)
            if day is not None:
                schedule = Schedule("weekly", hour, minute, (day,))
        if schedule is None:
            return None
    else:
        delay = _IN.search(canon)
        if delay:
            spans.append(delay.span())
            n = int(delay.group("n"))
            unit = delay.group("unit")
            seconds = n * (3600 if unit.startswith("h") else 1 if unit.startswith("s") else 60)
            at = now + timedelta(seconds=seconds)
            schedule = Schedule("once", at.hour, at.minute, once_at=at.timestamp())
        elif hm is not None:
            day_match = _ONCE_DAY.search(canon)
            base = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
            if day_match:
                spans.append(day_match.span())
                if day_match.group("day") in ("demain", "tomorrow"):
                    base += timedelta(days=1)
            if base <= now:
                base += timedelta(days=1)
            schedule = Schedule("once", hm[0], hm[1], once_at=base.timestamp())
        else:
            return None

    action = canon
    for start, end in sorted(spans, reverse=True):
        action = action[:start] + " " + action[end:]
    action = re.sub(r"\s+", " ", action).strip()
    action = _FILLERS.sub("", action).strip()
    action = _FILLERS.sub("", action).strip()
    return schedule, action


@dataclass
class Automation:
    id: int
    name: str
    kind: str
    intent: str
    slots: dict[str, Any]
    schedule: Schedule
    enabled: bool = True
    created: float = field(default_factory=time.time)
    last_run: float | None = None
    source: str = "voice"

    def describe(self, lang: str = "fr", action: str | None = None) -> str:
        return f"{self.schedule.describe(lang)} : {action or self.name}"


class Scheduler:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    # ------------------------------------------------------------------ CRUD
    def add(
        self,
        name: str,
        intent: str,
        slots: dict[str, Any],
        schedule: Schedule,
        source: str = "voice",
    ) -> Automation:
        auto_id = self.journal.add_automation(
            name,
            schedule.kind,
            intent,
            json.dumps(slots, ensure_ascii=False),
            schedule.hour,
            schedule.minute,
            ",".join(str(d) for d in schedule.days),
            schedule.once_at,
            source,
        )
        return Automation(auto_id, name, schedule.kind, intent, slots, schedule, source=source)

    def list(self, enabled_only: bool = True) -> list[Automation]:
        result = []
        for row in self.journal.list_automations():
            if enabled_only and not row["enabled"]:
                continue
            days = tuple(int(d) for d in (row["days"] or "").split(",") if d)
            schedule = Schedule(
                row["kind"], int(row["hour"]), int(row["minute"]), days, row["once_at"]
            )
            result.append(
                Automation(
                    int(row["id"]),
                    row["name"],
                    row["kind"],
                    row["intent"],
                    json.loads(row["slots"] or "{}"),
                    schedule,
                    bool(row["enabled"]),
                    row["created"],
                    row["last_run"],
                    row["source"],
                )
            )
        return result

    def find(self, query: str) -> Automation | None:
        q = canonical(query)
        items = self.list()
        if not items:
            return None
        if q.isdigit():
            return next((a for a in items if a.id == int(q)), None)
        best: tuple[float, Automation] | None = None
        for auto in items:
            haystack = canonical(
                f"{auto.name} {auto.schedule.describe('fr')} {auto.schedule.hour} h"
            )
            score = (
                0.95 if q in haystack else SequenceMatcher(None, q, canonical(auto.name)).ratio()
            )
            if score >= 0.55 and (best is None or score > best[0]):
                best = (score, auto)
        return best[1] if best else None

    def delete(self, query: str) -> Automation | None:
        auto = self.find(query)
        if auto is not None:
            self.journal.delete_automation(auto.id)
        return auto

    def exists(self, intent: str, slots: dict[str, Any]) -> bool:
        wanted = json.dumps(slots, sort_keys=True, ensure_ascii=False)
        return any(
            a.intent == intent and json.dumps(a.slots, sort_keys=True, ensure_ascii=False) == wanted
            for a in self.list()
        )

    # ------------------------------------------------------------------ exécution
    def due(self, now: datetime | None = None, window_min: int = 10) -> list[Automation]:
        now = now or datetime.now()
        result = []
        for auto in self.list():
            s = auto.schedule
            if s.kind == "once":
                if s.once_at is not None and s.once_at <= now.timestamp() and auto.last_run is None:
                    result.append(auto)
                continue
            if s.kind == "weekly" and now.weekday() not in s.days:
                continue
            planned = now.replace(hour=s.hour, minute=s.minute, second=0, microsecond=0)
            if not (planned <= now < planned + timedelta(minutes=window_min)):
                continue
            if (
                auto.last_run is not None
                and datetime.fromtimestamp(auto.last_run).date() == now.date()
            ):
                continue
            result.append(auto)
        return result

    def mark_run(self, auto: Automation, now: float | None = None) -> None:
        now = now or time.time()
        auto.last_run = now
        self.journal.mark_automation_run(auto.id, now)
        if auto.kind == "once":
            self.journal.delete_automation(auto.id)
