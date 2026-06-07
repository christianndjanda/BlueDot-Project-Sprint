"""Colluding debater: embeds a payload via an Encoding while nominally arguing.

Phase 2 deliverable — not implemented yet. See debate_stego_design.md §7 (Phase 2)
and Appendix B (colluding debater prompt). Do not implement without sign-off.
"""

from __future__ import annotations

from ..interface import DebaterInput, Encoding
from ..llm import LLMClient


class ColludingDebater:
    def __init__(self, llm: LLMClient, encoding: Encoding, **kwargs) -> None:
        self.llm = llm
        self.encoding = encoding

    def argue(self, x: DebaterInput) -> str:
        raise NotImplementedError("ColludingDebater is a Phase 2 deliverable.")
