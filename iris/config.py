"""Chargement de la configuration : défauts embarqués + surcharge utilisateur (TOML)."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from iris import paths

log = logging.getLogger(__name__)


@dataclass
class AssistantConfig:
    name: str = "Iris"
    language: str = "fr"
    verbosity: str = "normal"
    tone: str = "warm"
    active_window_s: float = 8.0
    follow_up_window_s: float = 5.0
    confirm_timeout_s: float = 12.0
    ack_sound: bool = True


@dataclass
class WakeConfig:
    backend: str = "transcript"
    phrases: list[str] = field(
        default_factory=lambda: ["hey iris", "iris", "ok iris", "salut iris", "dis iris", "hé iris"]
    )
    fuzzy_threshold: float = 0.76
    openwakeword_model: str = ""
    openwakeword_threshold: float = 0.5


@dataclass
class AudioConfig:
    backend: str = "auto"
    device: str = ""
    player: str = "auto"
    sample_rate: int = 16000
    frame_ms: int = 30
    vad_backend: str = "auto"
    vad_aggressiveness: int = 2
    energy_threshold: float = 0.010
    silence_ms: int = 800
    min_speech_ms: int = 250
    max_utterance_s: float = 15.0
    pre_roll_ms: int = 300

    @property
    def frame_samples(self) -> int:
        return int(self.sample_rate * self.frame_ms / 1000)


@dataclass
class STTConfig:
    backend: str = "faster-whisper"
    model: str = "base"
    device: str = "auto"
    compute_type: str = "int8"
    language: str = ""
    beam_size: int = 1
    cloud_fallback: bool = False
    openai_model: str = "whisper-1"


@dataclass
class TTSConfig:
    backend: str = "auto"
    piper_voice: str = "fr_FR-siwis-medium"
    piper_voices_dir: str = ""
    piper_length_scale: float = 1.0
    piper_sentence_silence: float = 0.15
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    espeak_voice: str = "fr"
    max_spoken_chars: int = 600


@dataclass
class PrivacyConfig:
    allow_cloud: bool = False
    store_transcripts: bool = False
    journal_actions: bool = True


@dataclass
class SystemConfig:
    terminal: str = ""
    browser: str = ""
    editor: str = ""
    launcher: str = "auto"
    volume_step: int = 5
    brightness_step: int = 10
    search_url: str = "https://duckduckgo.com/?q={q}"
    notify: bool = True


@dataclass
class AgentsConfig:
    claude_code_enabled: bool = False
    claude_bin: str = "claude"
    claude_timeout_s: int = 180
    claude_workdir: str = ""


@dataclass
class CustomCommand:
    name: str
    phrases: list[str]
    exec: str
    confirm: bool = False
    wait: bool = False
    reply: str = ""


@dataclass
class Config:
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    apps: dict[str, str] = field(default_factory=dict)
    commands: list[CustomCommand] = field(default_factory=list)
    source: Path | None = None

    @property
    def stt_language(self) -> str | None:
        """Langue passée au moteur STT (None = détection automatique)."""
        lang = self.stt.language or self.assistant.language
        return None if lang == "auto" else lang


SECTION_TYPES: dict[str, type] = {
    "assistant": AssistantConfig,
    "wake": WakeConfig,
    "audio": AudioConfig,
    "stt": STTConfig,
    "tts": TTSConfig,
    "privacy": PrivacyConfig,
    "system": SystemConfig,
    "agents": AgentsConfig,
}


def default_config_text() -> str:
    return resources.files("iris.data").joinpath("config.default.toml").read_text(encoding="utf-8")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build(cls: type, data: dict[str, Any], where: str) -> Any:
    assert is_dataclass(cls)
    known = {f.name for f in fields(cls)}
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        name = key.replace("-", "_")
        if name not in known:
            log.warning("Option de configuration inconnue ignorée : [%s] %s", where, key)
            continue
        kwargs[name] = value
    return cls(**kwargs)


def config_from_dict(data: dict[str, Any], source: Path | None = None) -> Config:
    cfg = Config(source=source)
    for section, cls in SECTION_TYPES.items():
        raw = data.get(section, {})
        if not isinstance(raw, dict):
            log.warning("Section [%s] invalide, valeurs par défaut utilisées", section)
            raw = {}
        setattr(cfg, section, _build(cls, raw, section))

    apps = data.get("apps", {})
    cfg.apps = {str(k): str(v) for k, v in apps.items()} if isinstance(apps, dict) else {}

    commands: list[CustomCommand] = []
    for i, raw_cmd in enumerate(data.get("commands", []) or []):
        if not isinstance(raw_cmd, dict):
            continue
        phrases = raw_cmd.get("phrases") or []
        if isinstance(phrases, str):
            phrases = [phrases]
        exec_ = raw_cmd.get("exec", "")
        if not phrases or not exec_:
            log.warning("[[commands]] n°%d ignorée : 'phrases' et 'exec' sont obligatoires", i + 1)
            continue
        commands.append(
            CustomCommand(
                name=str(raw_cmd.get("name") or f"command-{i + 1}"),
                phrases=[str(p) for p in phrases],
                exec=str(exec_),
                confirm=bool(raw_cmd.get("confirm", False)),
                wait=bool(raw_cmd.get("wait", False)),
                reply=str(raw_cmd.get("reply", "")),
            )
        )
    cfg.commands = commands
    return cfg


def load_config(path: Path | None = None) -> Config:
    """Charge les défauts embarqués puis, s'il existe, le fichier utilisateur."""
    defaults = tomllib.loads(default_config_text())
    path = path or paths.config_file()
    user: dict[str, Any] = {}
    if path.exists():
        try:
            user = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            log.error("Configuration illisible (%s) : %s — défauts utilisés", path, exc)
    merged = _deep_merge(defaults, user)
    return config_from_dict(merged, source=path if path.exists() else None)


def write_default_config(path: Path | None = None, force: bool = False) -> Path:
    path = path or paths.config_file()
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(default_config_text(), encoding="utf-8")
    return path
