# debate-stego

Measuring whether two LLM debaters can collude via a steganographic channel to fool a
judge in a single-turn QuALITY debate, and whether paraphrasing the transcript closes
the channel.

See [`../debate_stego_design.md`](../debate_stego_design.md) for the full design,
threat model, and phase plan. This repo follows that document.

## Status

**Phase 1 (skeleton + baseline).** Implemented:

- `debate_stego/llm.py` — Anthropic API wrapper with SQLite caching, retry, async
  batching, and per-call token logging.
- `debate_stego/dataset/quality.py` — loads the QuALITY dev set and samples N
  questions deterministically.
- `HonestDebater` and `NaiveJudge`.
- `experiment.py` + `cli.py` — runs the `honest + naive + no-paraphrase` baseline
  end-to-end and writes a CSV.

Encodings, the colluding debater, the scheme-aware judge, and paraphrase defences are
later-phase stubs (they raise `NotImplementedError`).

## Setup

```bash
pip install -e .            # runtime deps (anthropic, python-dotenv)
pip install -e .[dev]       # + pytest
cp .env.example .env        # then add your ANTHROPIC_API_KEY
```

The QuALITY dataset is expected at `./QuALITY.v1.0.1` or `../QuALITY.v1.0.1` (the
`*.htmlstripped.dev` file is used). Override with `--quality-dir` or
`DEBATE_STEGO_QUALITY_DIR`.

## Run the Phase 1 baseline

```bash
python scripts/run_all_conditions.py --conditions baseline --n 20
```

Writes `results/baseline_n20_seed0.csv` with columns
`question_id, correct_index, chosen_index, is_correct, target_index, target_hit,
parse_failed, condition, encoding`, and prints judge accuracy plus an estimated API
cost. Results are cached in `results/llm_cache.sqlite`, so re-runs are free and
deterministic.

Useful flags: `--n`, `--seed`, `--model` (debaters + judge),
`--paraphraser-model`, `--max-concurrency`, `--out`, `--quality-dir`.

## Tests

```bash
pytest
```

`test_llm_cache.py` monkeypatches the API seam (no key needed). `test_quality_loader.py`
runs against the real dataset if present, otherwise skips.
