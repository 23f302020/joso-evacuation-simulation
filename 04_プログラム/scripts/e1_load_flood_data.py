"""コンフリクト解消済み。STEP 1b: 浸水データ読み込みと時系列浸水ポリゴン生成。"""

from __future__ import annotations

import pickle
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import pyogrio

import config


def ensure_output_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _find_files(dir_path: str, suffix: str) -> list[Path]:
    return sorted([p for p in Path(dir_path).glob(f"*{suffix}") if p.is_file()])


def _pick_layer(path: Path) -> str | None:
    layers = pyogrio.list_layers(path)
    if layers is None or len(layers) == 0:
        return None
    return str(layers[0][0])


def load_a31a_gml(gml_dir: str) -> gpd.GeoDataFrame:
    gml_files = _find_files(gml_dir, ".gml")
    if not gml_files:
        raise FileNotFoundError(f"GML files not found: {gml_dir}")

    frames: list[gpd.GeoDataFrame] = []
    for gml_path in gml_files:
        layer = _pick_layer(gml_path)
        gdf = gpd.read_file(gml_path, layer=layer, engine="pyogrio")
        frames.append(gdf)

    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)
    wd_col = next((c for c in merged.columns if "waterDepth" in c), None)
    if wd_col is None:
        raise KeyError("waterDepth attribute not found in A31a GML")

    merged[wd_col] = pd.to_numeric(merged[wd_col], errors="coerce")
    filtered = merged[merged[wd_col] >= config.FLOOD_DEPTH_THRESHOLD].copy()
    filtered = filtered.to_crs(config.CRS_JGD2011)
    return filtered


def _read_kml(path: Path) -> gpd.GeoDataFrame:
    try:
        return gpd.read_file(path, driver="KML", engine="pyogrio")
    except Exception:
        return gpd.read_file(path, driver="LIBKML", engine="pyogrio")


def _extract_kml_timestamp(path: Path) -> str:
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    if len(digits) < 12:
        raise ValueError(f"timestamp not found in filename: {path.name}")
    ymdhm = digits[-12:]
    return f"{ymdhm[0:4]}-{ymdhm[4:6]}-{ymdhm[6:8]}T{ymdhm[8:10]}:{ymdhm[10:12]}:00"


def load_kml_timeline(kml_dir: str) -> dict[str, gpd.GeoDataFrame]:
    kml_files = _find_files(kml_dir, ".kml")
    by_ts = {_extract_kml_timestamp(p): p for p in kml_files}

    missing = [ts for ts in config.KML_TIMESTAMPS if ts not in by_ts]
    if missing:
        raise ValueError(f"KML timestamp mismatch. missing={missing}")

    timeline: dict[str, gpd.GeoDataFrame] = {}
    for ts in config.KML_TIMESTAMPS:
        gdf = _read_kml(by_ts[ts]).to_crs(config.CRS_JGD2011)
        gdf = gdf[gdf.geometry.notnull()].copy()
        gdf["geometry"] = gdf.geometry.buffer(10)
        timeline[ts] = gdf
    return timeline


def build_flood_polygons(a31a: gpd.GeoDataFrame, kml_timeline: dict[str, gpd.GeoDataFrame]) -> dict[str, gpd.GeoDataFrame]:
    result: dict[str, gpd.GeoDataFrame] = {}
    for ts, kml_buf in kml_timeline.items():
        joined = gpd.sjoin(a31a, kml_buf[["geometry"]], predicate="intersects", how="inner")
        result[ts] = joined.drop(columns=[c for c in ["index_right"] if c in joined.columns]).copy()
    return result


def save_flood_polygons(flood_dict: dict[str, gpd.GeoDataFrame], path: str) -> None:
    with open(path, "wb") as f:
        pickle.dump(flood_dict, f)


def visualize_flood_timeline(flood_dict: dict[str, gpd.GeoDataFrame], output_path: str) -> None:
    fmap = folium.Map(location=[36.05, 140.0], zoom_start=11, tiles="OpenStreetMap")
    colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#999999"]
    for i, (ts, gdf) in enumerate(flood_dict.items()):
        folium.GeoJson(
            gdf.to_crs(config.CRS_WGS84),
            name=ts,
            style_function=lambda _, color=colors[i % len(colors)]: {"color": color, "weight": 1.0, "fillOpacity": 0.25},
        ).add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(output_path)


def main() -> None:
    ensure_output_dir(config.OUT_FLOOD_DIR)
    a31a = load_a31a_gml(config.GML_DIR)
    kml_timeline = load_kml_timeline(config.KML_DIR)
    flood_dict = build_flood_polygons(a31a, kml_timeline)
    save_flood_polygons(flood_dict, config.FLOOD_PKL_PATH)
    visualize_flood_timeline(flood_dict, config.FLOOD_MAP_PATH)
    print(f"[INFO] saved: {config.FLOOD_PKL_PATH}")
    print(f"[INFO] saved: {config.FLOOD_MAP_PATH}")


if __name__ == "__main__":
    main()
