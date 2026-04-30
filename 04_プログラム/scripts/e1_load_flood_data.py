"""STEP 1b: 浸水データを読み込み、時刻別浸水ポリゴン辞書を構築する。"""

import glob
import pickle
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import Polygon

import config

# KML LineString を Polygon 化するバッファ幅（m）
_KML_BUFFER_M = 10
_CRS_METRIC = "EPSG:6690"  # JGD2011 / UTM zone 54N

# 時刻別表示色（folium可視化用）
_TIMELINE_COLORS = [
    "#e41a1c", "#ff7f00", "#ffff33", "#4daf4a",
    "#377eb8", "#984ea3", "#a65628", "#f781bf",
]


def load_a31a_gml(gml_dir: str) -> gpd.GeoDataFrame:
    """A31a GML から waterDepth >= しきい値 のポリゴンを抽出して返す。

    国土数値情報A31a形式はpyogrioで読めないため、ETでxlink参照を手動解決する。
    座標系: gml:posList は (lat, lon) 順 → Shapely用に (lon, lat) へ変換。
    """
    _NS = {
        "gml":   "http://schemas.opengis.net/gml/3.2.1",
        "ksj":   "http://nlftp.mlit.go.jp/ksj/schemas/ksj-app",
        "xlink": "http://www.w3.org/1999/xlink",
    }

    def _parse_one(path: str) -> list[dict]:
        tree = ET.parse(path)
        root = tree.getroot()

        curves: dict[str, list[tuple[float, float]]] = {}
        for cv in root.iter(f"{{{_NS['gml']}}}Curve"):
            cv_id = cv.get(f"{{{_NS['gml']}}}id")
            pos = cv.find(f".//{{{_NS['gml']}}}posList")
            if cv_id is None or pos is None or not pos.text:
                continue
            vals = list(map(float, pos.text.split()))
            curves[cv_id] = [(vals[i + 1], vals[i]) for i in range(0, len(vals) - 1, 2)]

        surfaces: dict[str, Polygon] = {}
        for sf in root.iter(f"{{{_NS['gml']}}}Surface"):
            sf_id = sf.get(f"{{{_NS['gml']}}}id")
            if sf_id is None:
                continue
            ext_ring = sf.find(f".//{{{_NS['gml']}}}exterior/{{{_NS['gml']}}}Ring")
            if ext_ring is None:
                continue
            coords: list[tuple[float, float]] = []
            for cm in ext_ring.findall(f"{{{_NS['gml']}}}curveMember"):
                href = cm.get(f"{{{_NS['xlink']}}}href", "").lstrip("#")
                coords.extend(curves.get(href, []))
            if len(coords) >= 3:
                surfaces[sf_id] = Polygon(coords)

        rows = []
        for feat in root.iter(f"{{{_NS['ksj']}}}PlanScale"):
            bounds_el = feat.find(f"{{{_NS['ksj']}}}bounds")
            depth_el  = feat.find(f"{{{_NS['ksj']}}}waterDepth")
            if bounds_el is None or depth_el is None:
                continue
            sf_ref = bounds_el.get(f"{{{_NS['xlink']}}}href", "").lstrip("#")
            if sf_ref not in surfaces:
                continue
            depth = int(depth_el.text)
            if depth >= config.FLOOD_DEPTH_THRESHOLD:
                rows.append({"waterDepth": depth, "geometry": surfaces[sf_ref]})
        return rows

    xml_files = glob.glob(f"{gml_dir}/**/*.xml", recursive=True)
    xml_files = [f for f in xml_files if "META" not in Path(f).name.upper()]

    all_rows: list[dict] = []
    for path in xml_files:
        try:
            all_rows.extend(_parse_one(path))
        except Exception as e:
            print(f"[warn] {Path(path).name}: {e}")

    if not all_rows:
        raise RuntimeError("A31a GML から浸水ポリゴンを抽出できませんでした")

    a31a = gpd.GeoDataFrame(all_rows, crs="EPSG:6668")
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

        gdf = gdf.to_crs(_CRS_METRIC).copy()
        gdf["geometry"] = gdf.geometry.buffer(_KML_BUFFER_M)
        gdf = gdf.to_crs(config.CRS_JGD2011)
        gdf = gdf[~gdf.geometry.is_empty]
        timeline[ts] = gdf
        print(f"[kml] {ts}: {len(gdf)} フィーチャ")

    return timeline


