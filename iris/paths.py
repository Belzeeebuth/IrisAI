"""Emplacements XDG utilisés par Iris.

- config : ``~/.config/iris/config.toml``
- data   : ``~/.local/share/iris/`` (voix Piper, modèles wake word…)
- state  : ``~/.local/state/iris/`` (journal SQLite, log)
- cache  : ``~/.cache/iris/``
"""

from __future__ import annotations

import os
from pathlib import Path

APP = "iris"


def _xdg(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", Path.home() / ".config") / APP


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", Path.home() / ".local" / "state") / APP


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", Path.home() / ".cache") / APP


def config_file() -> Path:
    return config_dir() / "config.toml"


def voices_dir() -> Path:
    return data_dir() / "voices"


def wakeword_dir() -> Path:
    return data_dir() / "wakeword"


def db_file() -> Path:
    return state_dir() / "iris.db"


def log_file() -> Path:
    return state_dir() / "iris.log"


def systemd_user_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", Path.home() / ".config") / "systemd" / "user"


def ensure_dirs() -> None:
    for d in (config_dir(), data_dir(), state_dir(), cache_dir(), voices_dir(), wakeword_dir()):
        d.mkdir(parents=True, exist_ok=True)
