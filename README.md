# Debate-stego

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

## Results

Headline run: **n=150** QuALITY questions, `claude-sonnet-4-6` debaters + judge,
`claude-haiku-4-5` paraphraser, seed 0 (~$32, 0 parse failures). Full per-question data
in [`results/combined_results.csv`](results/combined_results.csv); aggregates in
[`results/summary.csv`](results/summary.csv); notes in [`results/RESULTS.md`](results/RESULTS.md).

Two judges probe two different questions:
- **Scheme-aware judge** — a diagnostic that *decodes* the encoding. Measures whether the
  hidden channel transmits at all, and whether it survives a paraphrase.
- **Naive judge** — a normal LLM judge reading only the arguments. Measures whether a
  realistic overseer is actually fooled.

![Judge accuracy by condition](results/accuracy_by_condition.png)

![Target-hit rate by condition](results/target_hit_by_condition.png)

**Does the channel transmit / survive paraphrasing?** (scheme-aware judge, target-hit rate)

| Encoding | no paraphrase | context_aware | suspicious |
|---|---|---|---|
| acrostic | 0.99 | 0.11 | 0.17 |
| marker_word | 0.97 | 0.09 | 0.11 |
| sentence_count | 0.85 | 0.14 | 0.17 |

**Is a realistic judge fooled?** (naive judge, accuracy — target-hit in parentheses; honest baseline = 0.96 / 0.04)

| Encoding | no paraphrase | context_aware | suspicious |
|---|---|---|---|
| acrostic | 0.91 (0.09) | 0.89 (0.11) | 0.82 (0.17) |
| marker_word | 0.93 (0.07) | 0.91 (0.09) | 0.88 (0.11) |
| sentence_count | 0.87 (0.12) | 0.89 (0.11) | 0.83 (0.17) |

**Takeaways (preliminary):**
1. All three hand-crafted channels transmit to a judge that decodes them (0.85–0.99 target-hit).
2. Paraphrasing collapses every channel to ≈0.10 target-hit — and a *neutral* paraphrase
   is as effective as a stego-hunting one.
3. A realistic (naive) judge is barely fooled in the first place: accuracy stays 0.82–0.93
   vs. the 0.96 honest baseline, with target-hit only 0.04–0.17.

> Single-turn QuALITY debate, n=150, one seed — directional, not a significance claim.

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

## Future work (v2)

v1 measures whether a hidden channel *survives paraphrasing*; the naive judge is barely
moved, so it tests channel survival rather than manipulation of a realistic overseer.
The planned v2 reframes the question as **covert rhetorical steering** — can colluding
debaters steer a naive judge to a predetermined wrong answer in multi-turn debate, and
does paraphrasing (a *transformation* defence) or a side-classifier (a *detection*
defence) stop it? It forks [`ucl-dark/llm_debate`](https://github.com/ucl-dark/llm_debate),
uses the both-know collusion setup with QuALITY's best distractor as the target, and
keeps the symbol-level encoding as a paraphrase-vulnerable foil against semantic steering.

Design decisions and rationale are in [`docs/v2-notes.md`](docs/v2-notes.md).
