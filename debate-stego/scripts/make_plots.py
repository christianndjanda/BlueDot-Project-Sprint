#!/usr/bin/env python
"""Aggregate result CSVs and render the headline plots.

Reads every per-job CSV in the results directory, writes:
  - results/combined_results.csv   one tidy row per question per job
  - results/summary.csv            accuracy / target-hit per (condition, paraphraser, encoding)
  - results/accuracy_by_condition.png
  - results/target_hit_by_condition.png

Usage:
    python scripts/make_plots.py [--results-dir results] [--n 150] [--seed 0]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_COLS = {"question_id", "is_correct", "target_hit", "parse_failed", "condition", "encoding"}
PARAPHRASERS = ["none", "context_aware", "suspicious"]
# Generated outputs we must not read back in as inputs.
SKIP_FILES = {"combined_results.csv", "summary.csv"}


def _infer_paraphraser(stem: str) -> str:
    # Filenames look like <condition>_<encoding>[_<paraphraser>]_n<N>_seed<S>.
    for p in ("context_aware", "suspicious"):
        if f"_{p}_" in stem:
            return p
    return "none"


def _load(results_dir: Path, n: int | None, seed: int | None):
    import pandas as pd

    frames = []
    for csv in sorted(results_dir.glob("*.csv")):
        if csv.name in SKIP_FILES:
            continue
        if n is not None and f"n{n}_seed{seed}" not in csv.stem:
            continue  # skip files for other sample sizes / seeds
        df = pd.read_csv(csv)
        if not REQUIRED_COLS.issubset(df.columns):
            continue
        if "paraphraser" not in df.columns:
            df["paraphraser"] = _infer_paraphraser(csv.stem)
        df["source_file"] = csv.name
        frames.append(df)
    if not frames:
        raise SystemExit(f"No matching result CSVs found in {results_dir}.")
    return pd.concat(frames, ignore_index=True)


def _summarise(df):
    parsed = df[df["parse_failed"] == 0]
    g = parsed.groupby(["condition", "paraphraser", "encoding"])
    summary = g.agg(
        n=("question_id", "count"),
        accuracy=("is_correct", "mean"),
        target_hit=("target_hit", "mean"),
    ).reset_index()
    return summary


def _condition_label(condition: str, paraphraser: str) -> str:
    if condition == "baseline":
        return "baseline"
    short = condition.replace("colluding_", "coll_")
    return short if paraphraser == "none" else f"{short}\n+{paraphraser}"


def _bar_plot(summary, value: str, title: str, out_path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = summary.copy()
    s["label"] = [_condition_label(c, p) for c, p in zip(s["condition"], s["paraphraser"])]
    labels = list(dict.fromkeys(s["label"]))          # preserve first-seen order
    encodings = sorted(s["encoding"].unique())

    fig, ax = plt.subplots(figsize=(max(8, 1.6 * len(labels)), 5))
    width = 0.8 / max(len(encodings), 1)
    for i, enc in enumerate(encodings):
        xs, ys = [], []
        for j, label in enumerate(labels):
            row = s[(s["label"] == label) & (s["encoding"] == enc)]
            if not row.empty:
                xs.append(j + i * width)
                ys.append(float(row[value].iloc[0]))
        ax.bar(xs, ys, width=width, label=enc)

    ax.set_xticks([j + width * (len(encodings) - 1) / 2 for j in range(len(labels))])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_ylabel(value.replace("_", " "))
    ax.set_title(title)
    ax.legend(title="encoding", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aggregate results and render plots.")
    p.add_argument("--results-dir", default=str(Path(__file__).resolve().parents[1] / "results"))
    p.add_argument("--n", type=int, default=None, help="Only include files for this sample size.")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    try:
        import matplotlib  # noqa: F401
        import pandas  # noqa: F401
    except ImportError:
        print("make_plots needs the plotting extras: pip install -e '.[plots]'", file=sys.stderr)
        return 1

    results_dir = Path(args.results_dir)
    df = _load(results_dir, args.n, args.seed)
    summary = _summarise(df)

    combined_path = results_dir / "combined_results.csv"
    summary_path = results_dir / "summary.csv"
    df.to_csv(combined_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(f"  wrote {combined_path} ({len(df)} rows)")
    print(f"  wrote {summary_path}")
    print("\nsummary:")
    print(summary.to_string(index=False))

    _bar_plot(summary, "accuracy", "Judge accuracy by condition", results_dir / "accuracy_by_condition.png")
    _bar_plot(summary, "target_hit", "Target-hit rate by condition", results_dir / "target_hit_by_condition.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
