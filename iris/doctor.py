"""`iris doctor` : vérifie les dépendances, l'audio, Hyprland, les modèles et la configuration."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass

from iris import __version__, paths
from iris.actions import hyprland, omarchy, system
from iris.config import Config
from iris.tts.voices import voice_files


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    hint: str = ""
    level: str = "error"  # error | warn | info

    def render(self) -> str:
        mark = "✓" if self.ok else {"error": "✗", "warn": "!"}.get(self.level, "·")
        line = f"  {mark} {self.name}"
        if self.detail:
            line += f" — {self.detail}"
        if not self.ok and self.hint:
            line += f"\n      → {self.hint}"
        return line


def _module(name: str, extra: str, level: str = "warn") -> Check:
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "")
        return Check(f"module {name}", True, version)
    except Exception as exc:  # noqa: BLE001
        return Check(
            f"module {name}",
            False,
            str(exc).split("(")[0],
            f"pip install 'iris-assistant[{extra}]'",
            level,
        )


def _binary(name: str, hint: str, level: str = "warn", alternatives: tuple[str, ...] = ()) -> Check:
    for candidate in (name, *alternatives):
        path = system.which(candidate)
        if path:
            return Check(candidate, True, path)
    return Check(name, False, "introuvable", hint, level)


def run_checks(cfg: Config) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check("Iris", True, f"v{__version__}, Python {sys.version.split()[0]}", level="info")
    )
    checks.append(
        Check(
            "configuration",
            cfg.source is not None,
            str(cfg.source or paths.config_file()),
            "iris config init",
            "warn",
        )
    )

    # --- session graphique
    checks.append(
        Check(
            "WAYLAND_DISPLAY",
            bool(os.environ.get("WAYLAND_DISPLAY")),
            os.environ.get("WAYLAND_DISPLAY", ""),
            "lance Iris depuis la session Hyprland (uwsm)",
            "warn",
        )
    )
    checks.append(
        Check(
            "Hyprland",
            hyprland.available(),
            os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")[:12],
            "hyprctl introuvable ou instance non détectée",
            "warn",
        )
    )
    checks.append(
        Check(
            "Omarchy",
            omarchy.is_omarchy(),
            "scripts omarchy-* détectés" if omarchy.is_omarchy() else "non détecté",
            "certaines commandes (thèmes, web-apps) nécessitent Omarchy",
            "info",
        )
    )

    # --- audio
    checks.append(
        _binary(
            "parec",
            "installe libpulse (parec) ou sounddevice",
            alternatives=("pw-record", "arecord"),
        )
    )
    checks.append(
        _binary(
            "pw-play",
            "installe pipewire (pw-play) / libpulse (paplay)",
            alternatives=("paplay", "aplay", "ffplay"),
        )
    )
    checks.append(
        _binary(
            "wpctl", "installe wireplumber (wpctl) ou libpulse (pactl)", alternatives=("pactl",)
        )
    )
    checks.append(_binary("brightnessctl", "sudo pacman -S brightnessctl", alternatives=("light",)))
    checks.append(_binary("playerctl", "sudo pacman -S playerctl"))
    checks.append(_binary("notify-send", "sudo pacman -S libnotify"))
    checks.append(_binary("uwsm", "lancement des apps via uwsm (recommandé sous Omarchy)", "info"))

    # --- modules python
    checks.append(_module("numpy", "all", "error"))
    checks.append(
        _module("faster_whisper", "stt", "error" if cfg.stt.backend == "faster-whisper" else "info")
    )
    checks.append(_module("sounddevice", "audio", "info"))
    checks.append(_module("webrtcvad", "audio", "info"))
    checks.append(
        _module(
            "openwakeword", "wakeword", "warn" if cfg.wake.backend == "openwakeword" else "info"
        )
    )

    # --- TTS
    piper_ok = False
    try:
        importlib.import_module("piper")
        piper_ok = True
        checks.append(Check("piper (python)", True))
    except Exception:
        from iris.tts.piper import find_piper_binary

        binary = find_piper_binary()
        piper_ok = binary is not None
        checks.append(
            Check(
                "piper",
                piper_ok,
                binary or "",
                "pip install 'iris-assistant[tts]' ou paquet AUR piper-tts-bin",
                "warn",
            )
        )
    files = voice_files(cfg.tts.piper_voice, cfg.tts.piper_voices_dir)
    checks.append(
        Check(
            f"voix {cfg.tts.piper_voice}",
            files is not None,
            str(files[0]) if files else "",
            f"iris voices download {cfg.tts.piper_voice}",
            "warn",
        )
    )
    checks.append(_binary("espeak-ng", "voix de secours : sudo pacman -S espeak-ng", "info"))

    # --- STT modèle
    hf_cache = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    model_dir = os.path.join(hf_cache, "hub", f"models--Systran--faster-whisper-{cfg.stt.model}")
    checks.append(
        Check(
            f"modèle Whisper {cfg.stt.model}",
            os.path.isdir(model_dir),
            model_dir if os.path.isdir(model_dir) else "pas encore téléchargé",
            f"iris models download {cfg.stt.model}",
            "warn",
        )
    )

    # --- agents
    if cfg.agents.claude_code_enabled:
        checks.append(
            _binary(cfg.agents.claude_bin, "installe Claude Code puis `claude login`", "warn")
        )

    # --- privacy
    checks.append(
        Check(
            "mode local",
            not cfg.privacy.allow_cloud,
            "aucune donnée n'est envoyée vers le cloud"
            if not cfg.privacy.allow_cloud
            else "cloud autorisé",
            level="info",
        )
    )
    return checks


def report(cfg: Config) -> tuple[str, bool]:
    checks = run_checks(cfg)
    lines = ["Iris — diagnostic", ""]
    lines += [c.render() for c in checks]
    errors = [c for c in checks if not c.ok and c.level == "error"]
    warns = [c for c in checks if not c.ok and c.level == "warn"]
    lines.append("")
    if errors:
        lines.append(f"{len(errors)} problème(s) bloquant(s), {len(warns)} avertissement(s).")
    elif warns:
        lines.append(f"Prêt avec {len(warns)} avertissement(s) (fonctionnalités en repli).")
    else:
        lines.append("Tout est en ordre.")
    return "\n".join(lines), not errors
