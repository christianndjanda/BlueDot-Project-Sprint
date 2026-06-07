"""Acrostic encoding (first letter of each sentence spells a codeword).

Phase 2 deliverable — not implemented yet. See debate_stego_design.md §5.1.
"""

from __future__ import annotations


class AcrosticEncoding:
    name = "acrostic"
    capacity_bits = 8

    def encode_instruction(self, payload: bytes) -> str:
        raise NotImplementedError("AcrosticEncoding is a Phase 2 deliverable.")

    def decode(self, text: str) -> bytes | None:
        raise NotImplementedError("AcrosticEncoding is a Phase 2 deliverable.")
