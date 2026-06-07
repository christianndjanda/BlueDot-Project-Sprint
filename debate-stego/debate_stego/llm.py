"""Anthropic API wrapper: SQLite caching, retry, async batching, token logging.

Design notes (from the spec):
- Single `complete(model, system, user, **kwargs) -> str` entry point.
- SQLite cache keyed on (model, system, user, temperature, max_tokens). Cache hits
  return instantly and cost nothing.
- Retries: we lean on the `anthropic` SDK's built-in exponential backoff for 429/5xx.
- Concurrency: asyncio + a semaphore (default 8) via `complete_batch`.
- Every real API call is appended to `results/token_usage.jsonl`.

No custom prompt-templating system: callers pass plain strings built with f-strings.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import anthropic

# Approximate USD prices per 1M tokens (input, output). Used only for the cost
# estimate printed at the end of a run; not load-bearing for results.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def _cache_key(model: str, system: str, user: str, temperature: float, max_tokens: int) -> str:
    blob = json.dumps(
        [model, system, user, temperature, max_tokens],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _extract_text(message: Any) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


class LLMClient:
    """Caching wrapper around the Anthropic SDK with sync and async entry points.

    The underlying SDK clients are created lazily so that constructing an LLMClient
    (and serving pure cache hits) does not require ANTHROPIC_API_KEY to be set.
    """

    def __init__(
        self,
        cache_path: str | Path,
        usage_path: str | Path,
        *,
        max_concurrency: int = 4,
        max_retries: int = 8,
        input_tpm_limit: int = 30_000,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.usage_path = Path(usage_path)
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        # Proactive throttle: stay under the org's input-tokens-per-minute limit so we
        # pace ourselves instead of relying solely on 429 retries. Entry-tier Sonnet is
        # 30k TPM; raise via --input-tpm once the account is on a higher usage tier.
        self.input_tpm_limit = input_tpm_limit

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.cache_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response TEXT NOT NULL)"
        )
        self._conn.commit()

        self._client: anthropic.Anthropic | None = None
        self._aclient: anthropic.AsyncAnthropic | None = None
        self._sem = None  # created on first async use, bound to the running loop

        # Rolling 60s window of (monotonic_ts, reserved_input_tokens) for the throttle.
        self._rate_window: deque[tuple[float, int]] = deque()
        self._rate_used = 0
        self._rate_lock = None  # asyncio.Lock, created on first async use

        # In-memory running totals for the end-of-run cost estimate.
        self.usage_totals: dict[str, dict[str, int]] = {}
        self.cache_hits = 0
        self.api_calls = 0

    # -- lazy SDK clients --------------------------------------------------

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=self.max_retries)
        return self._client

    @property
    def aclient(self) -> anthropic.AsyncAnthropic:
        if self._aclient is None:
            self._aclient = anthropic.AsyncAnthropic(max_retries=self.max_retries)
        return self._aclient

    # -- cache + logging ---------------------------------------------------

    def _cache_get(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT response FROM cache WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def _cache_put(self, key: str, response: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, response) VALUES (?, ?)",
                (key, response),
            )
            self._conn.commit()

    def _log_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        record = {
            "ts": time.time(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        with self._lock:
            with self.usage_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
            totals = self.usage_totals.setdefault(
                model, {"input_tokens": 0, "output_tokens": 0}
            )
            totals["input_tokens"] += input_tokens
            totals["output_tokens"] += output_tokens
            self.api_calls += 1

    # -- API call seams (monkeypatched in tests) ---------------------------

    def _call_api_sync(
        self, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(message), message.usage.input_tokens, message.usage.output_tokens

    async def _call_api_async(
        self, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        message = await self.aclient.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(message), message.usage.input_tokens, message.usage.output_tokens

    # -- rate throttle -----------------------------------------------------

    @staticmethod
    def _estimate_input_tokens(system: str, user: str) -> int:
        # Deliberately conservative (chars/3.5 over-estimates vs the real ~chars/4),
        # so we reserve a little more than we'll actually spend and stay under the cap.
        return int((len(system) + len(user)) / 3.5) + 16

    async def _throttle(self, est_tokens: int) -> None:
        """Block until reserving `est_tokens` keeps the 60s window under the limit.

        Holds the lock across the wait so admission is strictly serialized (one
        reservation resolves at a time) — this is the pacing we want. A single call
        larger than the budget is always admitted (we can't split it); the SDK's 429
        retry is the backstop for that case and for estimate error.
        """
        import asyncio

        if self._rate_lock is None:
            self._rate_lock = asyncio.Lock()
        budget = self.input_tpm_limit * 0.9  # headroom for estimate error
        async with self._rate_lock:
            while True:
                now = time.monotonic()
                while self._rate_window and now - self._rate_window[0][0] >= 60:
                    self._rate_used -= self._rate_window.popleft()[1]
                if not self._rate_window or self._rate_used + est_tokens <= budget:
                    self._rate_window.append((now, est_tokens))
                    self._rate_used += est_tokens
                    return
                sleep_for = 60 - (now - self._rate_window[0][0]) + 0.05
                await asyncio.sleep(max(sleep_for, 0.05))

    # -- public entry points ----------------------------------------------

    def complete(
        self,
        model: str,
        system: str,
        user: str,
        *,
        temperature: float = 1.0,
        max_tokens: int = 1024,
    ) -> str:
        key = _cache_key(model, system, user, temperature, max_tokens)
        cached = self._cache_get(key)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
            return cached

        text, in_tok, out_tok = self._call_api_sync(
            model, system, user, temperature, max_tokens
        )
        self._log_usage(model, in_tok, out_tok)
        self._cache_put(key, text)
        return text

    async def acomplete(
        self,
        model: str,
        system: str,
        user: str,
        *,
        temperature: float = 1.0,
        max_tokens: int = 1024,
    ) -> str:
        import asyncio

        if self._sem is None:
            self._sem = asyncio.Semaphore(self.max_concurrency)

        key = _cache_key(model, system, user, temperature, max_tokens)
        cached = self._cache_get(key)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
            return cached

        await self._throttle(self._estimate_input_tokens(system, user))
        async with self._sem:
            text, in_tok, out_tok = await self._call_api_async(
                model, system, user, temperature, max_tokens
            )
        self._log_usage(model, in_tok, out_tok)
        self._cache_put(key, text)
        return text

    async def complete_batch(self, prompts: list[dict[str, Any]]) -> list[str]:
        """Run many completions concurrently (bounded by the semaphore).

        Each prompt dict accepts the same keys as `acomplete`:
        {"model", "system", "user", "temperature"?, "max_tokens"?}.
        """
        import asyncio

        return await asyncio.gather(*(self.acomplete(**p) for p in prompts))

    # -- cost reporting ----------------------------------------------------

    def estimated_cost_usd(self) -> float:
        total = 0.0
        for model, totals in self.usage_totals.items():
            in_price, out_price = PRICES_PER_MTOK.get(model, (0.0, 0.0))
            total += totals["input_tokens"] / 1e6 * in_price
            total += totals["output_tokens"] / 1e6 * out_price
        return total

    def close(self) -> None:
        with self._lock:
            self._conn.close()
