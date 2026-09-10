"""Mémoire persistante d'Iris (au-dessus du journal SQLite).

- **faits** : « retiens que mon éditeur est Zed » → injectés dans le prompt du LLM, consultables (« que sais-tu de moi ? ») ;
- **historique de conversation LLM** : survit aux redémarrages ;
- **instantanés de session** : « reprends ma session d'hier ».
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from iris.core.journal import Journal
from iris.nlu.normalize import canonical

_KEY_VALUE = re.compile(r"^(?P<key>[^:=]{2,40}?)\s*(?:[:=]|c'est|est|=)\s+(?P<value>.+)$")


@dataclass
class Fact:
    key: str
    value: str
    source: str
    ts: float

    def sentence(self) -> str:
        return self.value if self.key.startswith("fact:") else f"{self.key} : {self.value}"


class Memory:
    def __init__(self, journal: Journal, max_facts: int = 200) -> None:
        self.journal = journal
        self.max_facts = max_facts

    # ------------------------------------------------------------------ faits
    def remember(self, text: str, source: str = "voice") -> Fact:
        text = text.strip().rstrip(".")
        m = _KEY_VALUE.match(text)
        if m and len(m.group("value")) >= 2 and " " in m.group("key").strip():
            key, value = m.group("key").strip(), m.group("value").strip()
        else:
            key, value = "fact:" + hashlib.sha1(canonical(text).encode()).hexdigest()[:10], text
        fact = Fact(key, value, source, time.time())
        self.journal.set_fact(fact.key, fact.value, fact.source)
        return fact

    def facts(self) -> list[Fact]:
        return [Fact(*row) for row in self.journal.all_facts()][-self.max_facts :]

    def forget(self, query: str) -> Fact | None:
        q = canonical(query)
        best: tuple[float, Fact] | None = None
        for fact in self.facts():
            score = max(
                SequenceMatcher(None, q, canonical(fact.sentence())).ratio(),
                SequenceMatcher(None, q, canonical(fact.key)).ratio(),
                1.0 if q and q in canonical(fact.sentence()) else 0.0,
            )
            if score >= 0.6 and (best is None or score > best[0]):
                best = (score, fact)
        if best is None:
            return None
        self.journal.delete_fact(best[1].key)
        return best[1]

    def forget_all(self) -> int:
        return self.journal.clear_facts()

    def facts_block(self, lang: str = "fr", limit: int = 30) -> str:
        facts = self.facts()[-limit:]
        if not facts:
            return ""
        intro = (
            "Ce que tu sais de l'utilisateur (mémoire) :"
            if lang == "fr"
            else "What you know about the user (memory):"
        )
        return intro + "\n" + "\n".join(f"- {f.sentence()}" for f in facts)

    # ------------------------------------------------------------------ conversation
    def add_turn(self, role: str, content: str) -> None:
        self.journal.add_chat(role, content)

    def history(self, turns: int) -> list[dict[str, str]]:
        return [{"role": r, "content": c} for r, c in self.journal.recent_chat(turns * 2)]

    def clear_history(self) -> None:
        self.journal.clear_chat()
