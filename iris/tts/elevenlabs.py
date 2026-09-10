"""Voix ElevenLabs — la voix IA de référence d'Iris (cloud, bibliothèque standard uniquement).

- ``tts.elevenlabs_voice`` : nom (« Sarah », « Charlotte », une voix ajoutée depuis la bibliothèque)
  ou identifiant de voix ; résolu via ``GET /v1/voices`` (mis en cache un jour).
- Modèles : ``eleven_multilingual_v2`` (qualité, français natif), ``eleven_flash_v2_5`` (latence
  minimale), ``eleven_v3`` (le plus expressif : balises ``[laughs]``, ``[whispers]``…).
- Réglages : stability, similarity_boost, style, speed, speaker boost.
- ``previous_text`` relie les phrases d'une même réponse pour une prosodie continue.
- Sortie PCM 16 bits mono (``pcm_24000`` par défaut), lecture phrase par phrase en pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from iris import paths
from iris.audio.playback import play_pcm
from iris.config import TTSConfig
from iris.tts.base import clean_for_speech, speak_streaming
from iris.tts.cache import TTSCache

log = logging.getLogger(__name__)

BASE_URL = "https://api.elevenlabs.io"
_VOICE_ID = re.compile(r"^[A-Za-z0-9]{18,24}$")
# language_code n'est pas accepté par multilingual_v2 (ignoré ou refusé) ; utile pour flash/turbo v2.5 et v3.
_LANGUAGE_CODE_MODELS = ("eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_v3")
MODELS = {
    "eleven_multilingual_v2": "qualité de référence, 29 langues dont le français — défaut",
    "eleven_flash_v2_5": "latence minimale (~75 ms), moitié prix, 32 langues",
    "eleven_turbo_v2_5": "compromis qualité / latence",
    "eleven_v3": "le plus expressif ; balises [laughs], [whispers], [excited]… (stability 0.0 / 0.5 / 1.0)",
}


@dataclass
class ElevenVoice:
    voice_id: str
    name: str
    category: str = ""
    labels: dict[str, str] | None = None
    description: str = ""
    preview_url: str = ""
    public_owner_id: str = ""

    def summary(self) -> str:
        labels = self.labels or {}
        tags = ", ".join(
            v
            for k, v in labels.items()
            if v and k in ("language", "accent", "gender", "age", "descriptive", "use_case")
        )
        return f"{self.name:22} {self.voice_id}  {self.category:12} {tags}"


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsTTS:
    name = "elevenlabs"

    def __init__(
        self,
        cfg: TTSConfig,
        language: str = "fr",
        player: str = "auto",
        cache: TTSCache | None = None,
    ) -> None:
        self.cfg = cfg
        self.language = language
        self.player = player
        self.cache = cache
        self.base_url = (cfg.elevenlabs_base_url or BASE_URL).rstrip("/")
        self.api_key = cfg.elevenlabs_api_key or (
            os.environ.get(cfg.elevenlabs_api_key_env, "") if cfg.elevenlabs_api_key_env else ""
        )
        if not self.api_key:
            raise ElevenLabsError(
                f"{cfg.elevenlabs_api_key_env} absent de l'environnement (clé sur elevenlabs.io → Profile → API keys)"
            )
        self.model = cfg.elevenlabs_model
        self.output_format = cfg.elevenlabs_output_format or "pcm_24000"
        self.sample_rate = (
            int(self.output_format.split("_")[-1])
            if self.output_format.startswith("pcm_")
            else 24000
        )
        self._voice_id: str | None = None
        self._previous_text = ""
        log.info(
            "TTS ElevenLabs : voix « %s », modèle %s, %s",
            cfg.elevenlabs_voice or cfg.elevenlabs_voice_id,
            self.model,
            self.output_format,
        )

    # ------------------------------------------------------------------ HTTP
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
        timeout: float = 60,
    ) -> tuple[bytes, dict]:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v not in (None, "")}
            )
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"xi-api-key": self.api_key, "Accept": "*/*", "User-Agent": "iris-assistant"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 401:
                raise ElevenLabsError("clé ElevenLabs refusée (401)") from exc
            if exc.code in (402, 429):
                raise ElevenLabsError(f"quota ElevenLabs atteint ({exc.code}) : {detail}") from exc
            raise ElevenLabsError(f"ElevenLabs HTTP {exc.code} : {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ElevenLabsError(f"connexion ElevenLabs impossible : {exc}") from exc

    # ------------------------------------------------------------------ voix
    def voices(self, refresh: bool = False) -> list[ElevenVoice]:
        """Voix du compte (prédéfinies + ajoutées), avec cache disque d'un jour."""
        cache_file = paths.cache_dir() / "elevenlabs-voices.json"
        if not refresh:
            try:
                if time.time() - cache_file.stat().st_mtime < 86400:
                    return [
                        ElevenVoice(**v) for v in json.loads(cache_file.read_text(encoding="utf-8"))
                    ]
            except (OSError, ValueError, TypeError):
                pass
        raw, _ = self._request("GET", "/v1/voices", timeout=30)
        voices = [
            ElevenVoice(
                v["voice_id"],
                v.get("name") or "",
                v.get("category") or "",
                v.get("labels") or {},
                v.get("description") or "",
                v.get("preview_url") or "",
            )
            for v in json.loads(raw).get("voices", [])
            if v.get("voice_id")
        ]
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps([v.__dict__ for v in voices], ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass
        return voices

    def library(
        self,
        language: str | None = "fr",
        search: str | None = None,
        gender: str | None = None,
        page_size: int = 30,
        featured: bool | None = None,
    ) -> list[ElevenVoice]:
        """Bibliothèque communautaire (``/v1/shared-voices``), filtrée par langue."""
        params = {
            "language": language,
            "search": search,
            "gender": gender,
            "page_size": page_size,
            "featured": "true" if featured else None,
            "sort": "cloned_by_count",
        }
        raw, _ = self._request("GET", "/v1/shared-voices", params=params, timeout=30)
        result = []
        for v in json.loads(raw).get("voices", []):
            labels = {
                k: str(v.get(k) or "")
                for k in ("language", "accent", "gender", "age", "descriptive", "use_case")
            }
            result.append(
                ElevenVoice(
                    v["voice_id"],
                    v.get("name") or "",
                    str(v.get("category") or "library"),
                    labels,
                    v.get("description") or "",
                    v.get("preview_url") or "",
                    v.get("public_owner_id") or "",
                )
            )
        return result

    def add_from_library(self, public_owner_id: str, voice_id: str, new_name: str) -> str:
        raw, _ = self._request(
            "POST",
            f"/v1/voices/add/{public_owner_id}/{voice_id}",
            body={"new_name": new_name},
            timeout=30,
        )
        try:
            self.voices(refresh=True)
        except ElevenLabsError:
            pass
        return json.loads(raw).get("voice_id", voice_id)

    def resolve_voice(self, wanted: str | None = None) -> str:
        wanted = (wanted or self.cfg.elevenlabs_voice or self.cfg.elevenlabs_voice_id or "").strip()
        if not wanted:
            raise ElevenLabsError(
                "tts.elevenlabs_voice n'est pas configuré (nom ou identifiant ; `iris voices list --engine elevenlabs`)"
            )
        if _VOICE_ID.match(wanted) and " " not in wanted and not wanted.isalpha():
            return wanted
        voices = self.voices()
        lowered = wanted.lower()
        for v in voices:
            if v.name.lower() == lowered or v.voice_id == wanted:
                return v.voice_id
        scored = sorted(
            ((SequenceMatcher(None, lowered, v.name.lower()).ratio(), v) for v in voices),
            key=lambda t: t[0],
            reverse=True,
        )
        if scored and scored[0][0] >= 0.75:
            log.info("Voix ElevenLabs « %s » → « %s »", wanted, scored[0][1].name)
            return scored[0][1].voice_id
        names = ", ".join(v.name for v in voices[:25])
        raise ElevenLabsError(f"voix ElevenLabs « {wanted} » introuvable (disponibles : {names})")

    @property
    def voice_id(self) -> str:
        if self._voice_id is None:
            self._voice_id = self.resolve_voice()
        return self._voice_id

    # ------------------------------------------------------------------ synthèse
    def voice_settings(self) -> dict:
        settings: dict = {}
        if self.cfg.elevenlabs_stability >= 0:
            stability = self.cfg.elevenlabs_stability
            if self.model.startswith("eleven_v3"):
                stability = min(
                    (0.0, 0.5, 1.0), key=lambda x: abs(x - stability)
                )  # v3 : Creative / Natural / Robust
            settings["stability"] = stability
        if self.cfg.elevenlabs_similarity >= 0:
            settings["similarity_boost"] = self.cfg.elevenlabs_similarity
        if self.cfg.elevenlabs_style >= 0 and not self.model.startswith("eleven_v3"):
            settings["style"] = self.cfg.elevenlabs_style
        if self.cfg.elevenlabs_speed and abs(self.cfg.elevenlabs_speed - 1.0) > 1e-6:
            settings["speed"] = max(0.7, min(1.2, self.cfg.elevenlabs_speed))
        settings["use_speaker_boost"] = bool(self.cfg.elevenlabs_speaker_boost)
        return settings

    def _payload(self, text: str, language: str | None) -> dict:
        payload: dict = {
            "text": text,
            "model_id": self.model,
            "voice_settings": self.voice_settings(),
        }
        lang = language or self.language
        if self.model in _LANGUAGE_CODE_MODELS and lang in (
            "fr",
            "en",
            "de",
            "es",
            "it",
            "pt",
            "nl",
        ):
            payload["language_code"] = lang
        if self._previous_text:
            payload["previous_text"] = self._previous_text[-300:]
        return payload

    def synthesize(self, text: str, language: str | None = None) -> tuple[bytes, int]:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return b"", self.sample_rate
        voice_id = self.voice_id

        def call() -> tuple[bytes, int]:
            payload = self._payload(text, language)
            try:
                pcm, _ = self._request(
                    "POST",
                    f"/v1/text-to-speech/{voice_id}",
                    params={"output_format": self.output_format},
                    body=payload,
                )
            except ElevenLabsError as exc:
                if "language_code" in str(exc) and "language_code" in payload:
                    payload.pop("language_code")
                    pcm, _ = self._request(
                        "POST",
                        f"/v1/text-to-speech/{voice_id}",
                        params={"output_format": self.output_format},
                        body=payload,
                    )
                else:
                    raise
            return pcm, self.sample_rate

        if self.cache is not None:
            key = self.cache.key(
                "elevenlabs",
                voice_id,
                self.model,
                self.output_format,
                json.dumps(self.voice_settings(), sort_keys=True),
                language or self.language,
                text,
            )
            pcm, rate = self.cache.fetch(key, call)
        else:
            pcm, rate = call()
        self._previous_text = text
        return pcm, rate

    def speak(self, text: str, language: str | None = None) -> bool:
        text = clean_for_speech(text, self.cfg.max_spoken_chars)
        if not text:
            return False
        self._previous_text = ""
        try:
            return speak_streaming(
                lambda sentence: self.synthesize(sentence, language),
                lambda pcm, rate: play_pcm(pcm, rate, player=self.player),
                text,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Synthèse ElevenLabs impossible : %s", exc)
            return False


def has_api_key(cfg: TTSConfig) -> bool:
    return bool(cfg.elevenlabs_api_key or os.environ.get(cfg.elevenlabs_api_key_env or "", ""))


def preview_to_file(url: str, dest: Path) -> Path:
    """Télécharge l'extrait (mp3) d'une voix de la bibliothèque."""
    req = urllib.request.Request(url, headers={"User-Agent": "iris-assistant"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:  # noqa: S310
        out.write(resp.read())
    return dest
