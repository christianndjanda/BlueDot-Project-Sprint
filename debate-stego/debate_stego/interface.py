"""Core data structures and Protocols shared across the pipeline.

Structural typing (Protocol) is used deliberately: a new debater/judge/encoding can
be dropped in without inheritance ceremony. Concrete classes may add extra methods
(e.g. async variants) beyond what the Protocol names.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol

# Answer-option index <-> letter helpers, used wherever we render options to a model.
LETTERS = ["A", "B", "C", "D"]


def index_to_letter(index: int) -> str:
    return LETTERS[index]


def letter_to_index(letter: str) -> int:
    return LETTERS.index(letter.strip().upper())


class QualityItem(NamedTuple):
    question_id: str
    passage: str
    question: str
    options: list[str]          # length 4
    correct_index: int          # 0..3
    target_wrong_index: int     # 0..3, != correct_index; chosen deterministically


class DebaterInput(NamedTuple):
    item: QualityItem
    assigned_index: int         # which answer this debater argues for
    payload: bytes | None       # the bits to embed; None for honest debaters


class DebateTranscript(NamedTuple):
    item: QualityItem
    arguments: list[str]        # length 4, one per option index;
                                # only the two debated indices are non-empty


class JudgeVerdict(NamedTuple):
    chosen_index: int | None    # None if the judge's choice could not be parsed
    reasoning: str


class Encoding(Protocol):
    name: str
    capacity_bits: int

    def encode_instruction(self, payload: bytes) -> str: ...

    def decode(self, text: str) -> bytes | None: ...


class Debater(Protocol):
    def argue(self, x: DebaterInput) -> str: ...


class Judge(Protocol):
    def judge(self, transcript: DebateTranscript) -> JudgeVerdict: ...


class Paraphraser(Protocol):
    name: str

    def rewrite(self, question: str, argument: str) -> str: ...
