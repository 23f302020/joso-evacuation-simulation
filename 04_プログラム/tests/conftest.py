"""pytest共通設定・fixture。

- scripts/ を import 可能にする（sys.path挿入）
- 実出力ディレクトリの解決と存在判定
- 空間系テスト用の小規模GeoDataFrameファクトリ

詳細は tests/テスト設計書.md を参照。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# --- scripts/ を import 可能にする ---------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _TESTS_DIR.parent            # 04_プログラム/
_SCRIPTS_DIR = _PROGRAM_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_OUTPUT_DIR = _PROGRAM_DIR / "output"


# --- 出力ディレクトリ関連 -------------------------------------------------
@pytest.fixture(scope="session")
def program_dir() -> Path:
    return _PROGRAM_DIR


@pytest.fixture(scope="session")
def output_dir() -> Path:
    """実出力ディレクトリ。存在しない環境では回帰テストをskipするために使う。"""
    return _OUTPUT_DIR


def require_output(relative_path: str) -> Path:
    """実出力ファイルのPathを返す。無ければ pytest.skip。

    41市区町村フル実行の成果物が無い環境（他PC・クリーンクローン）でも
    テストスイート全体が落ちないようにするためのガード。
    """
    path = _OUTPUT_DIR / relative_path
    if not path.exists():
        pytest.skip(f"実出力が存在しないためskip: {relative_path}")
    return path


# --- 空間系fixture --------------------------------------------------------
@pytest.fixture
def flood_cell_factory():
    """(中心lon, lat, 一辺メートル) から正方形浸水ポリゴンGeoDataFrameを返すファクトリ。

    EPSG:6690（メートル基準）で正方形を作ってから EPSG:6668(JGD2011) に変換するため、
    「道路から29m/31m」のような距離を正確に作為できる。
    """
    import geopandas as gpd
    from shapely.geometry import box

    def _make(center_lon: float, center_lat: float, side_m: float = 250.0):
        # まず経緯度点を投影座標(メートル)へ
        pt = gpd.GeoSeries(
            gpd.points_from_xy([center_lon], [center_lat]), crs="EPSG:6668"
        ).to_crs("EPSG:6690")
        x, y = pt.iloc[0].x, pt.iloc[0].y
        half = side_m / 2.0
        cell = box(x - half, y - half, x + half, y + half)
        gdf = gpd.GeoDataFrame(geometry=[cell], crs="EPSG:6690").to_crs("EPSG:6668")
        return gdf

    return _make
