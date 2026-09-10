"""Heure et date en toutes lettres (fr / en), sans dépendre de la locale système."""

from __future__ import annotations

from datetime import datetime

DAYS = {
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
MONTHS = {
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}


def say_time(now: datetime | None = None, lang: str = "fr") -> str:
    now = now or datetime.now()
    if lang == "en":
        return now.strftime("It is %-I:%M %p").replace("AM", "a.m.").replace("PM", "p.m.") + "."
    minutes = "" if now.minute == 0 else f" {now.minute:02d}"
    return f"Il est {now.hour} heure{'s' if now.hour > 1 else ''}{minutes}."


def say_date(now: datetime | None = None, lang: str = "fr") -> str:
    now = now or datetime.now()
    day = DAYS.get(lang, DAYS["fr"])[now.weekday()]
    month = MONTHS.get(lang, MONTHS["fr"])[now.month - 1]
    if lang == "en":
        return f"Today is {day}, {month} {now.day}, {now.year}."
    day_num = "1er" if now.day == 1 else str(now.day)
    return f"Nous sommes le {day} {day_num} {month} {now.year}."
