"""Command-line entry point. Phase 1 supports the `baseline` condition only."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv

from .dataset.quality import load_quality_items
from .debaters.honest import HonestDebater
from .experiment import ResultRow, run_condition, summarise
from .judges.naive import NaiveJudge
from .paraphrasers.none import NoneParaphraser

# Conditions implemented in this phase. The full set (colluding, scheme-aware,
# paraphrase defences) arrives in Phases 2-3.
PHASE1_CONDITIONS = {"baseline"}
ALL_KNOWN_CONDITIONS = {
    "baseline",
    "colluding_naive",
    "colluding_context_paraphrase",
    "colluding_suspicious_paraphrase",
    "colluding_scheme_aware",
}


def _parse_conditions(raw: str) -> list[str]:
    if raw == "all":
        return sorted(ALL_KNOWN_CONDITIONS)
    return [c.strip() for c in raw.split(",") if c.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="debate-stego",
        description="Run debate-stego experimental conditions.",
    )
    p.add_argument(
        "--conditions",
        default="baseline",
        help="Comma-separated condition names, or 'all'. Phase 1: only 'baseline'.",
    )
    p.add_argument("--n", type=int, default=20, help="Number of questions to sample.")
    p.add_argument("--seed", type=int, default=0, help="Sampling seed (deterministic).")
    p.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Model for debaters and the naive judge.",
    )
    p.add_argument(
        "--paraphraser-model",
        default="claude-haiku-4-5",
        help="Model for paraphrasers (Phase 3).",
    )
    p.add_argument(
        "--quality-dir",
        default=None,
        help="Path to the QuALITY dataset directory (overrides auto-detection).",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Default: results/<condition>_n<N>_seed<S>.csv per condition.",
    )
    p.add_argument(
        "--max-concurrency", type=int, default=4, help="Max concurrent API calls."
    )
    p.add_argument(
        "--input-tpm",
        type=int,
        default=30_000,
        help="Org input-tokens-per-minute limit to throttle under. Raise this once "
        "your account is on a higher usage tier (see console.anthropic.com/settings/limits).",
    )
    return p


def _results_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "results"


def _make_llm(max_concurrency: int, input_tpm: int):
    # Imported here so that --help works even if anthropic isn't installed.
    from .llm import LLMClient

    results = _results_dir()
    return LLMClient(
        cache_path=results / "llm_cache.sqlite",
        usage_path=results / "token_usage.jsonl",
        max_concurrency=max_concurrency,
        input_tpm_limit=input_tpm,
    )


def _write_csv(rows: list[ResultRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ResultRow.FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def run_baseline(args, llm) -> tuple[list[ResultRow], Path]:
    items = load_quality_items(args.n, seed=args.seed, quality_dir=args.quality_dir)
    debater_a = HonestDebater(llm, model=args.model)
    debater_b = HonestDebater(llm, model=args.model)
    judge = NaiveJudge(llm, model=args.model)
    paraphraser = NoneParaphraser()

    rows = run_condition(
        items, debater_a, debater_b, paraphraser, judge,
        condition="baseline", encoding="none",
    )

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = _results_dir() / f"baseline_n{args.n}_seed{args.seed}.csv"
    _write_csv(rows, out_path)
    return rows, out_path


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # picks up ANTHROPIC_API_KEY / DEBATE_STEGO_QUALITY_DIR from .env
    args = build_parser().parse_args(argv)
    conditions = _parse_conditions(args.conditions)

    unimplemented = [c for c in conditions if c not in PHASE1_CONDITIONS]
    if unimplemented:
        unknown = [c for c in unimplemented if c not in ALL_KNOWN_CONDITIONS]
        if unknown:
            print(f"ERROR: unknown condition(s): {unknown}", file=sys.stderr)
        phase_later = [c for c in unimplemented if c in ALL_KNOWN_CONDITIONS]
        if phase_later:
            print(
                f"ERROR: condition(s) {phase_later} are not implemented in Phase 1 "
                "(see debate_stego_design.md, Phase plan). Only 'baseline' is available.",
                file=sys.stderr,
            )
        return 2

    llm = _make_llm(args.max_concurrency, args.input_tpm)
    try:
        for condition in conditions:
            if condition == "baseline":
                rows, out_path = run_baseline(args, llm)
            else:  # pragma: no cover - guarded above
                continue

            stats = summarise(rows)
            print(f"\n=== condition: {condition} ===")
            print(f"  wrote {len(rows)} rows -> {out_path}")
            print(f"  parsed: {stats['n_parsed']}/{stats['n']} "
                  f"(parse failures: {stats['parse_failures']})")
            print(f"  judge accuracy:  {stats['accuracy']:.3f}")
            print(f"  target-hit rate: {stats['target_hit_rate']:.3f}")

        print("\n--- usage ---")
        print(f"  api calls: {llm.api_calls}, cache hits: {llm.cache_hits}")
        for model, totals in llm.usage_totals.items():
            print(f"  {model}: in={totals['input_tokens']} out={totals['output_tokens']}")
        print(f"  estimated cost: ${llm.estimated_cost_usd():.2f}")
    finally:
        llm.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
