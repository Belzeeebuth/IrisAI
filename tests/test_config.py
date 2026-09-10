from pathlib import Path

from iris.config import load_config, write_default_config


def test_defaults_when_file_absent(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nope.toml")
    assert cfg.source is None
    assert cfg.assistant.language == "fr"
    assert cfg.wake.backend == "transcript"
    assert cfg.stt_language == "fr"
    assert cfg.privacy.allow_cloud is False
    assert cfg.audio.frame_samples == 480


def test_user_override_merges(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        """
[assistant]
language = "en"
verbosity = "chatty"
unknown_option = 1

[stt]
language = "auto"

[apps]
"mon éditeur" = "zed"

[[commands]]
name = "dev"
phrases = ["lance mon workspace de dev"]
exec = "echo dev"
confirm = true

[[commands]]
phrases = ["sans exec"]
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.source == path
    assert cfg.assistant.language == "en"
    assert cfg.assistant.verbosity == "chatty"
    assert cfg.assistant.tone == "warm"  # défaut conservé
    assert cfg.stt_language is None  # "auto" → détection
    assert cfg.apps == {"mon éditeur": "zed"}
    assert len(cfg.commands) == 1
    assert cfg.commands[0].name == "dev" and cfg.commands[0].confirm is True


def test_write_default_config(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "config.toml"
    assert write_default_config(path) == path
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "[assistant]" in text and "[privacy]" in text
    path.write_text("# modifié", encoding="utf-8")
    write_default_config(path)  # sans force : inchangé
    assert path.read_text(encoding="utf-8") == "# modifié"
    write_default_config(path, force=True)
    assert "[assistant]" in path.read_text(encoding="utf-8")


def test_invalid_toml_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[assistant\nlanguage = ", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.assistant.language == "fr"
