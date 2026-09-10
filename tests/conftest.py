from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from iris.actions import system
from iris.actions.system import CmdResult
from iris.config import Config, load_config
from iris.core.journal import Journal
from iris.core.phrasebook import Phrasebook


class FakeSystem:
    """Simule run / launch / which : enregistre les appels et renvoie des sorties préparées."""

    def __init__(
        self, available: set[str] | None = None, outputs: dict[str, str] | None = None
    ) -> None:
        self.available = set(available or ())
        self.outputs = outputs or {}
        self.calls: list[list[str]] = []
        self.launched: list[list[str] | str] = []

    def which(self, name: str) -> str | None:
        return f"/usr/bin/{name}" if name in self.available else None

    def run(self, argv, **_kw) -> CmdResult:
        argv_list = shlex.split(argv) if isinstance(argv, str) else list(argv)
        self.calls.append(argv_list)
        key = " ".join(argv_list)
        for prefix, out in self.outputs.items():
            if key.startswith(prefix):
                if out is None:
                    return CmdResult(False, 1, "", "échec simulé", argv_list)
                return CmdResult(True, 0, out, "", argv_list)
        return CmdResult(True, 0, "", "", argv_list)

    def launch(self, argv, **_kw) -> bool:
        self.launched.append(argv if isinstance(argv, str) else list(argv))
        return True

    def joined_calls(self) -> list[str]:
        return [" ".join(c) for c in self.calls]


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return load_config(tmp_path / "absent.toml")


@pytest.fixture
def phrases() -> Phrasebook:
    return Phrasebook("fr", "normal", "warm", seed=0)


@pytest.fixture
def journal() -> Journal:
    j = Journal(":memory:", store_transcripts=True)
    yield j
    j.close()


@pytest.fixture
def fake_system(monkeypatch: pytest.MonkeyPatch) -> FakeSystem:
    fake = FakeSystem()
    monkeypatch.setattr(system, "run", fake.run)
    monkeypatch.setattr(system, "launch", fake.launch)
    monkeypatch.setattr(system, "which", fake.which)
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test-signature")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    return fake
