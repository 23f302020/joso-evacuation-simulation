"""T3 メッシュコード変換テスト（P0）。

meshcode_to_lon_lat は決定論的な純関数で、10桁地域メッシュコードを
中心経緯度へ変換する。卒論の出発地座標の基礎。

重要：i3_route_search と p2_region_pipeline に同一実装が重複しているため、
両者の同値性を検証してドリフト事故を防ぐ（テスト設計書 §2.2）。
"""
from __future__ import annotations

import pytest

from i3_route_search import meshcode_to_lon_lat as mesh_joso
from p2_region_pipeline import meshcode_to_lon_lat as mesh_region


# 既知値（実装式から算出・検証済み）
KNOWN = [
    ("5439071000", 139.8765625, 36.009375),
    ("5439171000", 139.8765625, 36.09270833333333),
]


@pytest.mark.parametrize("key,exp_lon,exp_lat", KNOWN)
def test_meshcode_known_values(key, exp_lon, exp_lat):
    lon, lat = mesh_joso(key)
    assert lon == pytest.approx(exp_lon, abs=1e-9)
    assert lat == pytest.approx(exp_lat, abs=1e-9)


def test_meshcode_nine_digit_is_zfilled():
    """9桁入力は zfill(10) で解釈される（先頭0補完）。"""
    assert mesh_joso("439071000") == mesh_joso("0439071000")


@pytest.mark.parametrize("key,_lon,_lat", KNOWN)
def test_meshcode_within_joso_bbox(key, _lon, _lat):
    """常総市域(543907/543917帯)の中心は想定BBOX内に収まる。"""
    lon, lat = mesh_joso(key)
    assert 139.8 < lon < 140.2, f"lon={lon} がBBOX外"
    assert 36.0 <= lat < 36.3, f"lat={lat} がBBOX外"


@pytest.mark.parametrize("key,_lon,_lat", KNOWN)
def test_meshcode_duplicate_implementations_agree(key, _lon, _lat):
    """i3版 と region版 の重複実装が同値であること（ドリフト検出）。"""
    assert mesh_joso(key) == mesh_region(key)
