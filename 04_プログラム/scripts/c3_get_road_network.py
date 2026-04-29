"""STEP 1a: 常総市の道路ネットワークを取得して保存する。"""

import os
from pathlib import Path

import folium
import networkx as nx
import osmnx as ox

import config


def get_road_network() -> nx.MultiDiGraph:
    """GraphMLキャッシュがあれば再利用し、なければOSM APIから取得する。"""
    if os.path.exists(config.GRAPHML_PATH):
        print(f"[cache] {config.GRAPHML_PATH} を読み込みます")
        return ox.load_graphml(config.GRAPHML_PATH)

    print(f"[osmnx] '{config.JOSO_PLACE}' の道路ネットワークを取得します")
    try:
        G = ox.graph_from_place(config.JOSO_PLACE, network_type=config.OSM_NETWORK_TYPE)
    except Exception as e:
        print(f"[warn] place名取得失敗 ({e})、BBOXで再試行します")
        lon_min, lat_min, lon_max, lat_max = config.JOSO_BBOX
        G = ox.graph_from_bbox(
            (lat_min, lat_max, lon_min, lon_max),
            network_type=config.OSM_NETWORK_TYPE,
        )
    return G


def save_network(G: nx.MultiDiGraph, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, path)
    print(f"[save] GraphML -> {path}")


def network_to_gdf(G: nx.MultiDiGraph):
    _, edges_gdf = ox.graph_to_gdfs(G)
    edges_gdf = edges_gdf.to_crs(config.CRS_JGD2011)
    return edges_gdf


def save_edges_gpkg(edges_gdf, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    edges_gdf.to_file(path, driver="GPKG")
    print(f"[save] GeoPackage -> {path}  ({len(edges_gdf)} edges)")


def visualize_network(edges_gdf, output_path: str) -> None:
    edges_wgs84 = edges_gdf.to_crs(config.CRS_WGS84)
    center = [
        edges_wgs84.geometry.centroid.y.mean(),
        edges_wgs84.geometry.centroid.x.mean(),
    ]
    m = folium.Map(location=center, zoom_start=13)
    folium.GeoJson(
        edges_wgs84.__geo_interface__,
        name="道路ネットワーク",
        style_function=lambda _: {"color": "#3388ff", "weight": 1.5, "opacity": 0.7},
    ).add_to(m)
    folium.LayerControl().add_to(m)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    m.save(output_path)
    print(f"[save] folium map -> {output_path}")


if __name__ == "__main__":
    G = get_road_network()
    print(f"  ノード数: {len(G.nodes)}, エッジ数: {len(G.edges)}")
    save_network(G, config.GRAPHML_PATH)
    edges_gdf = network_to_gdf(G)
    save_edges_gpkg(edges_gdf, config.EDGES_GPKG_PATH)
    visualize_network(edges_gdf, config.NETWORK_MAP_PATH)
    print("STEP 1a 完了")
