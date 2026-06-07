"""Shared base for encodings.

The canonical `Encoding` Protocol lives in `debate_stego.interface`. Concrete
encodings (acrostic, marker_word, sentence_count) are Phase 2 deliverables. This
module is a placeholder so the package layout matches the design doc; add shared
encoding helpers here when Phase 2 begins.
"""

from __future__ import annotations

from ..interface import Encoding  # re-exported for convenience

__all__ = ["Encoding"]
