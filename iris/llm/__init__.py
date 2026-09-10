"""Cerveau LLM : client OpenAI/Anthropic-compatible (OpenCode Zen, OpenCode Go, Ollama…) et décisions."""

from iris.llm.brain import Brain, Decision
from iris.llm.client import PROVIDERS, LLMClient, LLMError, build_client

__all__ = ["Brain", "Decision", "LLMClient", "LLMError", "PROVIDERS", "build_client"]
