"""STEP 1a: 常総市の道路ネットワーク取得と保存。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import config


def _require_dependency(module_name: str) -> Any:
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(f"Missing dependency: {module_name}. Install requirements.txt first.") from exc


def ensure_output_dir(path: str) -> None:
    """出力先ディレクトリを作成する。"""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_road_network():
    """常総市の道路ネットワークを OSM から取得する。"""
    ox = _require_dependency("osmnx")
    return ox.graph_from_place(config.JOSO_PLACE, network_type=config.OSM_NETWORK_TYPE)


def save_network(graph, path: str) -> None:
    """道路ネットワークを GraphML で保存する。"""
    ox = _require_dependency("osmnx")
    ox.save_graphml(graph, filepath=path)


def load_network(path: str):
    """GraphML から道路ネットワークを読み込む。"""
    ox = _require_dependency("osmnx")
    return ox.load_graphml(path)


def network_to_gdf(graph):
    """道路ネットワークをノード/エッジの GeoDataFrame に変換し CRS を統一する。"""
    ox = _require_dependency("osmnx")
    nodes, edges = ox.graph_to_gdfs(graph)
    nodes = nodes.to_crs(config.CRS_JGD2011)
    edges = edges.to_crs(config.CRS_JGD2011)
    return nodes, edges


def save_edges(edges_gdf, path: str) -> None:
    """エッジ GeoDataFrame を GeoPackage として保存する。"""
    edges_gdf.to_file(path, driver="GPKG")


def visualize_network(edges_gdf, output_path: str) -> None:
    """道路エッジを folium 地図へ出力する。"""
    folium = _require_dependency("folium")
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
        print(f"[INFO] GraphML 保存完了: {graphml_path}")

    _, edges = network_to_gdf(graph)
    save_edges(edges, config.EDGES_GPKG_PATH)
    print(f"[INFO] エッジ GPKG 保存完了: {config.EDGES_GPKG_PATH} ({len(edges)} edges)")

    visualize_network(edges, config.NETWORK_MAP_PATH)
    print(f"[INFO] 可視化HTML保存完了: {config.NETWORK_MAP_PATH}")


if __name__ == "__main__":
    main()
