"""STEP 1b: 浸水データを読み込み、時刻別浸水ポリゴン辞書を構築する。"""

import glob
import pickle
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import pyogrio

import config

# KML LineString を Polygon 化するバッファ幅（度; ≈10m）
_KML_BUFFER_DEG = 0.0001

# 時刻別表示色（folium可視化用）
_TIMELINE_COLORS = [
    "#e41a1c", "#ff7f00", "#ffff33", "#4daf4a",
    "#377eb8", "#984ea3", "#a65628", "#f781bf",
]


def load_a31a_gml(gml_dir: str) -> gpd.GeoDataFrame:
    """A31a GML から waterDepth >= しきい値 のポリゴンを抽出して返す。"""
    xml_files = glob.glob(f"{gml_dir}/**/*.xml", recursive=True)
    xml_files = [f for f in xml_files if "META" not in Path(f).name.upper()]

    frames = []
    for path in xml_files:
        try:
            layers = pyogrio.list_layers(path)
            for layer_name, _ in layers:
                gdf = gpd.read_file(path, layer=layer_name, engine="pyogrio")
                if gdf.empty:
                    continue
                depth_col = next(
                    (c for c in gdf.columns if "waterDepth" in c or "waterdepth" in c.lower()),
                    None,
                )
                if depth_col is None:
                    continue
                gdf = gdf[gdf[depth_col].notna()].copy()
                gdf["waterDepth"] = gdf[depth_col].astype(int)
                gdf = gdf[gdf["waterDepth"] >= config.FLOOD_DEPTH_THRESHOLD]
                if not gdf.empty:
                    frames.append(gdf[["waterDepth", "geometry"]])
        except Exception as e:
            print(f"[warn] {Path(path).name}: {e}")

    if not frames:
        raise RuntimeError("A31a GML から浸水ポリゴンを抽出できませんでした")

    a31a = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:6668")
    a31a = a31a.to_crs(config.CRS_JGD2011)
    print(f"[a31a] {len(a31a)} ポリゴン抽出 (waterDepth>={config.FLOOD_DEPTH_THRESHOLD})")
    return a31a


def load_kml_timeline(kml_dir: str) -> dict[str, gpd.GeoDataFrame]:
    """KML 8ファイルをタイムスタンプ順に読み込み、バッファ処理でPolygon化する。"""
    kml_files = sorted(glob.glob(f"{kml_dir}/**/*.kml", recursive=True))
    if len(kml_files) != 8:
        print(f"[warn] KMLファイル数が {len(kml_files)} 件（期待値: 8件）")

    timeline: dict[str, gpd.GeoDataFrame] = {}
    for i, path in enumerate(kml_files):
        ts = config.KML_TIMESTAMPS[i] if i < len(config.KML_TIMESTAMPS) else f"t{i}"
        gdf = None
        for driver in ("KML", "LIBKML"):
            try:
                gdf = gpd.read_file(path, driver=driver, engine="pyogrio")
                break
            except Exception:
                continue
        if gdf is None or gdf.empty:
            print(f"[warn] KML 読み込み失敗またはデータなし: {Path(path).name}")
            continue

        gdf = gdf.to_crs(config.CRS_JGD2011).copy()
        gdf["geometry"] = gdf.geometry.buffer(_KML_BUFFER_DEG)
        gdf = gdf[~gdf.geometry.is_empty]
        timeline[ts] = gdf
        print(f"[kml] {ts}: {len(gdf)} フィーチャ")

    return timeline


def build_flood_polygons(
    a31a: gpd.GeoDataFrame,
    kml_timeline: dict[str, gpd.GeoDataFrame],
) -> dict[str, gpd.GeoDataFrame]:
    """各KML時点と A31a を intersects 判定して時刻別浸水ポリゴンを構築する。"""
    assert a31a.crs.to_epsg() == 6668, f"a31a CRS 不一致: {a31a.crs}"

    flood_dict: dict[str, gpd.GeoDataFrame] = {}
    for ts, kml_gdf in kml_timeline.items():
        assert kml_gdf.crs.to_epsg() == 6668, f"KML CRS 不一致: {kml_gdf.crs}"
        joined = gpd.sjoin(a31a, kml_gdf[["geometry"]], how="inner", predicate="intersects")
        result = a31a.loc[joined.index.unique()].copy()
        flood_dict[ts] = result
        print(f"[flood] {ts}: {len(result)} ポリゴン")

    return flood_dict


def save_flood_polygons(flood_dict: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(flood_dict, f)
    print(f"[save] flood_polygons.pkl -> {path}  ({len(flood_dict)} 時点)")


def visualize_flood_timeline(flood_dict: dict, output_path: str) -> None:
    first_gdf = next(iter(flood_dict.values()))
    center_wgs84 = first_gdf.to_crs(config.CRS_WGS84).geometry.centroid
    center = [center_wgs84.y.mean(), center_wgs84.x.mean()]

    m = folium.Map(location=center, zoom_start=12)
    for i, (ts, gdf) in enumerate(flood_dict.items()):
        color = _TIMELINE_COLORS[i % len(_TIMELINE_COLORS)]
        fg = folium.FeatureGroup(name=ts)
        folium.GeoJson(
            gdf.to_crs(config.CRS_WGS84).__geo_interface__,
            style_function=lambda _, c=color: {
                "fillColor": c, "color": c, "weight": 1, "fillOpacity": 0.4,
            },
        ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl().add_to(m)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    m.save(output_path)
    print(f"[save] flood timeline map -> {output_path}")


if __name__ == "__main__":
    a31a = load_a31a_gml(config.GML_DIR)
    kml_timeline = load_kml_timeline(config.KML_DIR)
    flood_dict = build_flood_polygons(a31a, kml_timeline)
    save_flood_polygons(flood_dict, config.FLOOD_PKL_PATH)
    visualize_flood_timeline(flood_dict, config.FLOOD_MAP_PATH)
    print("STEP 1b 完了")
