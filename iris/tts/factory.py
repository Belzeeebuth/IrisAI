from __future__ import annotations

import logging
import os

from iris.config import Config
from iris.tts.cache import TTSCache
from iris.tts.console import ConsoleTTS, NullTTS

log = logging.getLogger(__name__)


def _cache(cfg: Config) -> TTSCache | None:
    return TTSCache(max_mb=cfg.tts.cache_max_mb) if cfg.tts.cache else None


def _has_key(env_name: str) -> bool:
    return bool(env_name and os.environ.get(env_name, ""))


def auto_order(cfg: Config) -> list[str]:
    """Ordre de préférence pour ``backend = "auto"`` selon les clés présentes et la vie privée."""
    from iris.tts.openai_speech import is_local_url

    order: list[str] = []
    cloud = cfg.privacy.allow_cloud
    if cloud and (cfg.tts.elevenlabs_api_key or _has_key(cfg.tts.elevenlabs_api_key_env)):
        order.append("elevenlabs")
    if (cloud or is_local_url(cfg.tts.openai_base_url)) and (
        _has_key(cfg.tts.openai_api_key_env) or is_local_url(cfg.tts.openai_base_url)
    ):
        order.append("openai")
    if cloud and _has_key(cfg.tts.cartesia_api_key_env):
        order.append("cartesia")
    order += ["kokoro", "piper", "espeak"]
    return order


def build_backend(name: str, cfg: Config):
    player = cfg.audio.player
    language = cfg.reply_language
    if name == "elevenlabs":
        from iris.tts.elevenlabs import ElevenLabsTTS

        if not cfg.privacy.allow_cloud:
            raise RuntimeError("tts.backend = 'elevenlabs' nécessite privacy.allow_cloud = true")
        return ElevenLabsTTS(cfg.tts, language, player, _cache(cfg))
    if name == "openai":
        from iris.tts.openai_speech import OpenAISpeechTTS, is_local_url

        if not cfg.privacy.allow_cloud and not is_local_url(cfg.tts.openai_base_url):
            raise RuntimeError(
                "tts.backend = 'openai' vers un serveur distant nécessite privacy.allow_cloud = true"
            )
        return OpenAISpeechTTS(cfg.tts, language, cfg.assistant.tone, player, _cache(cfg))
    if name == "cartesia":
        from iris.tts.cartesia import CartesiaTTS

        if not cfg.privacy.allow_cloud:
            raise RuntimeError("tts.backend = 'cartesia' nécessite privacy.allow_cloud = true")
        return CartesiaTTS(cfg.tts, language, player, _cache(cfg))
    if name == "kokoro":
        from iris.tts.kokoro import KokoroTTS

        return KokoroTTS(cfg.tts, language, player)
    if name == "piper":
        from iris.tts.piper import PiperTTS

        return PiperTTS(cfg.tts, player)
    if name == "espeak":
        from iris.tts.espeak import EspeakTTS

        return EspeakTTS(cfg.tts)
    if name == "console":
        return ConsoleTTS()
    if name == "none":
        return NullTTS()
    raise RuntimeError(f"backend TTS inconnu : {name}")


def build_tts(cfg: Config, prefer_console: bool = False):
    """Construit le backend TTS selon la config (auto : meilleure voix disponible, voir ``auto_order``)."""
    if prefer_console:
        return ConsoleTTS()
    backend = cfg.tts.backend
    if backend != "auto":
        return build_backend(backend, cfg)
    errors: list[str] = []
    for name in auto_order(cfg):
        try:
            tts = build_backend(name, cfg)
            log.info("Voix : %s", name)
            return tts
        except Exception as exc:  # noqa: BLE001 - on passe au suivant
            errors.append(f"{name}: {exc}")
    log.warning(
        "Aucune voix disponible (%s) — réponses affichées dans la console", " ; ".join(errors)
    )
    return ConsoleTTS()
