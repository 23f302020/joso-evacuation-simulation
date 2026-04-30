"""コンフリクト解消済み。STEP 1a: 常総市の道路ネットワーク取得。"""

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


def save_edges(edges_gdf: gpd.GeoDataFrame, path: str) -> None:
    edges_gdf.to_file(path, driver="GPKG")


def visualize_network(edges_gdf: gpd.GeoDataFrame, output_path: str) -> None:
    edges_wgs84 = edges_gdf.to_crs(config.CRS_WGS84)
    center = [36.05, 140.0]
    fmap = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap")
    folium.GeoJson(
        edges_wgs84,
        name="joso_road_edges",
        style_function=lambda _: {"color": "#1f77b4", "weight": 1.2, "opacity": 0.8},
    ).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    fmap.save(output_path)


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

    _, edges = network_to_gdf(graph)
    save_edges(edges, config.EDGES_GPKG_PATH)
    visualize_network(edges, config.NETWORK_MAP_PATH)

    print(f"[INFO] saved: {config.GRAPHML_PATH}")
    print(f"[INFO] saved: {config.EDGES_GPKG_PATH}")
    print(f"[INFO] saved: {config.NETWORK_MAP_PATH}")


if __name__ == "__main__":
    main()
