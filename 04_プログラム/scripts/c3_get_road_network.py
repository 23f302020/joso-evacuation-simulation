"""STEP 1a: 常総市の道路ネットワーク取得と保存。"""

from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd
import osmnx as ox
from networkx import MultiDiGraph

import config


def ensure_output_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def get_road_network() -> MultiDiGraph:
    return ox.graph_from_place(config.JOSO_PLACE, network_type=config.OSM_NETWORK_TYPE)


def save_network(graph: MultiDiGraph, path: str) -> None:
    ox.save_graphml(graph, filepath=path)


def load_network(path: str) -> MultiDiGraph:
    return ox.load_graphml(path)


def network_to_gdf(graph: MultiDiGraph) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    nodes, edges = ox.graph_to_gdfs(graph)
    nodes = nodes.to_crs(config.CRS_JGD2011)
    edges = edges.to_crs(config.CRS_JGD2011)
    return nodes, edges


def save_edges(edges_gdf: gpd.GeoDataFrame, path: str) -> bool:
    target = Path(path)
    if target.exists():
        try:
            target.unlink()
        except PermissionError:
            # Windows/OneDrive環境で既存GeoPackageがロックされる場合は、
            # 読み込み可能な既存成果物を保持して後続処理に進む。
            gpd.read_file(target, rows=1)
            print(f"[WARN] 既存GPKGを上書きできないため保持: {target}")
            return False
    edges_gdf.to_file(path, driver="GPKG")
    return True


def visualize_network(edges_gdf: gpd.GeoDataFrame, output_path: str) -> bool:
    edges_wgs84 = edges_gdf.to_crs(config.CRS_WGS84)
    reps = edges_wgs84.geometry.representative_point()
    center = [float(reps.y.mean()), float(reps.x.mean())]
    fmap = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap")
    folium.GeoJson(
        edges_wgs84,
        name="joso_road_edges",
        style_function=lambda _: {"color": "#1f77b4", "weight": 1.2, "opacity": 0.8},
    ).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    try:
        fmap.save(output_path)
    except PermissionError:
        if Path(output_path).exists():
            print(f"[WARN] 既存HTMLを上書きできないため保持: {output_path}")
            return False
        raise
    return True


def main() -> None:
    ensure_output_dir(config.OUT_NETWORK_DIR)

    graphml_path = Path(config.GRAPHML_PATH)
    if graphml_path.exists():
        print(f"[INFO] GraphML キャッシュを使用: {graphml_path}")
        graph = load_network(str(graphml_path))
    else:
        print("[INFO] OSM から道路ネットワークを取得中...")
        graph = get_road_network()
        save_network(graph, str(graphml_path))
        print(f"[INFO] GraphML 保存完了: {graphml_path}")

    _, edges = network_to_gdf(graph)
    if save_edges(edges, config.EDGES_GPKG_PATH):
        print(f"[INFO] エッジ GPKG 保存完了: {config.EDGES_GPKG_PATH} ({len(edges)} edges)")
    else:
        print(f"[INFO] 既存エッジ GPKG を使用: {config.EDGES_GPKG_PATH} ({len(edges)} edges)")

    if visualize_network(edges, config.NETWORK_MAP_PATH):
        print(f"[INFO] 可視化HTML保存完了: {config.NETWORK_MAP_PATH}")


if __name__ == "__main__":
    main()
