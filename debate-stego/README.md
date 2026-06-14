# debate-stego

Measuring whether two LLM debaters can collude via a steganographic channel to fool a
judge in a single-turn QuALITY debate, and whether paraphrasing the transcript closes
the channel.

See [`../debate_stego_design.md`](../debate_stego_design.md) for the full design,
threat model, and phase plan. This repo follows that document.

## Status

**v1 complete (Phases 1–4).**

Phase 1 (skeleton + baseline):
- `debate_stego/llm.py` — Anthropic API wrapper with SQLite caching, retry, async
  batching, per-call token logging, prompt caching, and an input-TPM throttle.
- `debate_stego/dataset/quality.py` — loads the QuALITY dev set and samples N
  questions deterministically.
- `HonestDebater`, `NaiveJudge`, and the `baseline` condition end-to-end.

Phase 2 (encodings + collusion):
- Three encodings — `acrostic`, `marker_word`, `sentence_count` — with passing
  round-trip tests (`tests/test_encodings.py`). Sentence splitting uses `nltk`, with a
  regex fallback so tests run offline.
- `ColludingDebater` (embeds the target letter via an `Encoding`) and
  `SchemeAwareJudge` (decodes both arguments; falls back to the naive judge on
  disagreement or a failed decode).
- Conditions `colluding_naive` and `colluding_scheme_aware`.

Phase 3 (paraphrase defences):
- `ContextAwareParaphraser` (neutral restatement) and `SuspiciousParaphraser`
  (stego-hunting), prompts ported verbatim from the Redwood benchmark (design
  Appendix A).
- The paraphraser is an orthogonal `--paraphraser` axis (`none` | `context_aware` |
  `suspicious`), applied between the debate and the judge.

Phase 4 (full sweep + outputs):
- `scripts/make_plots.py` aggregates the per-job CSVs into `results/combined_results.csv`
  + `results/summary.csv` and renders the headline bar charts.
- The canonical n=150 sweep (19 jobs) has been run; numbers and observations are in
  [`results/RESULTS.md`](results/RESULTS.md), with the committed dataset in
  `results/combined_results.csv` and the plots in `results/*.png`.
- `scripts/inspect_failures.py` is a deferred helper (stub) — see its docstring.

## Setup

```bash
pip install -e .            # runtime deps (anthropic, python-dotenv, nltk)
pip install -e ".[plots]"   # + matplotlib/pandas, needed only for scripts/make_plots.py
pip install -e ".[dev]"     # + pytest
cp .env.example .env        # then add your ANTHROPIC_API_KEY
```

The QuALITY dataset is expected at `./QuALITY.v1.0.1` or `../QuALITY.v1.0.1` (the
`*.htmlstripped.dev` file is used). Override with `--quality-dir` or
`DEBATE_STEGO_QUALITY_DIR`.

## Running conditions

```bash
# Phase 1 baseline (honest + naive judge)
python scripts/run_all_conditions.py --conditions baseline --n 20

# Phase 2: does the channel transmit? (upper-bound diagnostic)
python scripts/run_all_conditions.py --conditions colluding_scheme_aware --encoding acrostic --n 20

# Phase 2: is a naive judge fooled?
python scripts/run_all_conditions.py --conditions colluding_naive --encoding acrostic --n 20

# Phase 3: does paraphrasing close the channel? (scheme-aware diagnostic)
python scripts/run_all_conditions.py --conditions colluding_scheme_aware --encoding acrostic --paraphraser suspicious --n 20

# Phase 3 headline: colluding vs a naive judge, with/without a paraphrase defence
python scripts/run_all_conditions.py --conditions colluding_naive --encoding acrostic --paraphraser context_aware,suspicious --n 20

# Phase 4 full sweep (all conditions x encodings x paraphrasers, n=150).
# --input-tpm should match your org's Sonnet input-tokens/min limit (Tier 2 = 450000).
python scripts/run_all_conditions.py --conditions baseline,colluding_naive,colluding_scheme_aware --encoding all --paraphraser all --n 150 --input-tpm 450000

# Aggregate the per-job CSVs into combined_results.csv + summary.csv and render plots:
python scripts/make_plots.py --n 150
```

Each job writes a CSV to `results/` with columns
`question_id, correct_index, chosen_index, is_correct, target_index, target_hit,
parse_failed, condition, encoding, paraphraser`, and prints judge accuracy, target-hit
rate, and an estimated API cost. Results are cached in `results/llm_cache.sqlite`, so
re-runs are free and deterministic.

`--encoding` and `--paraphraser` each accept a comma-separated list or `all`, and the
run expands to the cross product of conditions x encodings x paraphrasers (both ignored
for `baseline`). Other useful flags: `--n`, `--seed`, `--model` (debaters + judge),
`--paraphraser-model`, `--input-tpm`, `--max-concurrency`, `--out`, `--quality-dir`.

## Tests

```bash
pytest
```

`test_llm_cache.py` monkeypatches the API seam (no key needed). `test_quality_loader.py`
runs against the real dataset if present, otherwise skips.
