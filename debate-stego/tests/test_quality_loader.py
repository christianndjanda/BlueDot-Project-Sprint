"""Tests for the QuALITY loader. Skipped if the dataset isn't present."""

from __future__ import annotations

import pytest

from debate_stego.dataset.quality import (
    _choose_target_wrong_index,
    find_quality_dir,
    load_quality_items,
)


def _dataset_available() -> bool:
    try:
        find_quality_dir()
        return True
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not _dataset_available(), reason="QuALITY dataset not found"
)


def test_loads_requested_count():
    items = load_quality_items(20, seed=0)
    assert len(items) == 20


def test_items_are_well_formed():
    for item in load_quality_items(20, seed=0):
        assert len(item.options) == 4
        assert 0 <= item.correct_index <= 3
        assert 0 <= item.target_wrong_index <= 3
        assert item.target_wrong_index != item.correct_index
        assert item.question_id
        assert item.passage
        assert item.question


def test_sampling_is_deterministic():
    a = load_quality_items(15, seed=42)
    b = load_quality_items(15, seed=42)
    assert [i.question_id for i in a] == [i.question_id for i in b]


def test_different_seeds_differ():
    a = load_quality_items(30, seed=1)
    b = load_quality_items(30, seed=2)
    assert [i.question_id for i in a] != [i.question_id for i in b]


def test_target_wrong_index_picks_closest_length():
    # correct = index 0 ("aaaa", len 4); closest-length wrong option is index 2 ("bbbb").
    options = ["aaaa", "z", "bbbb", "zz"]
    assert _choose_target_wrong_index(options, correct_index=0) == 2


def test_target_wrong_index_tie_breaks_low():
    # Two wrong options equidistant in length -> lowest index wins.
    options = ["aa", "bb", "cc", "z"]
    assert _choose_target_wrong_index(options, correct_index=0) == 1
