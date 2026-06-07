"""Sentence-count encoding (number of sentences mod 4 encodes 2 bits).

Phase 2 deliverable — not implemented yet. See debate_stego_design.md §5.3.
"""

from __future__ import annotations


class SentenceCountEncoding:
    name = "sentence_count"
    capacity_bits = 2

    def encode_instruction(self, payload: bytes) -> str:
        raise NotImplementedError("SentenceCountEncoding is a Phase 2 deliverable.")

    def decode(self, text: str) -> bytes | None:
        raise NotImplementedError("SentenceCountEncoding is a Phase 2 deliverable.")
