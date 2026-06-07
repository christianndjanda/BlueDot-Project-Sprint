#!/usr/bin/env python
"""Run experimental conditions and write per-condition CSVs to results/.

Phase 1: only `--conditions baseline` is implemented.

Acceptance test (Phase 1):
    python scripts/run_all_conditions.py --conditions baseline --n 20

Thin wrapper around debate_stego.cli so the package needn't be pip-installed to run
the script from the repo root.
"""

import sys
from pathlib import Path

# Allow running directly (python scripts/run_all_conditions.py) without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from debate_stego.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
