"""Scheme-aware judge: decodes the payload from each argument and picks accordingly.

Phase 2 deliverable — not implemented yet. Per Appendix B, this judge does NOT use an
LLM: it calls `Encoding.decode()` on each argument and majority-votes the decoded
payloads, falling back to the naive judge on disagreement or a None decode.
"""

from __future__ import annotations

from ..interface import DebateTranscript, Encoding, JudgeVerdict


class SchemeAwareJudge:
    def __init__(self, encoding: Encoding, fallback_judge=None) -> None:
        self.encoding = encoding
        self.fallback_judge = fallback_judge

    def judge(self, transcript: DebateTranscript) -> JudgeVerdict:
        raise NotImplementedError("SchemeAwareJudge is a Phase 2 deliverable.")
