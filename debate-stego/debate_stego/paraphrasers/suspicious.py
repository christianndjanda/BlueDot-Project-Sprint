"""Suspicious paraphraser, ported from Redwood's .very_suspicious() variant.

Phase 3 deliverable — not implemented yet. Prompt to port verbatim is in
debate_stego_design.md Appendix A.2 (temperature 0).
"""

from __future__ import annotations

from ..llm import LLMClient


class SuspiciousParaphraser:
    name = "suspicious"

    def __init__(self, llm: LLMClient, *, model: str = "claude-haiku-4-5") -> None:
        self.llm = llm
        self.model = model

    def rewrite(self, question: str, argument: str) -> str:
        raise NotImplementedError("SuspiciousParaphraser is a Phase 3 deliverable.")
