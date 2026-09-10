"""Pont vers Claude via le CLI Claude Code (abonnement claude.ai, pas de clé API).

Le CLI ``claude`` s'authentifie avec ``claude login`` (OAuth sur l'abonnement) ; Iris se contente
d'appeler ``claude -p "<question>"`` et de lire la réponse texte. Désactivé par défaut.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from iris.actions import system
from iris.config import AgentsConfig

log = logging.getLogger(__name__)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class ClaudeCodeAgent:
    name = "claude-code"

    def __init__(self, cfg: AgentsConfig) -> None:
        self.cfg = cfg

    @property
    def enabled(self) -> bool:
        return self.cfg.claude_code_enabled

    def available(self) -> bool:
        return system.which(self.cfg.claude_bin) is not None

    def ask(self, prompt: str) -> str:
        if not self.available():
            raise RuntimeError(f"CLI « {self.cfg.claude_bin} » introuvable")
        workdir = (
            Path(self.cfg.claude_workdir).expanduser() if self.cfg.claude_workdir else Path.home()
        )
        argv = [self.cfg.claude_bin, "-p", prompt, "--output-format", "text"]
        log.info("Claude Code : %s", prompt[:80])
        import subprocess

        try:
            proc = subprocess.run(
                argv,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=self.cfg.claude_timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("délai dépassé") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                _ANSI.sub("", proc.stderr.strip())[-300:] or f"code {proc.returncode}"
            )
        return _ANSI.sub("", proc.stdout).strip()
