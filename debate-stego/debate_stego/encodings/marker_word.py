"""Marker-word encoding (presence of a pre-agreed marker word per answer letter).

Phase 2 deliverable — not implemented yet. See debate_stego_design.md §5.2.
"""

from __future__ import annotations


class MarkerWordEncoding:
    name = "marker_word"
    capacity_bits = 2

    def encode_instruction(self, payload: bytes) -> str:
        raise NotImplementedError("MarkerWordEncoding is a Phase 2 deliverable.")

    def decode(self, text: str) -> bytes | None:
        raise NotImplementedError("MarkerWordEncoding is a Phase 2 deliverable.")
