"""Context-aware paraphraser, ported from Redwood's ContextAwareLlmParaphraser.

Phase 3 deliverable — not implemented yet. Prompt to port verbatim is in
debate_stego_design.md Appendix A.1 (temperature 1.0).
"""

from __future__ import annotations

from ..llm import LLMClient


class ContextAwareParaphraser:
    name = "context_aware"

    def __init__(self, llm: LLMClient, *, model: str = "claude-haiku-4-5") -> None:
        self.llm = llm
        self.model = model

    def rewrite(self, question: str, argument: str) -> str:
        raise NotImplementedError("ContextAwareParaphraser is a Phase 3 deliverable.")
