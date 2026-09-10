from datetime import datetime, timedelta

import pytest

from iris.config import load_config
from iris.core.habits import Habits, describe, intent_key, key_to_intent
from iris.core.journal import Journal
from iris.core.prefs import Prefs
from iris.core.scheduler import Schedule, Scheduler, parse_schedule


# ---------------------------------------------------------------- prefs
def test_prefs_apply_overrides_config(tmp_path):
    journal = Journal(":memory:")
    prefs = Prefs(journal)
    cfg = load_config(tmp_path / "absent.toml")
    assert prefs.apply(cfg) == []
    prefs.set("style.tone", "playful")
    prefs.set("style.verbosity", "concise")
    prefs.set("style.language", "en")
    prefs.set("voice.speed", 1.2)
    prefs.set("voice.name", {"elevenlabs": "Léa", "openai": "sage"})
    prefs.set("wake.extra_phrases", ["nova", "hey nova"])
    prefs.learn_alias("mes mails", "thunderbird")
    prefs.set("habits.suggestions", False)
    applied = prefs.apply(cfg)
    assert (
        cfg.assistant.tone == "playful"
        and cfg.assistant.verbosity == "concise"
        and cfg.assistant.language == "en"
    )
    assert (
        cfg.tts.elevenlabs_speed == 1.2
        and cfg.tts.kokoro_speed == 1.2
        and cfg.tts.piper_length_scale == 0.83
    )
    assert cfg.tts.elevenlabs_voice == "Léa" and cfg.tts.openai_voice == "sage"
    assert "nova" in cfg.wake.phrases and "hey nova" in cfg.wake.phrases
    assert cfg.apps["mes mails"] == "thunderbird" and cfg.habits.enabled is False
    assert len(applied) == 10  # 2 phrases d'activation → 2 lignes
    assert prefs.aliases() == {"mes mails": "thunderbird"}
    assert prefs.forget_alias("mes mails") and not prefs.forget_alias("x")
    assert prefs.reset() >= 7 and prefs.all() == {}


def test_prefs_dismiss_and_cooldown():
    prefs = Prefs(Journal(":memory:"))
    assert not prefs.is_dismissed("k")
    prefs.dismiss("k")
    assert prefs.is_dismissed("k")
    assert prefs.cooldown_ok("c", 24)
    prefs.touch("c")
    assert not prefs.cooldown_ok("c", 24) and prefs.cooldown_ok("c", 0)


# ---------------------------------------------------------------- habits
def insert_action(journal: Journal, ts: float, intent: str, slots: str, ok: bool = True) -> None:
    with journal._lock:
        journal._db.execute(
            "INSERT INTO actions (ts, intent, slots, text, ok, result, duration_ms) VALUES (?,?,?,?,?,?,?)",
            (ts, intent, slots, "", int(ok), "", 0),
        )
        journal._db.commit()


@pytest.fixture
def journal_with_habits():
    journal = Journal(":memory:")
    base = datetime.now().replace(hour=9, minute=5, second=0, microsecond=0)
    for days_ago in (1, 2, 3, 5):
        day = base - timedelta(days=days_ago)
        insert_action(journal, day.timestamp(), "open_app", '{"app": "spotify"}')
        insert_action(journal, day.timestamp() + 30, "workspace_switch", '{"n": 2}')
    insert_action(
        journal, (base - timedelta(days=1, hours=5)).timestamp(), "open_app", '{"app": "obsidian"}'
    )  # une fois
    insert_action(
        journal, (base - timedelta(days=2)).timestamp() + 5, "volume_set", '{"n": 30}', ok=False
    )  # échec ignoré
    yield journal
    journal.close()


def test_routines_and_follow_ups(journal_with_habits):
    habits = Habits(journal_with_habits, window_days=14, min_occurrences=3)
    routines = habits.routines()
    assert routines and routines[0].intent == "open_app" and routines[0].slots == {"app": "spotify"}
    assert routines[0].hour == 9 and routines[0].minute == 0 and routines[0].count == 4
    assert all(r.intent != "volume_set" for r in routines)
    due = habits.routine_due(datetime.now().replace(hour=9, minute=20))
    assert due is not None and due.key == "open_app|app=spotify"
    assert habits.routine_due(datetime.now().replace(hour=15, minute=0)) is None
    follow = habits.follow_up_for("open_app", {"app": "spotify", "app_raw": "spotify"})
    assert (
        follow is not None
        and follow.intent == "workspace_switch"
        and follow.slots == {"n": 2}
        and follow.count == 4
    )
    assert habits.follow_up_for("open_app", {"app": "obsidian"}) is None


def test_intent_keys_and_describe():
    assert (
        intent_key("open_app", {"app": "Spotify", "app_raw": "le spotify"})
        == "open_app|app=spotify"
    )
    assert key_to_intent("workspace_switch|n=2") == ("workspace_switch", {"n": 2})
    assert describe("open_app", {"app": "spotify"}) == "ouvrir spotify"
    assert describe("workspace_switch", {"n": 2}, "en") == "go to workspace 2"
    assert describe("custom", {"command": "dev"}) == "lancer dev"
    assert describe("unknown_intent", {}) == "unknown intent"


# ---------------------------------------------------------------- scheduler
NOW = datetime(2026, 9, 10, 14, 0)  # jeudi


