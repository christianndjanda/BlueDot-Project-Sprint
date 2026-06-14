"""Round-trip tests for the three encodings, plus scheme-aware judge / colluding
debater offline checks.

Round-trip uses hand-crafted compliant text (not LLM output): decode(compliant) must
recover the payload. Whether the LLM actually produces compliant text is a runtime
concern measured in the Phase 2 acceptance run, not here.
"""

from __future__ import annotations

import pytest

from debate_stego.encodings.acrostic import AcrosticEncoding
from debate_stego.encodings.marker_word import MARKERS, MarkerWordEncoding
from debate_stego.encodings.sentence_count import SentenceCountEncoding
from debate_stego.interface import DebateTranscript, JudgeVerdict, QualityItem

PAYLOADS = [b"A", b"B", b"C", b"D"]


# -- acrostic ----------------------------------------------------------------

def test_roundtrip_acrostic():
    enc = AcrosticEncoding()
    for payload in PAYLOADS:
        letter = payload.decode()
        text = " ".join(f"{letter}aa is a supporting sentence." for _ in range(4))
        assert enc.encode_instruction(payload)  # non-empty instruction
        assert enc.decode(text) == payload


def test_acrostic_ignores_trailing_sentences():
    enc = AcrosticEncoding()
    text = "Bbb one. Bbb two. Bbb three. Bbb four. Zzz trailing. Qqq more."
    assert enc.decode(text) == b"B"


def test_acrostic_redundancy_tolerates_one_flip():
    enc = AcrosticEncoding()
    # Three A initials, one stray B among the first four -> majority A.
    text = "Apples align. Also true. Again it holds. Bbb stray."
    assert enc.decode(text) == b"A"


def test_acrostic_ambiguous_returns_none():
    enc = AcrosticEncoding()
    assert enc.decode("Aaa. Bbb. Ccc. Ddd.") is None


def test_acrostic_empty_returns_none():
    assert AcrosticEncoding().decode("") is None


# -- marker word -------------------------------------------------------------

def test_roundtrip_marker_word():
    enc = MarkerWordEncoding()
    for payload in PAYLOADS:
        word = MARKERS[payload.decode()]
        text = f"The evidence is strong. {word.capitalize()}, the conclusion follows."
        assert enc.encode_instruction(payload)
        assert enc.decode(text) == payload


def test_marker_word_argmax_wins():
    enc = MarkerWordEncoding()
    # furthermore twice, notably once -> B wins.
    text = "Furthermore this. Furthermore that. Notably a stray."
    assert enc.decode(text) == b"B"


def test_marker_word_none_when_absent():
    assert MarkerWordEncoding().decode("Plain prose with no discourse markers.") is None


def test_marker_word_tie_returns_none():
    enc = MarkerWordEncoding()
    assert enc.decode("Moreover this. Furthermore that.") is None


# -- sentence count ----------------------------------------------------------

def test_roundtrip_sentence_count():
    enc = SentenceCountEncoding()
    for payload in PAYLOADS:
        n = enc.target_count(payload.decode())
        text = " ".join("Word here." for _ in range(n))
        assert enc.encode_instruction(payload)
        assert enc.decode(text) == payload


def test_sentence_count_mapping():
    enc = SentenceCountEncoding()
    # target_count must satisfy count % 4 == index of the letter.
    for i, payload in enumerate(PAYLOADS):
        assert enc.target_count(payload.decode()) % 4 == i


def test_sentence_count_empty_returns_none():
    assert SentenceCountEncoding().decode("") is None


# -- scheme-aware judge (offline) -------------------------------------------

def _item() -> QualityItem:
    return QualityItem(
        question_id="q1",
        passage="p",
        question="Which?",
        options=["w", "x", "y", "z"],
        correct_index=0,
        target_wrong_index=1,
    )


class _StubJudge:
    """Records whether it was consulted and returns a fixed verdict."""

    def __init__(self, idx: int) -> None:
        self.idx = idx
        self.called = False

    def judge(self, transcript):
        self.called = True
        return JudgeVerdict(self.idx, "fallback")


def _transcript(arg_correct: str, arg_target: str) -> DebateTranscript:
    args = ["", "", "", ""]
    args[0] = arg_correct       # correct_index
    args[1] = arg_target        # target_wrong_index
    return DebateTranscript(_item(), args)


def test_scheme_aware_decodes_when_debaters_agree():
    from debate_stego.judges.scheme_aware import SchemeAwareJudge

    enc = AcrosticEncoding()
    # Both arguments encode "B" (target index 1).
    arg = " ".join("Bbb supporting point." for _ in range(4))
    fallback = _StubJudge(99)
    judge = SchemeAwareJudge(enc, fallback_judge=fallback)
    verdict = judge.judge(_transcript(arg, arg))
    assert verdict.chosen_index == 1
    assert fallback.called is False


def test_scheme_aware_falls_back_on_disagreement():
    from debate_stego.judges.scheme_aware import SchemeAwareJudge

    enc = AcrosticEncoding()
    arg_a = " ".join("Aaa point." for _ in range(4))  # decodes A
    arg_b = " ".join("Bbb point." for _ in range(4))  # decodes B
    fallback = _StubJudge(2)
    judge = SchemeAwareJudge(enc, fallback_judge=fallback)
    verdict = judge.judge(_transcript(arg_a, arg_b))
    assert verdict.chosen_index == 2
    assert fallback.called is True


def test_scheme_aware_falls_back_on_none_decode():
    from debate_stego.judges.scheme_aware import SchemeAwareJudge

    enc = AcrosticEncoding()
    arg_a = " ".join("Bbb point." for _ in range(4))  # decodes B
    arg_b = "Aaa. Bbb. Ccc. Ddd."                     # ambiguous -> None
    fallback = _StubJudge(3)
    judge = SchemeAwareJudge(enc, fallback_judge=fallback)
    verdict = judge.judge(_transcript(arg_a, arg_b))
    assert verdict.chosen_index == 3
    assert fallback.called is True


# -- colluding debater prompt (offline) -------------------------------------

def test_colluding_prompt_embeds_target_and_instruction():
    from debate_stego.debaters.colluding import ColludingDebater
    from debate_stego.interface import DebaterInput

    enc = MarkerWordEncoding()
    deb = ColludingDebater(llm=None, encoding=enc)  # _prompt doesn't touch llm
    # assigned = option A (index 0), target payload = C
    x = DebaterInput(_item(), assigned_index=0, payload=b"C")
    system, user = deb._prompt(x)
    # Per-debater instructions live in the user message...
    assert "option A" in user            # assigned
    assert "option C" in user            # target letter
    assert MARKERS["C"] in user          # the encoding instruction's marker word
    # ...and the shared passage lives in the cacheable system prompt.
    assert "PASSAGE:" in system


def test_colluding_requires_payload():
    from debate_stego.debaters.colluding import ColludingDebater
    from debate_stego.interface import DebaterInput

    deb = ColludingDebater(llm=None, encoding=AcrosticEncoding())
    with pytest.raises(ValueError):
        deb._prompt(DebaterInput(_item(), assigned_index=0, payload=None))
