from pathlib import Path

import pytest

from iris.cli import main


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_ask_time(capsys) -> None:
    assert main(["ask", "quelle", "heure", "est-il"]) == 0
    assert "Il est" in capsys.readouterr().out


def test_ask_unknown_returns_1(capsys) -> None:
    assert main(["ask", "blorp"]) == 1
    out = capsys.readouterr().out
    assert "compris" in out or "saisi" in out


def test_config_init_and_path(isolated_home: Path, capsys) -> None:
    assert main(["config", "init"]) == 0
    path = isolated_home / ".config" / "iris" / "config.toml"
    assert path.exists()
    assert main(["config", "path"]) == 0
    assert str(path) in capsys.readouterr().out


def test_intents_and_service_show(capsys) -> None:
    assert main(["intents"]) == 0
    out = capsys.readouterr().out
    assert "open_app" in out and "shutdown (confirmation)" in out
    assert main(["service", "show"]) == 0
    unit = capsys.readouterr().out
    assert "WantedBy=graphical-session.target" in unit and " run" in unit


def test_journal_lists_actions(capsys) -> None:
    main(["ask", "quelle heure est-il"])
    capsys.readouterr()
    assert main(["journal", "--last", "5"]) == 0
    assert "time" in capsys.readouterr().out
    assert main(["journal", "--clear"]) == 0


def test_doctor_runs(capsys) -> None:
    main(["doctor"])
    assert "diagnostic" in capsys.readouterr().out


def test_llm_info_and_status(capsys) -> None:
    assert main(["llm", "info"]) == 0
    out = capsys.readouterr().out
    assert "opencode-go" in out and "ABSENTE" in out
    assert main(["status", "--waybar"]) == 0
    assert '"alt": "off"' in capsys.readouterr().out


def test_voices_list_kokoro(capsys) -> None:
    assert main(["voices", "list", "--engine", "kokoro"]) == 0
    assert "ff_siwis" in capsys.readouterr().out


def test_trigger_without_daemon(monkeypatch) -> None:
    from iris.actions import system

    monkeypatch.setattr(system, "run", lambda *a, **k: system.CmdResult(False, 1))
    assert main(["trigger"]) == 1
