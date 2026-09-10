"""Hyprland ≥ 0.56 : traduction des dispatchers vers l'API Lua ``hl.dsp``."""

from __future__ import annotations

import pytest

from iris.actions import hyprland
from iris.actions.system import CmdResult

LUA_ERROR = (
    'error: [string "return hl.dispatch(closewindow address:0x1..."]:1: \')\' expected near '
    "'address'\n\n → Note: dispatch in lua is a shorthand for hl.dispatch(...)"
)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("killactive",), "hl.dsp.window.close()"),
        (("closewindow", "address:0x1a"), 'hl.dsp.window.close({ window = "address:0x1a" })'),
        (("focuswindow", "address:0x1a"), 'hl.dsp.focus({ window = "address:0x1a" })'),
        (("workspace", "3"), 'hl.dsp.focus({ workspace = "3" })'),
        (("workspace", "e+1"), 'hl.dsp.focus({ workspace = "e+1" })'),
        (("movetoworkspace", "2"), 'hl.dsp.window.move({ workspace = "2" })'),
        (
            ("movetoworkspacesilent", "2"),
            'hl.dsp.window.move({ workspace = "2", follow = false })',
        ),
        (("fullscreen", "0"), 'hl.dsp.window.fullscreen({ mode = "fullscreen" })'),
        (("fullscreen", "1"), 'hl.dsp.window.fullscreen({ mode = "maximized" })'),
        (("togglefloating",), 'hl.dsp.window.float({ action = "toggle" })'),
        (("movewindow", "mon:l"), 'hl.dsp.window.move({ monitor = "l" })'),
        (("focusmonitor", "r"), 'hl.dsp.focus({ monitor = "r" })'),
    ],
)
def test_to_lua(args, expected):
    assert hyprland.to_lua(*args) == expected


def test_to_lua_escapes_quotes():
    assert hyprland.to_lua("focuswindow", 'title:a"b') == 'hl.dsp.focus({ window = "title:a\\"b" })'


def test_to_lua_unknown():
    with pytest.raises(RuntimeError):
        hyprland.to_lua("exec", "foo")


class _Hyprctl:
    """Simule hyprctl : l'ancienne syntaxe échoue, le Lua réussit."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kw) -> CmdResult:
        argv = list(argv)
        self.calls.append(argv)
        if argv[1] == "dispatch" and not argv[2].startswith("hl."):
            return CmdResult(False, 7, LUA_ERROR, "", argv)
        return CmdResult(True, 0, "ok", "", argv)


def test_dispatch_falls_back_to_lua_once(monkeypatch):
    fake = _Hyprctl()
    monkeypatch.setattr(hyprland.system, "run", fake)
    monkeypatch.setattr(hyprland, "_lua_dispatch", None)
    monkeypatch.setattr(hyprland, "ensure_env", lambda: True)

    hyprland.close_window("0x1a")
    hyprland.switch_workspace(2)

    assert [c[1:] for c in fake.calls] == [
        ["dispatch", "closewindow", "address:0x1a"],
        ["dispatch", 'hl.dsp.window.close({ window = "address:0x1a" })'],
        ["dispatch", 'hl.dsp.focus({ workspace = "2" })'],
    ]


def test_dispatch_other_errors_propagate(monkeypatch):
    def failing(argv, **_kw):
        return CmdResult(False, 1, "", "Couldn't connect to socket", list(argv))

    monkeypatch.setattr(hyprland.system, "run", failing)
    monkeypatch.setattr(hyprland, "_lua_dispatch", None)
    monkeypatch.setattr(hyprland, "ensure_env", lambda: True)
    with pytest.raises(RuntimeError, match="socket"):
        hyprland.close_active_window()
    assert hyprland._lua_dispatch is None
