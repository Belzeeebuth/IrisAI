import json

import pytest

from iris.config import LLMConfig
from iris.llm.brain import Brain, Decision, parse_decision
from iris.llm.client import LLMClient, LLMError, build_client


class FakeTransport:
    def __init__(self, status: int = 200, body: dict | str | None = None) -> None:
        self.status = status
        self.body = body
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body)))
        raw = self.body if isinstance(self.body, str) else json.dumps(self.body or {})
        return self.status, raw.encode("utf-8")


def chat_response(text: str) -> dict:
    return {
        "model": "glm-5.3-flash",
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }


def messages_response(text: str) -> dict:
    return {
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 9, "output_tokens": 3},
    }


def test_chat_completions_request_and_parse():
    t = FakeTransport(body=chat_response("Bonjour !"))
    client = LLMClient(
        "https://opencode.ai/zen/go/v1", "glm-5.3-flash", "KEY", transport=t, provider="opencode-go"
    )
    assert client.api == "chat"
    result = client.chat(
        [{"role": "user", "content": "salut"}], system="Tu es Iris.", json_mode=True, max_tokens=50
    )
    url, headers, payload = t.calls[0]
    assert url == "https://opencode.ai/zen/go/v1/chat/completions"
    assert headers["Authorization"] == "Bearer KEY"
    assert payload["messages"][0] == {"role": "system", "content": "Tu es Iris."}
    assert payload["response_format"] == {"type": "json_object"} and payload["max_tokens"] == 50
    assert result.text == "Bonjour !" and result.input_tokens == 12 and result.output_tokens == 5


def test_messages_api_for_claude_on_opencode():
    t = FakeTransport(body=messages_response("Salut."))
    client = LLMClient(
        "https://opencode.ai/zen/v1",
        "claude-haiku-4-5",
        "KEY",
        transport=t,
        provider="opencode-zen",
    )
    assert client.api == "messages"
    result = client.chat([{"role": "user", "content": "salut"}], system="Sys")
    url, headers, payload = t.calls[0]
    assert url == "https://opencode.ai/zen/v1/messages"
    assert headers["x-api-key"] == "KEY" and headers["anthropic-version"]
    assert payload["system"] == "Sys" and payload["messages"] == [
        {"role": "user", "content": "salut"}
    ]
    assert result.text == "Salut."


def test_api_resolution():
    assert (
        LLMClient("https://opencode.ai/zen/go/v1", "qwen3.7-plus", "k", provider="opencode-go").api
        == "messages"
    )
    assert LLMClient("https://api.openai.com/v1", "claude-x", "k", provider="openai").api == "chat"
    assert LLMClient("http://x", "claude-x", "k", api="chat").api == "chat"


@pytest.mark.parametrize(
    ("status", "needle"),
    [(401, "clé API"), (404, "introuvable"), (429, "quota"), (500, "HTTP 500")],
)
def test_http_errors_are_llm_errors(status, needle):
    client = LLMClient(
        "https://opencode.ai/zen/go/v1",
        "glm-5.3-flash",
        "k",
        transport=FakeTransport(status, {"error": "x"}),
    )
    with pytest.raises(LLMError, match=needle):
        client.chat([{"role": "user", "content": "x"}])


def test_non_json_response():
    client = LLMClient("https://x/v1", "m", "k", transport=FakeTransport(200, "<html>"))
    with pytest.raises(LLMError, match="non JSON"):
        client.chat([{"role": "user", "content": "x"}])


def test_build_client_rules(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    with pytest.raises(LLMError, match="allow_cloud"):
        build_client(LLMConfig(provider="opencode-go"), allow_cloud=False)
    with pytest.raises(LLMError, match="clé API"):
        build_client(LLMConfig(provider="opencode-go"), allow_cloud=True)
    monkeypatch.setenv("OPENCODE_API_KEY", "abc")
    client = build_client(LLMConfig(provider="opencode-go", model="kimi-k2.6"), allow_cloud=True)
    assert client.base_url == "https://opencode.ai/zen/go/v1" and client.api_key == "abc"
    local = build_client(
        LLMConfig(provider="ollama", model="llama3", api_key_env=""), allow_cloud=False
    )
    assert local.is_local and local.api_key == ""
    with pytest.raises(LLMError, match="inconnu"):
        build_client(LLMConfig(provider="nope"), allow_cloud=True)
    with pytest.raises(LLMError, match="base_url"):
        build_client(LLMConfig(provider="custom"), allow_cloud=True)
    custom = build_client(
        LLMConfig(provider="custom", base_url="http://localhost:8000/v1", api_key="k"),
        allow_cloud=False,
    )
    assert custom.base_url == "http://localhost:8000/v1"


@pytest.mark.parametrize(
    ("raw", "kind", "intent"),
    [
        ('{"action": "open_app", "slots": {"app": "obsidian"}}', "action", "open_app"),
        ('```json\n{"reply": "Un workspace est un bureau virtuel."}\n```', "reply", ""),
        ('{"ignore": true}', "none", ""),
        ("Bonjour **toi**", "reply", ""),
        ("", "none", ""),
        (
            '{"intent": "volume_set", "parameters": {"n": "40"}, "say": "Ok"}',
            "action",
            "volume_set",
        ),
    ],
)
def test_parse_decision(raw, kind, intent):
    d = parse_decision(raw)
    assert d.kind == kind and d.intent == intent


def test_brain_decide_and_history(cfg):
    cfg.llm.enabled = True
    cfg.assistant.personality = "Sois taquine."
    t = FakeTransport(
        body=chat_response(
            '{"action": "workspace_switch", "slots": {"n": 3}, "say": "Workspace 3."}'
        )
    )
    client = LLMClient("http://localhost:11434/v1", "llama3", transport=t, provider="ollama")
    brain = Brain(
        cfg,
        client,
        context_provider=lambda: {"workspace": "1", "absent": ""},
        custom_phrases=["lance mon workspace de dev"],
        session_names=["video"],
    )
    decision = brain.decide("mets-moi sur le troisième bureau")
    assert decision == Decision("action", "workspace_switch", {"n": 3}, "Workspace 3.")
    system = t.calls[0][2]["messages"][0]["content"]
    assert "Sois taquine." in system and "workspace_switch" in system and "workspace : 1" in system
    assert "lance mon workspace de dev" in system and "video" in system and "absent" not in system
    assert list(brain.history)[-1]["content"] == "Workspace 3."

    t.body = chat_response("Un **workspace** est un bureau virtuel.\n\nVoilà.")
    answer = brain.converse("c'est quoi un workspace ?")
    assert answer == "Un workspace est un bureau virtuel. Voilà."
    assert len(brain.history) == 4
    assert (
        t.calls[-1][2]["messages"][1]["content"] == "mets-moi sur le troisième bureau"
    )  # historique transmis
    brain.forget()
    assert not brain.history


def test_brain_without_context(cfg):
    cfg.llm.context = False
    t = FakeTransport(body=chat_response("ok"))
    brain = Brain(
        cfg,
        LLMClient("http://localhost:1/v1", "m", transport=t),
        context_provider=lambda: {"x": "y"},
    )
    brain.converse("salut")
    assert "Contexte" not in t.calls[0][2]["messages"][0]["content"]
