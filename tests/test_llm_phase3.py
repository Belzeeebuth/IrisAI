import json

import pytest

from iris.core.journal import Journal
from iris.core.memory import Memory
from iris.llm.brain import Brain, Decision
from iris.llm.client import LLMClient, LLMError, parse_sse
from iris.llm.tools import ToolContext, calc, read_file, run_tool


def sse(*payloads) -> list[bytes]:
    return [f"data: {json.dumps(p)}\n".encode() for p in payloads] + [b"data: [DONE]\n"]


def chat_chunk(text: str) -> dict:
    return {"choices": [{"delta": {"content": text}}]}


def test_parse_sse_skips_noise():
    lines = [b": ping\n", b"\n", b'data: {"a": 1}\n', b"data: not-json\n", b"data: [DONE]\n"]
    assert list(parse_sse(iter(lines))) == [{"a": 1}]


def test_chat_stream_openai_and_anthropic():
    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, json.loads(body)))
        if url.endswith("/messages"):
            return 200, iter(
                sse(
                    {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Bon"}},
                    {
                        "type": "content_block_delta",
                        "delta": {"type": "text_delta", "text": "jour."},
                    },
                    {"type": "message_stop"},
                )
            )
        return 200, iter(sse(chat_chunk("Sa"), chat_chunk("lut.")))

    chat = LLMClient(
        "https://opencode.ai/zen/go/v1",
        "glm-5.3-flash",
        "k",
        provider="opencode-go",
        stream_transport=transport,
    )
    assert "".join(chat.chat_stream([{"role": "user", "content": "x"}], system="S")) == "Salut."
    assert calls[-1][1]["stream"] is True and calls[-1][1]["messages"][0]["role"] == "system"
    msgs = LLMClient(
        "https://opencode.ai/zen/v1",
        "claude-haiku-4-5",
        "k",
        provider="opencode-zen",
        stream_transport=transport,
    )
    assert "".join(msgs.chat_stream([{"role": "user", "content": "x"}], system="S")) == "Bonjour."
    assert calls[-1][0].endswith("/messages") and calls[-1][1]["system"] == "S"


def test_chat_stream_http_error():
    client = LLMClient("http://x/v1", "m", "k", stream_transport=lambda *a: (401, iter([b"nope"])))
    with pytest.raises(LLMError, match="refusée"):
        list(client.chat_stream([{"role": "user", "content": "x"}]))


def test_brain_converse_stream_yields_sentences_and_persists(cfg):
    cfg.llm.enabled = True
    journal = Journal(":memory:")
    memory = Memory(journal)
    memory.add_turn("user", "avant")
    memory.add_turn("assistant", "réponse d'avant")
    chunks = sse(
        chat_chunk("Première phrase assez longue pour être dite seule. Deuxième"),
        chat_chunk(" phrase complète ici !"),
        chat_chunk(" Fin."),
    )
    client = LLMClient(
        "http://localhost:1/v1", "m", stream_transport=lambda *a: (200, iter(chunks))
    )
    brain = Brain(cfg, client, memory=memory)
    assert list(brain.history) == [
        {"role": "user", "content": "avant"},
        {"role": "assistant", "content": "réponse d'avant"},
    ]
    sentences = list(brain.converse_stream("raconte"))
    assert sentences == [
        "Première phrase assez longue pour être dite seule.",
        "Deuxième phrase complète ici !",
        "Fin.",
    ]
    assert (
        memory.history(6)[-1]["content"]
        == "Première phrase assez longue pour être dite seule. Deuxième phrase complète ici ! Fin."
    )


def test_brain_decide_uses_tool_round_trip(cfg):
    cfg.llm.enabled = True
    responses = [
        {
            "choices": [
                {"message": {"content": '{"tool": "calc", "args": {"expression": "15 % de 240"}}'}}
            ]
        },
        {"choices": [{"message": {"content": '{"reply": "Ça fait 36."}'}}]},
    ]
    bodies = []

    def transport(url, headers, body, timeout):
        bodies.append(json.loads(body))
        return 200, json.dumps(responses.pop(0)).encode()

    brain = Brain(cfg, LLMClient("http://localhost:1/v1", "m", transport=transport))
    decision = brain.decide("ça fait combien quinze pour cent de deux cent quarante")
    assert decision == Decision("reply", reply="Ça fait 36.")
    assert len(bodies) == 2
    assert "Résultat de l'outil calc : 36" in bodies[1]["messages"][-1]["content"]
    assert "Outils disponibles" in bodies[0]["messages"][0]["content"]


def test_brain_prompt_includes_memory(cfg):
    cfg.llm.enabled = True
    journal = Journal(":memory:")
    memory = Memory(journal)
    memory.remember("mon éditeur est Zed")
    bodies = []

    def transport(url, headers, body, timeout):
        bodies.append(json.loads(body))
        return 200, json.dumps({"choices": [{"message": {"content": '{"ignore": true}'}}]}).encode()

    brain = Brain(cfg, LLMClient("http://localhost:1/v1", "m", transport=transport), memory=memory)
    brain.decide("blabla")
    assert "mon éditeur : Zed" in bodies[0]["messages"][0]["content"]
    cfg.llm.tools = False
    brain.decide("blabla")
    assert "Outils disponibles" not in bodies[1]["messages"][0]["content"]


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("15 % de 240", "36"),
        ("2^10", "1024"),
        ("3 fois 4 plus 1", "13"),
        ("(1+2)*3", "9"),
        ("1/3", "0.333333"),
    ],
)
def test_calc(expr, expected):
    assert calc(expr) == expected


def test_calc_rejects_code():
    with pytest.raises(ValueError):
        calc("__import__('os').system('ls')")
    with pytest.raises(ValueError):
        calc("abs")


def test_read_file_restricted(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from pathlib import Path

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "notes.md").write_text("bonjour\n", encoding="utf-8")
    assert read_file(str(tmp_path / "notes.md")) == "bonjour\n"
    with pytest.raises(PermissionError):
        read_file("/etc/passwd")
    assert run_tool("read_file", {"path": "/etc/passwd"}).startswith("erreur read_file")


def test_run_tool_context():
    ctx = ToolContext(
        memory_facts=lambda: "- fait",
        tasks_status=lambda: "build : done",
        extra={"echo": lambda **k: str(k)},
    )
    assert run_tool("recall", None, ctx) == "- fait"
    assert run_tool("tasks", None, ctx) == "build : done"
    assert run_tool("echo", {"a": 1}, ctx) == "{'a': 1}"
    assert run_tool("nope", None, ctx).startswith("outil inconnu")
    assert run_tool("recall", None, ToolContext()) == "aucun fait mémorisé"
