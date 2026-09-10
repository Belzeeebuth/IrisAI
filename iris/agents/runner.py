"""Agents IA lancés à la voix, en arrière-plan : Claude Code, OpenCode, Codex, Gemini CLI…

Tous s'authentifient avec leur propre connexion (abonnement claude.ai pour ``claude login``,
compte OpenCode pour ``opencode``…) : Iris n'a besoin d'aucune clé API. La sortie est
capturée par le ``TaskManager`` ; à la fin, Iris résume à voix haute et notifie.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from iris.actions import system
from iris.config import AgentsConfig
from iris.core.tasks import Task, TaskManager

log = logging.getLogger(__name__)

PRESETS: dict[str, dict] = {
    "claude": {
        "bin": "claude",
        "args": ["-p", "{prompt}", "--output-format", "text"],
        "label": "Claude",
    },
    "opencode": {"bin": "opencode", "args": ["run", "{prompt}"], "label": "OpenCode"},
    "codex": {"bin": "codex", "args": ["exec", "{prompt}"], "label": "Codex"},
    "gemini": {"bin": "gemini", "args": ["-p", "{prompt}"], "label": "Gemini"},
}
ALIASES = {
    "claude code": "claude",
    "l'agent": "",
    "the agent": "",
    "agent": "",
    "un agent": "",
    "an agent": "",
}
_PROJECT_SUFFIX = re.compile(
    r"\s+(?:dans|sur|pour|in|on|for)\s+(?:le |the )?(?:projet|project|dossier|repo|folder)\s+(?P<project>[\w.\-/~ ]+?)\s*$",
    re.IGNORECASE,
)


@dataclass
class AgentSpec:
    name: str
    label: str
    argv: list[str]


class AgentRunner:
    def __init__(self, cfg: AgentsConfig, tasks: TaskManager, projects=None) -> None:
        self.cfg = cfg
        self.tasks = tasks
        self.projects = projects

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.enabled or self.cfg.claude_code_enabled)

    def resolve(self, name: str | None) -> str:
        key = (name or "").strip().lower()
        key = ALIASES.get(key, key)
        if not key:
            key = self.cfg.default
        if key not in PRESETS and key not in self.cfg.bins:
            raise RuntimeError(f"agent inconnu : {name} (disponibles : {', '.join(PRESETS)})")
        return key

    def spec(self, name: str, prompt: str) -> AgentSpec:
        key = self.resolve(name)
        preset = PRESETS.get(key, {"bin": key, "args": ["{prompt}"], "label": key.capitalize()})
        binary = self.cfg.bins.get(key) or preset["bin"]
        if key == "claude" and self.cfg.claude_bin and self.cfg.claude_bin != "claude":
            binary = self.cfg.claude_bin
        if system.which(binary) is None and not Path(binary).expanduser().exists():
            raise RuntimeError(
                f"CLI « {binary} » introuvable — installe-le et connecte-toi (ex. `claude login`)"
            )
        argv = [str(Path(binary).expanduser())] + [
            a.replace("{prompt}", prompt) for a in preset["args"]
        ]
        return AgentSpec(key, preset["label"], argv)

    def available(self, name: str | None = None) -> bool:
        try:
            self.spec(name or self.cfg.default, "x")
            return True
        except RuntimeError:
            return False

    def split_project(self, prompt: str) -> tuple[str, str | None]:
        m = _PROJECT_SUFFIX.search(prompt)
        if not m:
            return prompt, None
        return prompt[: m.start()].strip(), m.group("project").strip()

    def run(self, name: str | None, prompt: str, cwd: str | Path | None = None) -> Task:
        if not self.enabled:
            raise RuntimeError("agents désactivés (agents.enabled = false)")
        prompt, project = self.split_project(prompt)
        workdir: Path | None = Path(cwd).expanduser() if cwd else None
        if project and self.projects is not None:
            resolved = self.projects.resolve(project)
            if resolved is None:
                raise RuntimeError(f"projet introuvable : {project}")
            workdir = resolved
        if workdir is None:
            workdir = Path(self.cfg.workdir or self.cfg.claude_workdir or "~").expanduser()
        spec = self.spec(name, prompt)
        task = self.tasks.run(
            f"{spec.label} : {prompt[:40]}",
            spec.argv,
            cwd=workdir,
            kind="agent",
            meta={
                "agent": spec.name,
                "label": spec.label,
                "prompt": prompt,
                "project": str(workdir),
            },
        )
        return task
