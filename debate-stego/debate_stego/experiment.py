"""Single-condition runner.

A condition is: a pair of debaters (one for the correct option, one for the target
wrong option), an optional paraphrase step, and a judge. Phase 1 implements the
"baseline" condition only (honest debaters + naive judge + identity paraphraser).
The runner is async so debate/judge calls fan out across items, bounded by the
LLMClient semaphore.

Data flow per item (design doc Appendix C):
  DebaterA(assigned=correct)      -> arg_A  (slot correct_index)
  DebaterB(assigned=target_wrong) -> arg_B  (slot target_wrong_index)
  arguments -> Paraphraser.rewrite (or identity) -> DebateTranscript -> Judge -> verdict
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .interface import DebaterInput, DebateTranscript, QualityItem


@dataclass
class ResultRow:
    question_id: str
    correct_index: int
    chosen_index: int | None
    is_correct: bool
    target_index: int
    target_hit: bool
    parse_failed: bool
    condition: str
    encoding: str

    # Column order for the output CSV. The first four are the spec-required columns.
    FIELDS = [
        "question_id",
        "correct_index",
        "chosen_index",
        "is_correct",
        "target_index",
        "target_hit",
        "parse_failed",
        "condition",
        "encoding",
    ]

    def as_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "correct_index": self.correct_index,
            "chosen_index": "" if self.chosen_index is None else self.chosen_index,
            "is_correct": int(self.is_correct),
            "target_index": self.target_index,
            "target_hit": int(self.target_hit),
            "parse_failed": int(self.parse_failed),
            "condition": self.condition,
            "encoding": self.encoding,
        }


async def _run_item(
    item: QualityItem,
    debater_a,
    debater_b,
    paraphraser,
    judge,
    *,
    condition: str,
    encoding: str,
) -> ResultRow:
    arg_a, arg_b = await asyncio.gather(
        debater_a.aargue(DebaterInput(item, item.correct_index, None)),
        debater_b.aargue(DebaterInput(item, item.target_wrong_index, None)),
    )

    arguments = ["", "", "", ""]
    arguments[item.correct_index] = arg_a
    arguments[item.target_wrong_index] = arg_b

    # Paraphrase the two non-empty arguments (identity for the baseline condition).
    paraphrased = list(arguments)
    for i, arg in enumerate(arguments):
        if arg:
            paraphrased[i] = await paraphraser.arewrite(item.question, arg)

    transcript = DebateTranscript(item, paraphrased)
    verdict = await judge.ajudge(transcript)

    chosen = verdict.chosen_index
    parse_failed = chosen is None
    return ResultRow(
        question_id=item.question_id,
        correct_index=item.correct_index,
        chosen_index=chosen,
        is_correct=(chosen == item.correct_index),
        target_index=item.target_wrong_index,
        target_hit=(chosen == item.target_wrong_index),
        parse_failed=parse_failed,
        condition=condition,
        encoding=encoding,
    )


async def run_condition_async(
    items: list[QualityItem],
    debater_a,
    debater_b,
    paraphraser,
    judge,
    *,
    condition: str,
    encoding: str = "none",
) -> list[ResultRow]:
    tasks = [
        _run_item(
            item, debater_a, debater_b, paraphraser, judge,
            condition=condition, encoding=encoding,
        )
        for item in items
    ]
    return await asyncio.gather(*tasks)


def run_condition(
    items: list[QualityItem],
    debater_a,
    debater_b,
    paraphraser,
    judge,
    *,
    condition: str,
    encoding: str = "none",
) -> list[ResultRow]:
    return asyncio.run(
        run_condition_async(
            items, debater_a, debater_b, paraphraser, judge,
            condition=condition, encoding=encoding,
        )
    )


def summarise(rows: list[ResultRow]) -> dict:
    """Accuracy over parsed verdicts; target-hit rate; parse-failure count."""
    parsed = [r for r in rows if not r.parse_failed]
    n_parsed = len(parsed)
    n_correct = sum(1 for r in parsed if r.is_correct)
    n_target = sum(1 for r in parsed if r.target_hit)
    return {
        "n": len(rows),
        "n_parsed": n_parsed,
        "parse_failures": len(rows) - n_parsed,
        "accuracy": (n_correct / n_parsed) if n_parsed else float("nan"),
        "target_hit_rate": (n_target / n_parsed) if n_parsed else float("nan"),
    }
