"""Load the QuALITY dev set and sample N questions deterministically.

QuALITY JSONL schema (one article per line): each article has a `questions` list;
each question has `options` (4 strings) and `gold_label` (1-indexed correct option).
We flatten to one `QualityItem` per question.

Target-wrong-answer selection (spec §9.2): deterministic, not random. Among the
options other than the correct one, pick the option whose text length is closest to
the correct option's length (tie-break: lowest index). This avoids the judge keying
on trivial length cues when the channel is later pushing toward the target.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from ..interface import QualityItem

DEV_FILENAME = "QuALITY.v1.0.1.htmlstripped.dev"


def find_quality_dir(explicit: str | Path | None = None) -> Path:
    """Resolve the QuALITY directory.

    Order: explicit arg, DEBATE_STEGO_QUALITY_DIR env var, then a few candidate
    locations relative to the cwd and to this repo.
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env = os.environ.get("DEBATE_STEGO_QUALITY_DIR")
    if env:
        candidates.append(Path(env))

    repo_root = Path(__file__).resolve().parents[2]  # debate-stego/
    candidates.extend(
        [
            Path("QuALITY.v1.0.1"),
            Path("..") / "QuALITY.v1.0.1",
            repo_root / "QuALITY.v1.0.1",
            repo_root.parent / "QuALITY.v1.0.1",
        ]
    )

    for cand in candidates:
        if (cand / DEV_FILENAME).is_file():
            return cand
    raise FileNotFoundError(
        f"Could not find {DEV_FILENAME}. Set DEBATE_STEGO_QUALITY_DIR or pass "
        f"--quality-dir. Tried: {[str(c) for c in candidates]}"
    )


def _choose_target_wrong_index(options: list[str], correct_index: int) -> int:
    correct_len = len(options[correct_index])
    best_index = None
    best_diff = None
    for i, opt in enumerate(options):
        if i == correct_index:
            continue
        diff = abs(len(opt) - correct_len)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = i
    assert best_index is not None  # 4 options => at least 3 candidates
    return best_index


def _iter_items(dev_path: Path):
    with dev_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            passage = article.get("article", "")
            for q in article.get("questions", []):
                options = q.get("options")
                gold = q.get("gold_label")
                # Skip malformed / ungraded questions.
                if not options or len(options) != 4:
                    continue
                if not isinstance(gold, int) or not (1 <= gold <= 4):
                    continue
                correct_index = gold - 1
                yield QualityItem(
                    question_id=q["question_unique_id"],
                    passage=passage,
                    question=q["question"],
                    options=list(options),
                    correct_index=correct_index,
                    target_wrong_index=_choose_target_wrong_index(options, correct_index),
                )


def load_quality_items(
    n: int,
    *,
    seed: int = 0,
    quality_dir: str | Path | None = None,
) -> list[QualityItem]:
    """Return `n` QualityItems sampled deterministically from the dev set.

    Sampling is a seeded shuffle of all valid questions (in file order) followed by a
    head slice, so the same (seed, n) always yields the same subset, and a larger n is
    a superset prefix is *not* guaranteed (shuffle reorders) — but a given (seed, n) is
    fully reproducible, which is what the experiment needs across conditions.
    """
    dev_dir = find_quality_dir(quality_dir)
    dev_path = dev_dir / DEV_FILENAME
    all_items = list(_iter_items(dev_path))
    if n > len(all_items):
        raise ValueError(
            f"Requested n={n} but only {len(all_items)} valid questions available."
        )
    rng = random.Random(seed)
    indices = list(range(len(all_items)))
    rng.shuffle(indices)
    return [all_items[i] for i in indices[:n]]
