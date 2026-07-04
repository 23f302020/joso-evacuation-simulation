"""T5 エージェント4分類テスト（P0）。

allocate_agent_types は住民を Type1〜4 に分類する（公平性指標の母集団）。
  Type1: 車あり×非高齢   Type2: 車あり×高齢
  Type3: 車なし×非高齢   Type4: 車なし×高齢（バス優先対象）

卒論の公平性議論の土台であり、分類の総和保存が最重要の不変条件。
"""
from __future__ import annotations

import pandas as pd
import pytest

from p2_phase3_prep_agents import allocate_agent_types


def _row(total_pop, elderly_pop):
    return pd.Series({"total_pop": total_pop, "elderly_pop": elderly_pop})


def test_allocate_agent_types_typical_case():
    """total=100, elderly=27 → 4分類の総和が100（NON_CAR_RATE=0.15）。"""
    r = allocate_agent_types(_row(100, 27))
    # type4 = round(27*0.15)=4, type2 = 27-4=23
    # type3 = round(73*0.15)=11, type1 = 73-11=62
    assert r["type4_no_car_elderly_pop"] == 4
    assert r["type2_car_elderly_pop"] == 23
    assert r["type3_no_car_non_elderly_pop"] == 11
    assert r["type1_car_non_elderly_pop"] == 62
    total = (
        r["type1_car_non_elderly_pop"] + r["type2_car_elderly_pop"]
        + r["type3_no_car_non_elderly_pop"] + r["type4_no_car_elderly_pop"]
    )
    assert total == 100


@pytest.mark.parametrize("total,elderly", [(100, 27), (0, 0), (50, 50), (200, 1), (1, 1)])
def test_agent_types_sum_preserved_when_elderly_le_total(total, elderly):
    """elderly <= total の正常データでは 4分類の総和 == total_pop（不変条件）。"""
    r = allocate_agent_types(_row(total, elderly))
    four = (
        r["type1_car_non_elderly_pop"] + r["type2_car_elderly_pop"]
        + r["type3_no_car_non_elderly_pop"] + r["type4_no_car_elderly_pop"]
    )
    assert four == total


def test_agent_types_zero_population():
    r = allocate_agent_types(_row(0, 0))
    for key in (
        "type1_car_non_elderly_pop", "type2_car_elderly_pop",
        "type3_no_car_non_elderly_pop", "type4_no_car_elderly_pop",
    ):
        assert r[key] == 0


@pytest.mark.parametrize("total,elderly", [(100, 27), (50, 50), (200, 30), (0, 0)])
def test_agent_types_non_negative_and_priority_subset(total, elderly):
    """全分類は非負、かつ bus_priority <= bus_candidate（不変条件）。"""
    r = allocate_agent_types(_row(total, elderly))
    for v in r.values():
        assert v >= 0
    assert r["bus_priority_population"] <= r["bus_candidate_population"]


def test_agent_types_elderly_exceeds_total_clamps_non_elderly():
    """elderly > total（データ異常）では non_elderly が0にクランプされる。

    この場合 4分類の総和 == total は保証されない。異常入力の挙動を仕様として固定。
    """
    r = allocate_agent_types(_row(10, 15))
    assert r["non_elderly_pop"] == 0
    assert r["type1_car_non_elderly_pop"] == 0
    assert r["type3_no_car_non_elderly_pop"] == 0
