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
    language: str = "fr"  # fr | en | auto (répond dans la langue entendue)
    verbosity: str = "normal"
    tone: str = "warm"
    personality: str = ""  # profil libre transmis au LLM (« Sois directe, tutoie… »)
    active_window_s: float = 8.0
    follow_up_window_s: float = 5.0
    confirm_timeout_s: float = 12.0
    ack_sound: bool = True
    resume_prompt: bool = False  # au démarrage : « Veux-tu reprendre ta session d'hier ? »


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
    # Kokoro (voix IA locale, 24 kHz)
    kokoro_model: str = "kokoro-v1.0.onnx"
    kokoro_voice: str = ""  # vide = ff_siwis (fr) / af_heart (en)
    kokoro_speed: float = 1.0
    kokoro_lang: str = ""  # vide = suit la langue ; ex. fr-fr, en-us, en-gb
    kokoro_models_dir: str = ""  # vide = ~/.local/share/iris/kokoro
    # Endpoint OpenAI-compatible /audio/speech (OpenAI gpt-4o-mini-tts, Kokoro-FastAPI, Speaches…)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini-tts"
    openai_voice: str = "coral"
    openai_instructions: str = ""  # vide = style par défaut selon le ton
    openai_speed: float = 1.0
    openai_api_key_env: str = "OPENAI_API_KEY"
    # ElevenLabs (voix IA de référence)
    elevenlabs_voice: str = "Sarah"  # nom ou identifiant ; `iris voices list --engine elevenlabs`
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "pcm_24000"
    elevenlabs_stability: float = 0.45
    elevenlabs_similarity: float = 0.8
    elevenlabs_style: float = 0.15
    elevenlabs_speed: float = 1.0
    elevenlabs_speaker_boost: bool = True
    elevenlabs_api_key_env: str = "ELEVENLABS_API_KEY"
    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = ""
    # Cartesia Sonic (alternative premium, très faible latence)
    cartesia_voice: str = ""  # identifiant de voix ; `iris voices list --engine cartesia`
    cartesia_model: str = "sonic-3"
    cartesia_emotion: str = ""  # ex. "content", "calm", "enthusiastic" (sonic-3)
    cartesia_speed: float = 1.0
    cartesia_api_key_env: str = "CARTESIA_API_KEY"
    cartesia_version: str = "2026-08-14"
    # Cache disque des synthèses (voix cloud)
    cache: bool = True
    cache_max_mb: int = 200
    # Piper (voix locale de secours)
    piper_voice: str = "fr_FR-siwis-medium"
    piper_voices_dir: str = ""
    piper_length_scale: float = 1.0
    piper_sentence_silence: float = 0.15
    elevenlabs_voice_id: str = ""  # ancien nom, toujours accepté
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
    typing_tool: str = "auto"  # auto | wtype | ydotool | clipboard
    project_dirs: list[str] = field(
        default_factory=lambda: [
            "~/projets",
            "~/projects",
            "~/Projects",
            "~/code",
            "~/dev",
            "~/src",
            "~/work",
        ]
    )
    status_file: str = ""  # vide = $XDG_RUNTIME_DIR/iris/state.json
    waybar_signal: int = 0  # ex. 8 → pkill -RTMIN+8 waybar à chaque changement d'état


@dataclass
class AgentsConfig:
    enabled: bool = False
    default: str = "claude"  # claude | opencode | codex | gemini
    timeout_s: int = 600
    workdir: str = ""  # dossier par défaut (vide = dossier personnel)
    bins: dict[str, str] = field(default_factory=dict)  # [agents.bins] claude = "/chemin/claude"
    # anciens noms (0.1 / 0.2), toujours acceptés
    claude_code_enabled: bool = False
    claude_bin: str = "claude"
    claude_timeout_s: int = 180
    claude_workdir: str = ""


@dataclass
class MemoryConfig:
    enabled: bool = True
    snapshot_interval_min: int = (
        10  # instantané « last » des fenêtres ouvertes (reprise de session)
    )
    resume_min_age_min: int = 60  # âge minimal de l'instantané pour proposer une reprise
    max_facts: int = 200


@dataclass
class BackgroundTask:
    name: str
    phrases: list[str]
    exec: str
    cwd: str = ""
    announce: bool = True
    notify: bool = True


