"""鬼怒川の OSM データを取得し JS ファイルとして出力する。

出力:
    output/unified/assets/kinugawa_river.js     (統合ページ用)
    output/scenario_cities/kinugawa_river.js    (市区町村別ページ共有)

使い方:
    python _gen_kinugawa_river.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import mapping

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

# 鬼怒川が流れる広域 bbox (west, south, east, north)
# 茨城・栃木南部を含む範囲
_BBOX = (139.5, 35.5, 140.6, 37.1)


def _load_modules():
    try:
        import osmnx as ox
        import geopandas as gpd
        return ox, gpd
    except ImportError as e:
        print(f"[ERROR] {e} → venv を有効化してください", file=sys.stderr)
        sys.exit(1)


def fetch_kinugawa_geojson() -> dict:
    ox, gpd = _load_modules()

    print("[fetch] OSM から鬼怒川データを取得中 ...")
    gdf = None

    # bbox フェッチを試みる (osmnx 2.x: (west, south, east, north))
    try:
        gdf = ox.features_from_bbox(
            bbox=_BBOX,
            tags={"waterway": ["river", "riverbank"]},
        )
    except Exception as e:
        print(f"[WARN] bbox fetch 失敗: {e}", file=sys.stderr)

    # フォールバック: 常総市周辺を place で取得
    if gdf is None or gdf.empty:
        print("[fetch] フォールバック: 常総市周辺から取得中 ...")
        gdfs = []
        for place in ["常総市, 茨城県, 日本", "筑西市, 茨城県, 日本", "結城市, 茨城県, 日本"]:
            try:
                g = ox.features_from_place(place, tags={"waterway": ["river", "riverbank"]})
                if not g.empty:
                    gdfs.append(g)
            except Exception:
                pass
        if gdfs:
            import pandas as pd
            gdf = pd.concat(gdfs)
        else:
            raise RuntimeError("OSM からデータを取得できませんでした")

    # 鬼怒川でフィルタ
    name_col = "name" if "name" in gdf.columns else None
    if name_col:
        kinugawa = gdf[gdf[name_col].fillna("").str.contains("鬼怒川", na=False)].copy()
    else:
        kinugawa = gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs)

    if kinugawa.empty:
        print("[WARN] 名前フィルタで 0 件 → waterway=river 全件を使用")
        if "waterway" in gdf.columns:
            kinugawa = gdf[gdf["waterway"] == "river"].copy()
        else:
            kinugawa = gdf.copy()

    if kinugawa.empty:
        raise RuntimeError("鬼怒川データが見つかりませんでした")

    print(f"[ok] {len(kinugawa)} フィーチャー取得 (types: {kinugawa.geometry.geom_type.unique().tolist()})")

    kinugawa = kinugawa.to_crs("EPSG:4326")
    union_geom = kinugawa.geometry.union_all().simplify(0.00008, preserve_topology=True)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "鬼怒川"},
                "geometry": mapping(union_geom),
            }
        ],
    }


def write_js(geojson: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "window.KINUGAWA_RIVER = "
        + json.dumps(geojson, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    out_path.write_text(content, encoding="utf-8")
    print(f"[write] {out_path}  ({len(content):,} bytes)")


def main() -> None:
    geojson = fetch_kinugawa_geojson()

    unified_out = OUTPUT_DIR / "unified" / "assets" / "kinugawa_river.js"
    cities_out  = OUTPUT_DIR / "scenario_cities" / "kinugawa_river.js"

    write_js(geojson, unified_out)
    write_js(geojson, cities_out)
    print("\n完了: kinugawa_river.js を生成しました")
    print(f"  {unified_out}")
    print(f"  {cities_out}")


if __name__ == "__main__":
    main()
