"""Tests for the LLM cache. The API call seam is monkeypatched, so no key needed."""

from __future__ import annotations

import asyncio
import json

from debate_stego.llm import LLMClient


def _usage(in_tok=10, out_tok=5, creation=0, read=0):
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cache_creation_input_tokens": creation,
        "cache_read_input_tokens": read,
    }


def _make_client(tmp_path, counter):
    llm = LLMClient(
        cache_path=tmp_path / "cache.sqlite",
        usage_path=tmp_path / "usage.jsonl",
    )

    def fake_sync(model, system, user, temperature, max_tokens, cache_system=False):
        counter["calls"] += 1
        return (f"resp:{model}:{user}", _usage())

    llm._call_api_sync = fake_sync  # type: ignore[method-assign]
    return llm


def test_cache_hit_avoids_second_api_call(tmp_path):
    counter = {"calls": 0}
    llm = _make_client(tmp_path, counter)
    try:
        r1 = llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
        r2 = llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
        assert r1 == r2
        assert counter["calls"] == 1
        assert llm.cache_hits == 1
        assert llm.api_calls == 1
    finally:
        llm.close()


def test_different_args_miss_cache(tmp_path):
    counter = {"calls": 0}
    llm = _make_client(tmp_path, counter)
    try:
        llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
        llm.complete("claude-sonnet-4-6", "sys", "world", temperature=0.0, max_tokens=64)
        llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.5, max_tokens=64)
        assert counter["calls"] == 3
    finally:
        llm.close()


def test_usage_is_logged_per_api_call(tmp_path):
    counter = {"calls": 0}
    llm = _make_client(tmp_path, counter)
    try:
        llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
        llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)  # cached
        lines = (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1  # only the real call is logged
        rec = json.loads(lines[0])
        assert rec["model"] == "claude-sonnet-4-6"
        assert rec["input_tokens"] == 10
        assert rec["output_tokens"] == 5
    finally:
        llm.close()


def test_persistence_across_instances(tmp_path):
    counter = {"calls": 0}
    llm = _make_client(tmp_path, counter)
    llm.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
    llm.close()

    # New client, same cache file: should hit cache without calling the API.
    counter2 = {"calls": 0}
    llm2 = _make_client(tmp_path, counter2)
    try:
        llm2.complete("claude-sonnet-4-6", "sys", "hello", temperature=0.0, max_tokens=64)
        assert counter2["calls"] == 0
        assert llm2.cache_hits == 1
    finally:
        llm2.close()


def test_acomplete_survives_multiple_event_loops(tmp_path):
    # Each run_condition() uses its own asyncio.run(); the loop-bound semaphore/lock
    # must be rebound per loop or the 2nd job crashes ("different event loop").
    counter = {"calls": 0}
    llm = LLMClient(cache_path=tmp_path / "c.sqlite", usage_path=tmp_path / "u.jsonl")

    async def fake_async(model, system, user, temperature, max_tokens, cache_system=False):
        counter["calls"] += 1
        return (f"r:{user}", _usage(5, 1))

    llm._call_api_async = fake_async  # type: ignore[method-assign]
    try:
        asyncio.run(llm.acomplete("m", "s", "u1", temperature=0.0, max_tokens=8))
        asyncio.run(llm.acomplete("m", "s", "u2", temperature=0.0, max_tokens=8))
        assert counter["calls"] == 2
    finally:
        llm.close()


def test_async_cache_hit(tmp_path):
    counter = {"calls": 0}
    llm = LLMClient(cache_path=tmp_path / "c.sqlite", usage_path=tmp_path / "u.jsonl")

    async def fake_async(model, system, user, temperature, max_tokens, cache_system=False):
        counter["calls"] += 1
        return (f"resp:{user}", _usage(7, 3))

    llm._call_api_async = fake_async  # type: ignore[method-assign]

    async def run():
        a = await llm.acomplete("claude-sonnet-4-6", "s", "x", temperature=0.0, max_tokens=16)
        b = await llm.acomplete("claude-sonnet-4-6", "s", "x", temperature=0.0, max_tokens=16)
        return a, b

    try:
        a, b = asyncio.run(run())
        assert a == b
        assert counter["calls"] == 1
    finally:
        llm.close()