@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = (
        "opencode-go"  # opencode-go | opencode-zen | openai | openrouter | ollama | custom
    )
    base_url: str = ""  # surcharge l'URL du provider (custom)
    api: str = (
        "auto"  # auto | chat | messages   (auto : messages pour claude-*/qwen* chez OpenCode)
    )
    model: str = "glm-5.3-flash"
    api_key_env: str = "OPENCODE_API_KEY"
    api_key: str = ""  # ou directement ici (déconseillé)
    timeout_s: float = 30.0
    max_tokens: int = 400
    temperature: float = 0.4
    fallback_nlu: bool = True  # phrase inconnue → le LLM choisit une action ou répond
    chat: bool = True  # questions ouvertes (« Iris, explique-moi… »)
    context: bool = True  # fenêtre active, workspace, heure, dernières actions dans le prompt
    history_turns: int = 6
    system_prompt_extra: str = ""
    stream: bool = True  # réponses parlées phrase par phrase pendant la génération
    tools: bool = (
        True  # petits outils pour le modèle (calcul, presse-papiers, fichier, mémoire, tâches)
    )


@dataclass
class SessionApp:
    exec: str
    workspace: int | None = None


@dataclass
class Session:
    name: str
    phrases: list[str]
    apps: list[SessionApp]


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
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    apps: dict[str, str] = field(default_factory=dict)
    projects: dict[str, str] = field(default_factory=dict)
    tasks: list[BackgroundTask] = field(default_factory=list)
    bluetooth: dict[str, str] = field(default_factory=dict)
    commands: list[CustomCommand] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
    source: Path | None = None

    @property
    def stt_language(self) -> str | None:
        """Langue passée au moteur STT (None = détection automatique)."""
        lang = self.stt.language or self.assistant.language
        return None if lang == "auto" else lang

    @property
    def reply_language(self) -> str:
        """Langue par défaut des réponses (« auto » → fr)."""
        return "fr" if self.assistant.language == "auto" else self.assistant.language


SECTION_TYPES: dict[str, type] = {
    "assistant": AssistantConfig,
    "wake": WakeConfig,
    "audio": AudioConfig,
    "stt": STTConfig,
    "tts": TTSConfig,
    "privacy": PrivacyConfig,
    "system": SystemConfig,
    "agents": AgentsConfig,
    "llm": LLMConfig,
    "memory": MemoryConfig,
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
    bt = data.get("bluetooth", {})
    cfg.bluetooth = {str(k): str(v) for k, v in bt.items()} if isinstance(bt, dict) else {}
    projects = data.get("projects", {})
    cfg.projects = (
        {str(k): str(v) for k, v in projects.items()} if isinstance(projects, dict) else {}
    )

    tasks: list[BackgroundTask] = []
    for i, raw_t in enumerate(data.get("tasks", []) or []):
        if not isinstance(raw_t, dict) or not raw_t.get("exec"):
            log.warning("[[tasks]] n°%d ignorée : 'exec' est obligatoire", i + 1)
            continue
        phrases = raw_t.get("phrases") or [str(raw_t.get("name") or f"tache-{i + 1}")]
        if isinstance(phrases, str):
            phrases = [phrases]
        tasks.append(
            BackgroundTask(
                name=str(raw_t.get("name") or f"tache-{i + 1}"),
                phrases=[str(p) for p in phrases],
                exec=str(raw_t["exec"]),
                cwd=str(raw_t.get("cwd", "")),
                announce=bool(raw_t.get("announce", True)),
                notify=bool(raw_t.get("notify", True)),
            )
        )
    cfg.tasks = tasks

    sessions: list[Session] = []
    for i, raw_s in enumerate(data.get("sessions", []) or []):
        if not isinstance(raw_s, dict):
            continue
        name = str(raw_s.get("name") or f"session-{i + 1}")
        phrases = raw_s.get("phrases") or [name]
        if isinstance(phrases, str):
            phrases = [phrases]
        apps_list: list[SessionApp] = []
        for raw_app in raw_s.get("apps", []) or []:
            if isinstance(raw_app, str):
                apps_list.append(SessionApp(exec=raw_app))
            elif isinstance(raw_app, dict) and raw_app.get("exec"):
                ws = raw_app.get("workspace")
                apps_list.append(
                    SessionApp(
                        exec=str(raw_app["exec"]), workspace=int(ws) if ws is not None else None
                    )
                )
        if not apps_list:
            log.warning("[[sessions]] « %s » ignorée : aucune application", name)
            continue
        sessions.append(Session(name=name, phrases=[str(p) for p in phrases], apps=apps_list))
    cfg.sessions = sessions

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
