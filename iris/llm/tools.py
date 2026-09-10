"""Petits outils que le LLM peut demander (un seul appel par décision) :
calcul sûr, presse-papiers, lecture d'un fichier du dossier personnel, mémoire, tâches en cours."""

from __future__ import annotations

import ast
import json
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from iris.actions import system

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}
_FUNCS = {"abs": abs, "round": round, "min": min, "max": max, "sqrt": lambda x: x**0.5}
_PERCENT_OF = re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:de|of|du|des)\s*(\d+(?:[.,]\d+)?)")


def calc(expression: str) -> str:
    """Évalue une expression arithmétique sans exécuter de code (« 15 % de 240 », « 2^10 », « sqrt(2) »)."""
    expr = (
        expression.strip()
        .lower()
        .replace(",", ".")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
    )
    expr = _PERCENT_OF.sub(lambda m: f"({m.group(1)}/100*{m.group(2)})", expr)
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr)
    expr = re.sub(r"\b(fois|times)\b", "*", expr)
    expr = re.sub(r"\b(plus)\b", "+", expr)
    expr = re.sub(r"\b(moins|minus)\b", "-", expr)
    expr = re.sub(r"\b(divise par|divided by|sur)\b", "/", expr)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"expression invalide : {expression}") from exc

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
        ):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"élément non autorisé : {ast.dump(node)[:40]}")

    value = ev(tree)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:g}" if isinstance(value, float) else str(value)


def clipboard() -> str:
    if not system.which("wl-paste"):
        raise RuntimeError("wl-paste indisponible")
    res = system.run(["wl-paste", "--no-newline"], timeout=5)
    if not res.ok:
        raise RuntimeError("presse-papiers vide ou inaccessible")
    return res.out[:4000]


def read_file(path: str, max_chars: int = 20000) -> str:
    target = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    if home not in target.parents and target != home:
        raise PermissionError("lecture limitée à ton dossier personnel")
    if not target.is_file():
        raise FileNotFoundError(f"fichier introuvable : {path}")
    if target.stat().st_size > 2_000_000:
        raise ValueError("fichier trop volumineux")
    text = target.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars] + ("\n[… tronqué]" if len(text) > max_chars else "")


@dataclass
class ToolContext:
    memory_facts: Callable[[], str] | None = None
    tasks_status: Callable[[], str] | None = None
    extra: dict[str, Callable[..., str]] = field(default_factory=dict)


TOOL_DESCRIPTIONS = {
    "calc": 'calcul arithmétique — {"tool": "calc", "args": {"expression": "15 % de 240"}}',
    "clipboard": 'contenu du presse-papiers — {"tool": "clipboard"}',
    "read_file": 'lire un fichier texte du dossier personnel — {"tool": "read_file", "args": {"path": "~/notes.md"}}',
    "recall": 'ce que tu sais de l\'utilisateur — {"tool": "recall"}',
    "tasks": 'tâches et agents en cours ou terminés — {"tool": "tasks"}',
}


def run_tool(name: str, args: dict | None, ctx: ToolContext | None = None) -> str:
    args = args or {}
    ctx = ctx or ToolContext()
    try:
        if name == "calc":
            return calc(str(args.get("expression") or args.get("expr") or ""))
        if name == "clipboard":
            return clipboard()
        if name == "read_file":
            return read_file(str(args.get("path") or ""))
        if name == "recall":
            return (ctx.memory_facts() if ctx.memory_facts else "") or "aucun fait mémorisé"
        if name == "tasks":
            return (ctx.tasks_status() if ctx.tasks_status else "") or "aucune tâche"
        if name in ctx.extra:
            return str(ctx.extra[name](**args))
    except Exception as exc:  # noqa: BLE001
        return f"erreur {name} : {exc}"
    return f"outil inconnu : {name}"


def tools_block() -> str:
    return "Outils disponibles (au plus un appel, puis tu décides) :\n" + "\n".join(
        f"- {v}" for v in TOOL_DESCRIPTIONS.values()
    )


def parse_tool_call(data: dict) -> tuple[str, dict] | None:
    name = data.get("tool")
    if not name:
        return None
    args = data.get("args") or data.get("arguments") or {}
    return str(name), args if isinstance(args, dict) else {}


__all__ = [
    "ToolContext",
    "calc",
    "clipboard",
    "read_file",
    "run_tool",
    "tools_block",
    "parse_tool_call",
    "json",
]
