"""
Context engine: loads the user's domain docs (resume, product sheet, objection
playbook, CRM notes) and maintains a rolling transcript window so the LLM has
just enough recent conversation + just enough background — without blowing the
latency/token budget.

The whole pitch of a live copilot is HERE, not in the LLM call:
relevant context + tight window = fast, on-point suggestions.
"""

from __future__ import annotations
import os
import glob
import time
from collections import deque
from typing import Deque, List
from providers import Transcript


class ContextEngine:
    def __init__(self, context_dir: str, window_turns: int = 8, max_ctx_chars: int = 6000):
        self.context_dir = context_dir
        self.window_turns = window_turns
        self.max_ctx_chars = max_ctx_chars
        self.turns: Deque[str] = deque(maxlen=window_turns)
        self.docs = self._load_docs()

    def _load_docs(self) -> str:
        """Concatenate all .md/.txt context docs, truncated to the budget."""
        parts: List[str] = []
        for path in sorted(glob.glob(os.path.join(self.context_dir, "*.md")) +
                           glob.glob(os.path.join(self.context_dir, "*.txt"))):
            base = os.path.basename(path)
            if base.startswith("demo_call"):
                continue  # that's the mock STT script, not a context doc
            with open(path, "r", encoding="utf-8") as f:
                parts.append(f"## {base}\n{f.read().strip()}")
        blob = "\n\n".join(parts)
        if len(blob) > self.max_ctx_chars:
            # naive truncation; a real version would embed + retrieve top-k
            blob = blob[: self.max_ctx_chars] + "\n...[context truncated]"
        return blob or "(no context docs loaded)"

    def add(self, t: Transcript) -> None:
        if t.is_final and t.text.strip():
            tag = "THEM" if t.speaker == "them" else "ME"
            self.turns.append(f"{tag}: {t.text.strip()}")

    def transcript_window(self) -> str:
        return "\n".join(self.turns)

    def should_trigger(self, t: Transcript) -> bool:
        """
        Trigger a suggestion only when THEY finished a turn that looks like it
        wants a response (a question, an objection cue, or a longish statement).
        Avoids spamming a suggestion on every word -> saves tokens + cognitive load.
        """
        if not t.is_final or t.speaker != "them":
            return False
        text = t.text.strip().lower()
        if not text:
            return False
        if text.endswith("?"):
            return True
        cues = ("but ", "however", "worried", "concern", "expensive", "competitor",
                "not sure", "think about", "why ", "how ", "what about", "vs ",
                "too much", "already use", "budget")
        if any(c in text for c in cues):
            return True
        return len(text.split()) >= 12  # substantial statement
