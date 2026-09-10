"""Client HTTP minimal (urllib) pour les API de chat OpenAI-compatibles et Anthropic-compatibles.

Providers prédéfinis :
- ``opencode-go``  : https://opencode.ai/zen/go/v1  (abonnement OpenCode Go, modèles ouverts)
- ``opencode-zen`` : https://opencode.ai/zen/v1     (paiement à l'usage, modèles frontière)
- ``openai``, ``openrouter``, ``ollama`` (local), ``custom`` (base_url libre)

OpenCode expose ``/chat/completions`` (GPT, GLM, Kimi, MiniMax, DeepSeek…) et ``/messages``
(Claude, Qwen). ``api = "auto"`` choisit selon le nom du modèle.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from iris.config import LLMConfig

log = logging.getLogger(__name__)

PROVIDERS: dict[str, dict[str, str]] = {
    "opencode-go": {"base_url": "https://opencode.ai/zen/go/v1", "key_env": "OPENCODE_API_KEY"},
    "opencode-zen": {"base_url": "https://opencode.ai/zen/v1", "key_env": "OPENCODE_API_KEY"},
    "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": ""},
    "custom": {"base_url": "", "key_env": ""},
}

# Chez OpenCode, ces familles passent par l'API Anthropic-compatible /messages.
MESSAGES_API_PREFIXES = ("claude-", "qwen")


class LLMError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def is_local_url(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":")[0].lower()
    return (
        host in ("localhost", "127.0.0.1", "::1")
        or host.endswith(".local")
        or host.startswith(("192.168.", "10."))
    )


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        api: str = "auto",
        timeout: float = 30.0,
        transport: Transport | None = None,
        provider: str = "custom",
    ) -> None:
        if not base_url:
            raise LLMError("base_url manquante pour le LLM")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.provider = provider
        self._transport = transport or _urllib_transport
        self.api = self._resolve_api(api)

    def _resolve_api(self, api: str) -> str:
        if api in ("chat", "messages"):
            return api
        if self.provider.startswith("opencode") and self.model.lower().startswith(
            MESSAGES_API_PREFIXES
        ):
            return "messages"
        return "chat"

    @property
    def is_local(self) -> bool:
        return is_local_url(self.base_url)

    # ------------------------------------------------------------------ public
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str = "",
        max_tokens: int = 400,
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> ChatResult:
        if self.api == "messages":
            return self._chat_messages(messages, system, max_tokens, temperature)
        return self._chat_completions(messages, system, max_tokens, temperature, json_mode)

    # ------------------------------------------------------------------ OpenAI-compatible
    def _chat_completions(self, messages, system, max_tokens, temperature, json_mode) -> ChatResult:
        payload: dict = {
            "model": self.model,
            "messages": ([{"role": "system", "content": system}] if system else []) + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json", "User-Agent": "iris-assistant"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = self._post("/chat/completions", headers, payload)
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if isinstance(content, list):  # certains serveurs renvoient des blocs
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"réponse inattendue : {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        return ChatResult(
            content.strip(),
            data.get("model", self.model),
            int(usage.get("prompt_tokens", 0) or 0),
            int(usage.get("completion_tokens", 0) or 0),
        )

    # ------------------------------------------------------------------ Anthropic-compatible
    def _chat_messages(self, messages, system, max_tokens, temperature) -> ChatResult:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] != "system"
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "iris-assistant",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = self._post("/messages", headers, payload)
        try:
            text = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMError(f"réponse inattendue : {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        return ChatResult(
            text.strip(),
            data.get("model", self.model),
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
        )

    # ------------------------------------------------------------------ transport
    def _post(self, path: str, headers: dict[str, str], payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}{path}"
        try:
            status, raw = self._transport(url, headers, body, self.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError(f"connexion impossible à {self.base_url} : {exc}") from exc
        if status >= 400:
            detail = raw.decode("utf-8", "replace")[:300]
            if status in (401, 403):
                raise LLMError(
                    "clé API refusée (401/403) — vérifie OPENCODE_API_KEY / l'abonnement"
                )
            if status == 404:
                raise LLMError(f"modèle ou endpoint introuvable (404) : {self.model} sur {url}")
            if status == 429:
                raise LLMError("quota atteint (429) — réessaie plus tard")
            raise LLMError(f"HTTP {status} : {detail}")
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"réponse non JSON : {raw[:100]!r}") from exc


def build_client(
    cfg: LLMConfig, allow_cloud: bool, transport: Transport | None = None
) -> LLMClient:
    preset = PROVIDERS.get(cfg.provider)
    if preset is None:
        raise LLMError(f"provider LLM inconnu : {cfg.provider} (choix : {', '.join(PROVIDERS)})")
    base_url = cfg.base_url or preset["base_url"]
    if not base_url:
        raise LLMError("llm.base_url est requis avec provider = custom")
    if not allow_cloud and not is_local_url(base_url):
        raise LLMError(
            "le LLM distant nécessite privacy.allow_cloud = true (les URL localhost restent permises)"
        )
    key_env = cfg.api_key_env or preset["key_env"]
    api_key = cfg.api_key or (os.environ.get(key_env, "") if key_env else "")
    if not api_key and not is_local_url(base_url):
        raise LLMError(
            f"clé API absente : exporte {key_env or 'la variable configurée'} ou renseigne llm.api_key"
        )
    return LLMClient(
        base_url, cfg.model, api_key, cfg.api, cfg.timeout_s, transport, provider=cfg.provider
    )
