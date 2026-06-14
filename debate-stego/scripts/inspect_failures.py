#!/usr/bin/env python
"""Print transcripts where the judge was fooled.

Deferred v1 helper — intentionally not implemented. The result CSVs record verdicts
(question_id, chosen_index, is_correct, target_hit, ...) but not the argument text, so
inspecting *why* a judge was fooled would require re-deriving each transcript from the
LLM cache (results/llm_cache.sqlite) by rebuilding the debater prompts. That work is out
of scope for v1; the canonical analysis dataset is results/combined_results.csv.

To implement later: load combined_results.csv, filter to fooled cases
(is_correct == 0, typically target_hit == 1), and for each rebuild the debater prompts
(debaters/common.py:context_system + the debater USER_TEMPLATE) to fetch the cached
arguments, then print them alongside the verdict.
"""

import sys


def main() -> int:
    print(
        "inspect_failures.py is a deferred v1 helper and is not implemented yet. "
        "See the module docstring; analyse results/combined_results.csv directly.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
