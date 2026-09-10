"""Mémoire persistante (SQLite) : journal des actions, préférences, transcriptions (optionnel).

Phase 1 : traçabilité des actions + fondation pour la mémoire contextuelle (phases 3-4).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    intent TEXT NOT NULL,
    slots TEXT NOT NULL DEFAULT '{}',
    text TEXT NOT NULL DEFAULT '',
    ok INTEGER NOT NULL DEFAULT 1,
    result TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    text TEXT NOT NULL,
    wake INTEGER NOT NULL DEFAULT 0,
    handled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS prefs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions(ts);
CREATE INDEX IF NOT EXISTS idx_actions_intent ON actions(intent);
"""


@dataclass
class ActionRecord:
    id: int
    ts: float
    intent: str
    slots: dict[str, Any]
    text: str
    ok: bool
    result: str
    duration_ms: int

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.ts))


class Journal:
    def __init__(
        self,
        path: Path | str = ":memory:",
        store_transcripts: bool = False,
        journal_actions: bool = True,
    ) -> None:
        self.path = str(path)
        self.store_transcripts = store_transcripts
        self.journal_actions = journal_actions
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------------ actions
    def log_action(
        self,
        intent: str,
        slots: dict[str, Any] | None,
        text: str,
        ok: bool,
        result: str = "",
        duration_ms: int = 0,
    ) -> None:
        if not self.journal_actions:
            return
        with self._lock:
            self._db.execute(
                "INSERT INTO actions (ts, intent, slots, text, ok, result, duration_ms) VALUES (?,?,?,?,?,?,?)",
                (
                    time.time(),
                    intent,
                    json.dumps(slots or {}, ensure_ascii=False),
                    text if self.store_transcripts else "",
                    int(ok),
                    result[:500],
                    int(duration_ms),
                ),
            )
            self._db.commit()

    def recent(self, limit: int = 20) -> list[ActionRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM actions ORDER BY id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [
            ActionRecord(
                r["id"],
                r["ts"],
                r["intent"],
                json.loads(r["slots"] or "{}"),
                r["text"],
                bool(r["ok"]),
                r["result"],
                r["duration_ms"],
            )
            for r in rows
        ]

    def intent_counts(self, since_days: float | None = None) -> dict[str, int]:
        """Fréquence des intentions : base de l'apprentissage des habitudes (phase 4)."""
        query = "SELECT intent, COUNT(*) AS n FROM actions"
        params: tuple[Any, ...] = ()
        if since_days is not None:
            query += " WHERE ts >= ?"
            params = (time.time() - since_days * 86400,)
        query += " GROUP BY intent ORDER BY n DESC"
        with self._lock:
            rows = self._db.execute(query, params).fetchall()
        return {r["intent"]: int(r["n"]) for r in rows}

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM actions")
            self._db.execute("DELETE FROM utterances")
            self._db.commit()

    # ------------------------------------------------------------------ transcriptions
    def log_utterance(self, text: str, wake: bool, handled: bool) -> None:
        if not self.store_transcripts:
            return
        with self._lock:
            self._db.execute(
                "INSERT INTO utterances (ts, text, wake, handled) VALUES (?,?,?,?)",
                (time.time(), text, int(wake), int(handled)),
            )
            self._db.commit()

    # ------------------------------------------------------------------ préférences
    def set_pref(self, key: str, value: Any) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO prefs (key, value, updated) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                (key, json.dumps(value, ensure_ascii=False), time.time()),
            )
            self._db.commit()

    def get_pref(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM prefs WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def all_prefs(self) -> dict[str, Any]:
        with self._lock:
            rows = self._db.execute("SELECT key, value FROM prefs ORDER BY key").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}
