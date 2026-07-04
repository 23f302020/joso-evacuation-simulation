"""T4 車両会計テスト（P0）。

full_vehicle_count / ten_percent_vehicle_count は Phase2 の車両数（＝公平性の分母）を
決める。allocate_integer_counts は Phase3 救出車両数の整数割当（最大剰余法）。

重複実装（p2_derived_data と p2_region_pipeline）の同値性も検証（設計書 §2.2）。
"""
from __future__ import annotations

import pandas as pd
import pytest

from p2_derived_data import full_vehicle_count, ten_percent_vehicle_count
from p2_region_pipeline import (
    allocate_integer_counts,
    full_vehicle_count as full_region,
    ten_percent_vehicle_count as ten_region,
)


# full_vehicle_count = max(1, ceil(pop/2.3))、pop<=0 -> 0（実装式から検証済み）
@pytest.mark.parametrize(
    "pop,expected",
    [(0, 0), (-1, 0), (1, 1), (2, 1), (3, 2), (23, 10), (100, 44)],
)
def test_full_vehicle_count(pop, expected):
    assert full_vehicle_count(pop) == expected


@pytest.mark.parametrize(
    "n,expected",
    [(0, 0), (1, 1), (10, 1), (11, 2)],
)
def test_ten_percent_vehicle_count(n, expected):
    assert ten_percent_vehicle_count(n) == expected


@pytest.mark.parametrize("pop", [0, 1, 2, 3, 23, 100, 999])
def test_full_vehicle_count_duplicate_implementations_agree(pop):
    """derived版 と region版 の重複実装が同値（ドリフト検出）。"""
    assert full_vehicle_count(pop) == full_region(pop)


@pytest.mark.parametrize("n", [0, 1, 10, 11, 100])
def test_ten_percent_duplicate_implementations_agree(n):
    assert ten_percent_vehicle_count(n) == ten_region(n)


def test_full_vehicle_count_never_negative():
    """人口がどうであれ車両数は非負（不変条件）。"""
    for pop in range(-10, 200):
        assert full_vehicle_count(pop) >= 0


# --- allocate_integer_counts（最大剰余法） ---------------------------------
def test_allocate_integer_counts_sum_equals_target():
    """target >= Σfloor のとき、割当の合計は target に一致する。"""
    raw = pd.Series([1.4, 1.4, 1.2])
    result = allocate_integer_counts(raw, target_total=4)
    assert sum(result) == 4
    # 各値は floor 以上
    assert all(r >= int(v) for r, v in zip(result, raw))


def test_allocate_integer_counts_each_at_least_floor():
    raw = pd.Series([2.9, 0.1, 0.1])
    result = allocate_integer_counts(raw, target_total=4)
    assert result[0] >= 2
    assert sum(result) == 4


def test_allocate_integer_counts_target_below_floor_sum_is_documented():
    """target < Σfloor のとき floors のまま返り、合計が target を超える（仕様固定）。

    設計書 §4-T4 参照。この挙動は現状の実装仕様であり、
    Phase3で救出車両数を扱う際にこの前提が変わらないことを保証する。
    """
    raw = pd.Series([2.0, 2.0, 2.0])  # Σfloor = 6
    result = allocate_integer_counts(raw, target_total=3)
    assert sum(result) == 6  # target=3 を超える（floorsのまま）
