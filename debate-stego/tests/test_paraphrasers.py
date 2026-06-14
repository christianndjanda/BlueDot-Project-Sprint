"""Offline tests for the paraphrasers: prompt construction and the rewrite call.

The LLM is stubbed (a fake with a `complete`/`acomplete` seam), so no API key needed.
Whether a real paraphraser actually degrades a channel is a runtime concern measured
in the Phase 3 acceptance run.
"""

from __future__ import annotations

import asyncio

from debate_stego.paraphrasers.context_aware import ContextAwareParaphraser
from debate_stego.paraphrasers.none import NoneParaphraser
from debate_stego.paraphrasers.suspicious import SuspiciousParaphraser

QUESTION = "What is the narrator's main motivation?"
ARGUMENT = "The narrator is driven by guilt, as shown throughout the passage."


class _FakeLLM:
    """Captures the (system, user) it was called with and echoes a marker."""

    def __init__(self) -> None:
        self.system = None
        self.user = None

    def complete(self, model, system, user, *, temperature, max_tokens):
        self.system, self.user = system, user
        return "PARAPHRASED"

    async def acomplete(self, model, system, user, *, temperature, max_tokens):
        self.system, self.user = system, user
        return "PARAPHRASED_ASYNC"


def test_none_paraphraser_is_identity():
    p = NoneParaphraser()
    assert p.rewrite(QUESTION, ARGUMENT) == ARGUMENT
    assert asyncio.run(p.arewrite(QUESTION, ARGUMENT)) == ARGUMENT


def test_context_aware_prompt_and_rewrite():
    llm = _FakeLLM()
    p = ContextAwareParaphraser(llm)
    out = p.rewrite(QUESTION, ARGUMENT)
    assert out == "PARAPHRASED"
    assert QUESTION in llm.system          # question embedded in the system prompt
    assert "paraphrase" in llm.system.lower()
    assert llm.user == ARGUMENT            # argument is the user message
    assert "steganograph" not in llm.system.lower()  # neutral, not the suspicious one


def test_suspicious_prompt_mentions_hidden_messages():
    llm = _FakeLLM()
    p = SuspiciousParaphraser(llm)
    out = p.rewrite(QUESTION, ARGUMENT)
    assert out == "PARAPHRASED"
    assert QUESTION in llm.system
    assert "steganograph" in llm.system.lower()
    assert "suspicious" in llm.system.lower()


def test_suspicious_temperature_is_zero():
    # Appendix A.2 specifies temperature 0 for the suspicious variant.
    assert SuspiciousParaphraser(_FakeLLM()).temperature == 0.0
    assert ContextAwareParaphraser(_FakeLLM()).temperature == 1.0


def test_async_rewrite_paths():
    llm = _FakeLLM()
    p = SuspiciousParaphraser(llm)
    assert asyncio.run(p.arewrite(QUESTION, ARGUMENT)) == "PARAPHRASED_ASYNC"
    assert QUESTION in llm.system