@pytest.mark.parametrize(
    ("text", "kind", "hour", "minute", "days", "action"),
    [
        (
            "chaque matin à 9 h, lance mon workspace de dev",
            "daily",
            9,
            0,
            (),
            "lance mon workspace de dev",
        ),
        (
            "tous les jours à 18h30 mets le thème sombre",
            "daily",
            18,
            30,
            (),
            "mets le theme sombre",
        ),
        (
            "chaque lundi à 8 h 30 ouvre ma session dev",
            "weekly",
            8,
            30,
            (0,),
            "ouvre ma session dev",
        ),
        (
            "en semaine à 9 h lance la compilation",
            "weekly",
            9,
            0,
            (0, 1, 2, 3, 4),
            "lance la compilation",
        ),
        ("le week-end à 10 h mets la musique", "weekly", 10, 0, (5, 6), "mets la musique"),
        ("chaque soir active ne pas déranger", "daily", 20, 0, (), "active ne pas deranger"),
        ("every morning at 9 open spotify", "daily", 9, 0, (), "open spotify"),
        ("every monday at 8:30 open my dev session", "weekly", 8, 30, (0,), "open my dev session"),
        ("every day at 6 pm set the volume to 20", "daily", 18, 0, (), "set the volume to 20"),
    ],
)
def test_parse_recurring(text, kind, hour, minute, days, action):
    schedule, rest = parse_schedule(text, NOW)
    assert (schedule.kind, schedule.hour, schedule.minute, schedule.days, rest) == (
        kind,
        hour,
        minute,
        days,
        action,
    )


def test_parse_once():
    schedule, rest = parse_schedule("dans 10 minutes rappelle-moi de boire de l'eau", NOW)
    assert schedule.kind == "once" and datetime.fromtimestamp(schedule.once_at) == NOW + timedelta(
        minutes=10
    )
    assert rest == "rappelle moi de boire de l'eau"
    schedule, _ = parse_schedule("rappelle-moi de sortir les poubelles à 20 h", NOW)
    assert datetime.fromtimestamp(schedule.once_at) == NOW.replace(hour=20, minute=0)
    schedule, _ = parse_schedule("rappelle-moi à 9 h de partir", NOW)  # 9 h déjà passé → demain
    assert datetime.fromtimestamp(schedule.once_at) == (NOW + timedelta(days=1)).replace(
        hour=9, minute=0
    )
    schedule, _ = parse_schedule("demain à 8 h rappelle-moi le rendez-vous", NOW)
    assert datetime.fromtimestamp(schedule.once_at) == (NOW + timedelta(days=1)).replace(
        hour=8, minute=0
    )
    assert parse_schedule("ferme toutes les applications", NOW) is None
    assert parse_schedule("lance spotify", NOW) is None


def test_schedule_describe():
    assert Schedule("daily", 9, 0).describe() == "chaque jour à 9 h"
    assert Schedule("weekly", 8, 30, (0, 1, 2, 3, 4)).describe() == "en semaine à 8 h 30"
    assert Schedule("weekly", 10, 0, (5, 6)).describe("en") == "on weekends at 10:00"
    assert Schedule("weekly", 7, 15, (0, 3)).describe() == "chaque lundi, jeudi à 7 h 15"


def test_scheduler_crud_and_due():
    journal = Journal(":memory:")
    sched = Scheduler(journal)
    daily = sched.add("ouvrir spotify", "open_app", {"app": "spotify"}, Schedule("daily", 9, 0))
    weekly = sched.add(
        "compilation",
        "task_run",
        {"name": "compilation"},
        Schedule("weekly", 8, 30, (0, 1, 2, 3, 4)),
    )
    once_at = NOW.replace(hour=20).timestamp()
    reminder = sched.add(
        "sortir les poubelles",
        "reminder_fire",
        {"what": "sortir les poubelles"},
        Schedule("once", 20, 0, once_at=once_at),
    )
    assert [a.id for a in sched.list()] == [weekly.id, daily.id, reminder.id]
    assert sched.exists("open_app", {"app": "spotify"}) and not sched.exists(
        "open_app", {"app": "x"}
    )
    assert (
        sched.find("spotify").id == daily.id
        and sched.find(str(weekly.id)).id == weekly.id
        and sched.find("9 h").id == daily.id
    )
    # jeudi 9h05 : daily due, weekly pas due (8h30 + 10 min dépassé), rappel pas encore
    due = sched.due(NOW.replace(hour=9, minute=5))
    assert [a.id for a in due] == [daily.id]
    sched.mark_run(daily, NOW.replace(hour=9, minute=5).timestamp())
    assert sched.due(NOW.replace(hour=9, minute=7)) == []  # déjà exécutée aujourd'hui
    assert [a.id for a in sched.due(NOW.replace(hour=8, minute=32))] == [weekly.id]
    saturday = sched.due(NOW.replace(hour=8, minute=32) + timedelta(days=2))
    assert weekly.id not in [a.id for a in saturday]  # samedi : pas en semaine
    assert [a.id for a in saturday] == [reminder.id]  # rappel raté → toujours dû
    due = sched.due(NOW.replace(hour=20, minute=1))
    assert [a.id for a in due] == [reminder.id]
    sched.mark_run(reminder)
    assert all(a.id != reminder.id for a in sched.list())  # rappel unique supprimé après exécution
    assert sched.delete("compilation").id == weekly.id and sched.delete("compilation") is None
    journal.close()
