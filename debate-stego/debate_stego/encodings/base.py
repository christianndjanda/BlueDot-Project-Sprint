"""Shared helpers for encodings.

The canonical `Encoding` Protocol lives in `debate_stego.interface`. This module
holds payload helpers and a sentence splitter used by the acrostic and
sentence-count encodings.

v1 payloads are the target answer letter as bytes: b"A".."D" (2 bits, which-of-4).
"""

from __future__ import annotations

import re

from ..interface import LETTERS, Encoding

__all__ = [
    "Encoding",
    "PAYLOAD_LETTERS",
    "validate_payload",
    "payload_letter",
    "letter_to_payload",
    "split_sentences",
    "first_alpha_upper",
]

PAYLOAD_LETTERS = [b"A", b"B", b"C", b"D"]

_FALLBACK_SPLIT = re.compile(r"(?<=[.!?])\s+")


def validate_payload(payload: bytes) -> None:
    if payload not in PAYLOAD_LETTERS:
        raise ValueError(f"payload must be one of {PAYLOAD_LETTERS}, got {payload!r}")


def payload_letter(payload: bytes) -> str:
    validate_payload(payload)
    return payload.decode("ascii")


def letter_to_payload(letter: str) -> bytes:
    payload = letter.strip().upper().encode("ascii")
    validate_payload(payload)
    return payload


def split_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Uses nltk.sent_tokenize (per the design doc) when available, downloading the
    tokenizer data on first use if needed; falls back to a regex splitter so that
    round-trip tests run offline without the nltk data.
    """
    text = text.strip()
    if not text:
        return []
    try:
        import nltk

        try:
            return [s for s in nltk.sent_tokenize(text) if s.strip()]
        except LookupError:
            for pkg in ("punkt_tab", "punkt"):
                try:
                    nltk.download(pkg, quiet=True)
                except Exception:
                    pass
            try:
                return [s for s in nltk.sent_tokenize(text) if s.strip()]
            except LookupError:
                pass
    except ImportError:
        pass
    return [s for s in _FALLBACK_SPLIT.split(text) if s.strip()]


def first_alpha_upper(sentence: str) -> str | None:
    for ch in sentence:
        if ch.isalpha():
            return ch.upper()
    return None