def build_flood_polygons(
    a31a: gpd.GeoDataFrame,
    kml_timeline: dict[str, gpd.GeoDataFrame],
) -> dict[str, gpd.GeoDataFrame]:
    """KML各時点の凸包エンベロープでA31aを絞り込み、時刻別浸水ポリゴンを構築する。

    アプローチ（案2+3複合）:
      案2: KML各時点の union_all().convex_hull を浸水エンベロープとして使用。
           時刻ごとに異なる KML 範囲を反映し、時刻別道路閉鎖の変化を表現する。
      案3: 凸包内に A31a ポリゴンが 0 件の場合は A31a 全体をフォールバック採用。
           浸水深フィルタ（waterDepth>=2 = 0.5m以上）は A31a 側で保証済み。
    """
    assert a31a.crs.to_epsg() == 6668, f"a31a CRS 不一致: {a31a.crs}"

    flood_dict: dict[str, gpd.GeoDataFrame] = {}
    for ts, kml_gdf in kml_timeline.items():
        assert kml_gdf.crs.to_epsg() == 6668, f"KML CRS 不一致: {kml_gdf.crs}"

        # KML 全ジオメトリの凸包を浸水エンベロープとして使用（案2）
        kml_hull = kml_gdf.geometry.union_all().convex_hull
        kml_envelope = gpd.GeoDataFrame(geometry=[kml_hull], crs=a31a.crs)
        joined = gpd.sjoin(a31a, kml_envelope, how="inner", predicate="intersects")
        result = a31a.loc[joined.index.unique()].copy()

        if len(result) == 0:
            # フォールバック: A31a 全体を採用（案3）
            print(f"[flood] {ts}: KML 凸包内 A31a なし → A31a 全体フォールバック ({len(a31a)} ポリゴン)")
            result = a31a.copy()
        else:
            print(f"[flood] {ts}: {len(result)} ポリゴン (KML 凸包との交差)")

        flood_dict[ts] = result

    return flood_dict


def save_flood_polygons(flood_dict: dict, path: str) -> bool:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "wb") as f:
            pickle.dump(flood_dict, f)
    except PermissionError:
        if Path(path).exists():
            with open(path, "rb") as f:
                pickle.load(f)
            print(f"[warn] 既存PKLを上書きできないため保持: {path}")
            return False
        raise
    print(f"[save] flood_polygons.pkl -> {path}  ({len(flood_dict)} 時点)")
    return True


def visualize_flood_timeline(flood_dict: dict, output_path: str) -> bool:
    first_gdf = next(iter(flood_dict.values()))
    center_wgs84 = first_gdf.to_crs(config.CRS_WGS84).geometry.representative_point()
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
    try:
        m.save(output_path)
    except PermissionError:
        if Path(output_path).exists():
            print(f"[warn] 既存HTMLを上書きできないため保持: {output_path}")
            return False
        raise
    print(f"[save] flood timeline map -> {output_path}")
    return True


if __name__ == "__main__":
    a31a = load_a31a_gml(config.GML_DIR)
    kml_timeline = load_kml_timeline(config.KML_DIR)
    flood_dict = build_flood_polygons(a31a, kml_timeline)
    save_flood_polygons(flood_dict, config.FLOOD_PKL_PATH)
    visualize_flood_timeline(flood_dict, config.FLOOD_MAP_PATH)
    print("STEP 1b 完了")
