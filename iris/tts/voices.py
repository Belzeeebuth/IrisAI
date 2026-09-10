"""Gestion des voix Piper : emplacement, téléchargement depuis Hugging Face."""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path

from iris import paths

log = logging.getLogger(__name__)

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICES_JSON = f"{HF_BASE}/voices.json"

# Sélection hors-ligne (la liste complète vient de voices.json).
KNOWN_VOICES: dict[str, str] = {
    "fr_FR-siwis-medium": "Française, féminine, naturelle — recommandée",
    "fr_FR-upmc-medium": "Française, deux locuteurs (jessica / pierre)",
    "fr_FR-tom-medium": "Française, masculine",
    "fr_FR-gilles-low": "Française, masculine, légère (rapide)",
    "en_US-lessac-medium": "Anglais US, féminine",
    "en_US-amy-medium": "Anglais US, féminine",
    "en_US-ryan-high": "Anglais US, masculine, haute qualité",
    "en_GB-alba-medium": "Anglais UK, féminine",
}


def voices_dir(configured: str = "") -> Path:
    return Path(configured).expanduser() if configured else paths.voices_dir()


def voice_files(voice: str, configured_dir: str = "") -> tuple[Path, Path] | None:
    """Retourne (modèle .onnx, config .onnx.json) si la voix est installée."""
    candidates = [
        voices_dir(configured_dir),
        Path.home() / ".local/share/piper-voices",
        Path("/usr/share/piper-voices"),
    ]
    for base in candidates:
        model = base / f"{voice}.onnx"
        config = base / f"{voice}.onnx.json"
        if model.exists() and config.exists():
            return model, config
        # voix rangées en sous-dossiers (fr/fr_FR/siwis/medium/…)
        for model in base.rglob(f"{voice}.onnx") if base.exists() else []:
            config = model.with_suffix(".onnx.json")
            if config.exists():
                return model, config
    return None


def voice_urls(voice: str) -> tuple[str, str]:
    try:
        lang_code, name, quality = voice.split("-", 2)
    except ValueError as exc:
        raise ValueError(f"Nom de voix invalide : {voice} (attendu : fr_FR-siwis-medium)") from exc
    family = lang_code.split("_")[0]
    base = f"{HF_BASE}/{family}/{lang_code}/{name}/{quality}/{voice}"
    return f"{base}.onnx?download=true", f"{base}.onnx.json?download=true"


def _download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "iris-assistant"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and sys.stderr.isatty():
                print(
                    f"\r  {dest.name}: {done * 100 // total:3d}%",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
        if total and sys.stderr.isatty():
            print(file=sys.stderr)
    tmp.replace(dest)


def download_voice(voice: str, configured_dir: str = "", force: bool = False) -> tuple[Path, Path]:
    target = voices_dir(configured_dir)
    target.mkdir(parents=True, exist_ok=True)
    model = target / f"{voice}.onnx"
    config = target / f"{voice}.onnx.json"
    if model.exists() and config.exists() and not force:
        return model, config
    model_url, config_url = voice_urls(voice)
    log.info("Téléchargement de la voix %s…", voice)
    _download(config_url, config)
    _download(model_url, model)
    return model, config


def list_remote_voices(language: str | None = None) -> list[tuple[str, str]]:
    """Liste (nom, description) depuis voices.json ; repli sur KNOWN_VOICES hors-ligne."""
    try:
        req = urllib.request.Request(VOICES_JSON, headers={"User-Agent": "iris-assistant"})
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            data = json.load(resp)
    except Exception as exc:
        log.debug("voices.json inaccessible (%s), liste embarquée", exc)
        return [(k, v) for k, v in KNOWN_VOICES.items() if not language or k.startswith(language)]
    result = []
    for key, info in sorted(data.items()):
        if language and not key.startswith(language):
            continue
        lang = info.get("language", {}).get("name_native", "")
        quality = info.get("quality", "")
        speakers = info.get("num_speakers", 1)
        result.append((key, f"{lang}, {quality}, {speakers} locuteur(s)"))
    return result
