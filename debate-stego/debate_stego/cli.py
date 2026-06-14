"""Command-line entry point.

Conditions (base = debaters + judge):
  baseline                honest debaters + naive judge
  colluding_naive         colluding debaters + naive judge
  colluding_scheme_aware  colluding debaters + scheme-aware judge (naive fallback)

The paraphraser is an orthogonal axis (`--paraphraser`): none | context_aware |
suspicious, applied between the debate and the judge. The design doc's five headline
conditions are these base conditions crossed with the paraphraser; e.g.
  colluding_naive        --paraphraser context_aware   (incidental defence)
  colluding_naive        --paraphraser suspicious       (deliberate defence)
  colluding_scheme_aware --paraphraser suspicious       (Phase 3 channel-degradation
                                                         diagnostic)
The paraphraser is ignored for `baseline`.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv

from .dataset.quality import load_quality_items
from .debaters.colluding import ColludingDebater
from .debaters.honest import HonestDebater
from .encodings.acrostic import AcrosticEncoding
from .encodings.marker_word import MarkerWordEncoding
from .encodings.sentence_count import SentenceCountEncoding
from .experiment import ResultRow, run_condition, summarise
from .interface import index_to_letter
from .judges.naive import NaiveJudge
from .judges.scheme_aware import SchemeAwareJudge
from .paraphrasers.context_aware import ContextAwareParaphraser
from .paraphrasers.none import NoneParaphraser
from .paraphrasers.suspicious import SuspiciousParaphraser

ENCODINGS = {
    "acrostic": AcrosticEncoding,
    "marker_word": MarkerWordEncoding,
    "sentence_count": SentenceCountEncoding,
}

PARAPHRASERS = ["none", "context_aware", "suspicious"]

IMPLEMENTED_CONDITIONS = {"baseline", "colluding_naive", "colluding_scheme_aware"}
COLLUDING_CONDITIONS = {"colluding_naive", "colluding_scheme_aware"}


def _parse_list(raw: str, all_values: list[str]) -> list[str]:
    if raw == "all":
        return list(all_values)
    return [x.strip() for x in raw.split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="debate-stego",
        description="Run debate-stego experimental conditions.",
    )
    p.add_argument(
        "--conditions",
        default="baseline",
        help="Comma-separated condition names, or 'all'. One of: "
        + ", ".join(sorted(IMPLEMENTED_CONDITIONS)),
    )
    p.add_argument(
        "--encoding",
        default="acrostic",
        help="Encoding(s) for colluding conditions: comma-separated or 'all'. "
        "One of: " + ", ".join(ENCODINGS) + ". Ignored for baseline.",
    )
    p.add_argument(
        "--paraphraser",
        default="none",
        help="Paraphraser(s) applied before the judge: comma-separated or 'all'. "
        "One of: " + ", ".join(PARAPHRASERS) + ". Ignored for baseline.",
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
        help="Model for the paraphrasers.",
    )
    p.add_argument(
        "--quality-dir",
        default=None,
        help="Path to the QuALITY dataset directory (overrides auto-detection).",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output CSV path (only valid for a single job). "
        "Default: results/<condition>[_<encoding>][_<paraphraser>]_n<N>_seed<S>.csv.",
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


def _target_payload(item) -> bytes:
    # Both colluding debaters embed the target wrong answer's letter.
    return index_to_letter(item.target_wrong_index).encode("ascii")


def _build_paraphraser(name: str, args, llm):
    if name == "none":
        return NoneParaphraser()
    if name == "context_aware":
        return ContextAwareParaphraser(llm, model=args.paraphraser_model)
    if name == "suspicious":
        return SuspiciousParaphraser(llm, model=args.paraphraser_model)
    raise ValueError(f"unknown paraphraser: {name}")


def _run_job(args, llm, condition, encoding_name, paraphraser_name, out):
    """Run one (condition, encoding, paraphraser) job and write its CSV."""
    items = load_quality_items(args.n, seed=args.seed, quality_dir=args.quality_dir)
    paraphraser = _build_paraphraser(paraphraser_name, args, llm)

    if condition == "baseline":
        debater_a = HonestDebater(llm, model=args.model)
        debater_b = HonestDebater(llm, model=args.model)
        judge = NaiveJudge(llm, model=args.model)
        rows = run_condition(
            items, debater_a, debater_b, paraphraser, judge,
            condition=condition, encoding="none", paraphraser_name=paraphraser_name,
        )
        default_name = f"baseline_n{args.n}_seed{args.seed}.csv"
    else:  # colluding_naive | colluding_scheme_aware
        enc = ENCODINGS[encoding_name]()
        debater_a = ColludingDebater(llm, enc, model=args.model)
        debater_b = ColludingDebater(llm, enc, model=args.model)
        naive = NaiveJudge(llm, model=args.model)
        judge = (
            SchemeAwareJudge(enc, fallback_judge=naive)
            if condition == "colluding_scheme_aware"
            else naive
        )
        rows = run_condition(
            items, debater_a, debater_b, paraphraser, judge,
            condition=condition, encoding=encoding_name,
            paraphraser_name=paraphraser_name, payload_fn=_target_payload,
        )
        parts = [condition, encoding_name]
        if paraphraser_name != "none":
            parts.append(paraphraser_name)
        default_name = "_".join(parts) + f"_n{args.n}_seed{args.seed}.csv"

    out_path = out if out is not None else _results_dir() / default_name
    _write_csv(rows, out_path)
    return rows, out_path


def _build_jobs(conditions, encodings, paraphrasers) -> list[tuple[str, str, str]]:
    jobs: list[tuple[str, str, str]] = []
    for condition in conditions:
        if condition in COLLUDING_CONDITIONS:
            for enc in encodings:
                for para in paraphrasers:
                    jobs.append((condition, enc, para))
        else:  # baseline: encoding/paraphraser don't apply
            jobs.append((condition, "none", "none"))
    return jobs


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # picks up ANTHROPIC_API_KEY / DEBATE_STEGO_QUALITY_DIR from .env
    args = build_parser().parse_args(argv)
    conditions = _parse_list(args.conditions, sorted(IMPLEMENTED_CONDITIONS))
    encodings = _parse_list(args.encoding, list(ENCODINGS))
    paraphrasers = _parse_list(args.paraphraser, PARAPHRASERS)

    unknown = [c for c in conditions if c not in IMPLEMENTED_CONDITIONS]
    if unknown:
        print(f"ERROR: unknown condition(s): {unknown}. Implemented: "
              + ", ".join(sorted(IMPLEMENTED_CONDITIONS)), file=sys.stderr)
        return 2

    if any(c in COLLUDING_CONDITIONS for c in conditions):
        bad_enc = [e for e in encodings if e not in ENCODINGS]
        if bad_enc:
            print(f"ERROR: unknown encoding(s): {bad_enc}. "
                  f"Choose from: {', '.join(ENCODINGS)} or 'all'.", file=sys.stderr)
            return 2
        bad_par = [p for p in paraphrasers if p not in PARAPHRASERS]
        if bad_par:
            print(f"ERROR: unknown paraphraser(s): {bad_par}. "
                  f"Choose from: {', '.join(PARAPHRASERS)} or 'all'.", file=sys.stderr)
            return 2

    jobs = _build_jobs(conditions, encodings, paraphrasers)
    if args.out is not None and len(jobs) > 1:
        print("ERROR: --out is only valid for a single job; "
              f"this invocation expands to {len(jobs)} jobs.", file=sys.stderr)
        return 2

    llm = _make_llm(args.max_concurrency, args.input_tpm)
    try:
        for condition, encoding_name, paraphraser_name in jobs:
            rows, out_path = _run_job(
                args, llm, condition, encoding_name, paraphraser_name,
                out=Path(args.out) if args.out else None,
            )
            stats = summarise(rows)
            if condition == "baseline":
                label = "baseline"
            else:
                label = f"{condition} [{encoding_name}]"
                if paraphraser_name != "none":
                    label += f" + {paraphraser_name}"
            print(f"\n=== condition: {label} ===")
            print(f"  wrote {len(rows)} rows -> {out_path}")
            print(f"  parsed: {stats['n_parsed']}/{stats['n']} "
                  f"(parse failures: {stats['parse_failures']})")
            print(f"  judge accuracy:  {stats['accuracy']:.3f}")
            print(f"  target-hit rate: {stats['target_hit_rate']:.3f}")

        print("\n--- usage ---")
        print(f"  api calls: {llm.api_calls}, sqlite cache hits: {llm.cache_hits}")
        for model, totals in llm.usage_totals.items():
            print(f"  {model}: in={totals['input_tokens']} out={totals['output_tokens']} "
                  f"cache_write={totals['cache_creation_input_tokens']} "
                  f"cache_read={totals['cache_read_input_tokens']}")
        created, read = llm.cache_token_totals()
        print(f"  prompt-cache: wrote {created} / read {read} input tokens")
        print(f"  estimated cost: ${llm.estimated_cost_usd():.2f}")
    finally:
        llm.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
