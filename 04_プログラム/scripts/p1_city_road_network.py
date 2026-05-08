"""
茨城県内拡張 — 市区町村別道路ネットワーク取得スクリプト

使い方：
    # 全市区町村を順番に処理（既取得はスキップ）
    python p1_city_road_network.py

    # 特定の市区町村コードのみ処理
    python p1_city_road_network.py --code 08201
    python p1_city_road_network.py --code 08201 08207 08210

    # 取得済みステータス確認のみ（取得は行わない）
    python p1_city_road_network.py --status

出力先：
    04_プログラム/output/network/cities/{市区町村コード}/
        {code}_road_network.graphml  ... OSMnxグラフ
        {code}_edges.gpkg            ... エッジGeoPackage（空間結合用）
        {code}_summary.json          ... 取得メタ情報
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ===== 市区町村マスタ =====
MUNICIPALITIES: list[tuple[str, str]] = [
    ("08201", "水戸市"),
    ("08202", "日立市"),
    ("08203", "土浦市"),
    ("08204", "古河市"),
    ("08205", "石岡市"),
    ("08207", "結城市"),
    ("08208", "龍ケ崎市"),
    ("08210", "下妻市"),
    ("08211", "常総市"),       # Phase 1 完了済み（既存graphmlを流用）
    ("08212", "常陸太田市"),
    ("08214", "高萩市"),
    ("08215", "北茨城市"),
    ("08216", "笠間市"),
    ("08217", "取手市"),
    ("08219", "牛久市"),
    ("08220", "つくば市"),
    ("08221", "ひたちなか市"),
    ("08222", "鹿嶋市"),
    ("08223", "潮来市"),
    ("08224", "守谷市"),
    ("08225", "常陸大宮市"),
    ("08226", "那珂市"),
    ("08227", "筑西市"),
    ("08228", "坂東市"),
    ("08229", "稲敷市"),
    ("08230", "かすみがうら市"),
    ("08231", "桜川市"),
    ("08232", "神栖市"),
    ("08233", "行方市"),
    ("08234", "鉾田市"),
    ("08235", "つくばみらい市"),
    ("08236", "小美玉市"),
    ("08302", "茨城町"),
    ("08309", "大洗町"),
    ("08310", "城里町"),
    ("08341", "東海村"),
    ("08364", "大子町"),
    ("08442", "美浦村"),
    ("08443", "阿見町"),
    ("08447", "河内町"),
    ("08521", "八千代町"),
    ("08542", "五霞町"),
    ("08546", "境町"),
    ("08564", "利根町"),
]

# A31a 洪水データ カバレッジ（2026/05/08 再確認済み）
A31A_COVERAGE: dict[str, list[str]] = {
    "08201": ["08_10", "08_20"],  # 水戸市
    "08202": ["08_10"],           # 日立市
    "08203": ["08_20"],           # 土浦市
    "08204": ["08_20"],           # 古河市（08_20: 4,232件）
    "08205": ["08_10", "08_20"],  # 石岡市
    "08207": ["08_10", "08_20"],  # 結城市
    "08208": ["08_20"],           # 龍ケ崎市
    "08210": ["08_20"],           # 下妻市
    "08211": ["08_10", "08_20"],  # 常総市
    "08212": ["08_10", "08_20"],  # 常陸太田市
    "08214": ["08_10"],           # 高萩市
    "08215": ["08_10"],           # 北茨城市
    "08216": ["08_10", "08_20"],  # 笠間市
    "08217": ["08_20"],           # 取手市
    "08219": ["08_20"],           # 牛久市
    "08220": ["08_10", "08_20"],  # つくば市
    "08221": ["08_10", "08_20"],  # ひたちなか市
    "08222": [],                  # 鹿嶋市（08_10・08_20ともに境界内0件・対象外）
    "08223": ["08_10"],           # 潮来市
    "08224": ["08_20"],           # 守谷市
    "08225": ["08_10", "08_20"],  # 常陸大宮市
    "08226": ["08_10", "08_20"],  # 那珂市
    "08227": ["08_10", "08_20"],  # 筑西市
    "08228": ["08_20"],           # 坂東市（08_20: 6,126件）
    "08229": ["08_10", "08_20"],  # 稲敷市
    "08230": ["08_10", "08_20"],  # かすみがうら市
    "08231": ["08_10", "08_20"],  # 桜川市
    "08232": [],                  # 神栖市（08_10・08_20ともに境界内0件・対象外）
    "08233": ["08_10", "08_20"],  # 行方市（08_10境界内0件のため08_20も試行）
    "08234": ["08_10", "08_20"],  # 鉾田市
    "08235": ["08_10", "08_20"],  # つくばみらい市
    "08236": ["08_10", "08_20"],  # 小美玉市
    "08302": ["08_10", "08_20"],  # 茨城町
    "08309": ["08_20"],           # 大洗町
    "08310": ["08_10", "08_20"],  # 城里町
    "08341": [],                  # 東海村（08_10・08_20ともに境界内0件・対象外）
    "08364": ["08_10"],           # 大子町
    "08442": ["08_20"],           # 美浦村
    "08443": ["08_20"],           # 阿見町
    "08447": ["08_20"],           # 河内町
    "08521": ["08_20"],           # 八千代町（08_20: 3,098件）
    "08542": [],                  # 五霞町（08_10・08_20ともに境界内0件・対象外）
    "08546": ["08_20"],           # 境町（08_20: 2,168件）
    "08564": ["08_20"],           # 利根町
}

A31A_EXCLUDED: dict[str, str] = {
    "08222": "対象外(境界内0件)",
    "08232": "対象外(境界内0件)",
    "08341": "対象外(境界内0件)",
    "08542": "対象外(境界内0件)",
}

# 常総市の既存グラフファイル（Phase 1 の成果物）
JOSO_EXISTING_GRAPHML = Path(__file__).parent.parent / "output" / "network" / "joso_road_network.graphml"
JOSO_EXISTING_GPKG    = Path(__file__).parent.parent / "output" / "network" / "joso_edges.gpkg"

# 出力ベースディレクトリ
OUT_BASE = Path(__file__).parent.parent / "output" / "network" / "cities"

CRS_JGD2011 = "EPSG:6668"


def city_out_dir(code: str) -> Path:
    return OUT_BASE / code


def graphml_path(code: str) -> Path:
    return city_out_dir(code) / f"{code}_road_network.graphml"


def gpkg_path(code: str) -> Path:
    return city_out_dir(code) / f"{code}_edges.gpkg"


def summary_path(code: str) -> Path:
    return city_out_dir(code) / f"{code}_summary.json"


def is_acquired(code: str) -> bool:
    if code == "08211" and JOSO_EXISTING_GRAPHML.exists() and JOSO_EXISTING_GPKG.exists():
        return True
    return graphml_path(code).exists() and gpkg_path(code).exists()


def load_modules():
    """osmnx / geopandas を遅延インポート（status確認時に不要なため）"""
    try:
        import osmnx as ox
        import geopandas as gpd
        return ox, gpd
    except ImportError as e:
        print(f"[ERROR] ライブラリが見つかりません: {e}")
        print("  → venv を有効化してから実行してください:")
        print("       cd 04_プログラム")
        print("       .\\venv\\Scripts\\activate   (Windows)")
        print("       source venv/bin/activate  (Mac/Linux)")
        sys.exit(1)


def fetch_city(code: str, name: str, ox, gpd) -> dict:
    """1市区町村の道路ネットワークを取得して保存する。"""
    out_dir = city_out_dir(code)
    out_dir.mkdir(parents=True, exist_ok=True)

    gml_path = graphml_path(code)
    cache_exists = gml_path.exists() and gpkg_path(code).exists()

    # --- 常総市は既存ファイルを流用 ---
    if code == "08211":
        if not cache_exists:
            if JOSO_EXISTING_GRAPHML.exists():
                import shutil
                shutil.copy2(JOSO_EXISTING_GRAPHML, gml_path)
                print(f"  [COPY] 既存常総市グラフをコピー: {gml_path}")
            else:
                print(f"  [WARN] 常総市の既存グラフが見つかりません: {JOSO_EXISTING_GRAPHML}")
        if not gpkg_path(code).exists() and JOSO_EXISTING_GPKG.exists():
            import shutil
            shutil.copy2(JOSO_EXISTING_GPKG, gpkg_path(code))
        cache_exists = gml_path.exists() and gpkg_path(code).exists()

    # --- OSMから取得 ---
    if not cache_exists:
        start = datetime.now()
        place_name = f"{name}, 茨城県, 日本"
        print(f"  [FETCH] {place_name} ...")
        try:
            graph = ox.graph_from_place(place_name, network_type="drive")
        except Exception as e:
            print(f"  [ERROR] 取得失敗: {e}")
            return {"code": code, "name": name, "status": "error", "error": str(e)}

        ox.save_graphml(graph, filepath=str(gml_path))
        elapsed = (datetime.now() - start).total_seconds()
        print(f"  [SAVE] GraphML保存: {gml_path} ({elapsed:.1f}s)")

        # エッジGeoPackage保存
        try:
            _, edges = ox.graph_to_gdfs(graph)
            edges = edges.to_crs(CRS_JGD2011)
            out_gpkg = gpkg_path(code)
            if out_gpkg.exists():
                out_gpkg.unlink()
            edges.to_file(str(out_gpkg), driver="GPKG")
            edge_count = len(edges)
            print(f"  [SAVE] エッジGPKG保存: {out_gpkg} ({edge_count} edges)")
        except Exception as e:
            print(f"  [WARN] GPKG保存失敗: {e}")
            edge_count = -1
            elapsed = (datetime.now() - start).total_seconds()

        result = {
            "code": code,
            "name": name,
            "status": "ok",
            "graphml": str(gml_path),
            "gpkg": str(gpkg_path(code)),
            "edge_count": edge_count,
            "a31a_coverage": A31A_COVERAGE.get(code, []),
            "fetched_at": datetime.now().isoformat(),
            "elapsed_sec": elapsed,
        }
    else:
        print(f"  [SKIP] キャッシュ済み: {gml_path}")
        result = {
            "code": code,
            "name": name,
            "status": "cached",
            "graphml": str(gml_path),
            "gpkg": str(gpkg_path(code)),
            "a31a_coverage": A31A_COVERAGE.get(code, []),
        }

    # サマリJSON保存
    with open(summary_path(code), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def print_status():
    """全市区町村の取得状況を表示する。"""
    print(f"\n{'='*65}")
    print(f" 茨城県内拡張 --- 道路ネットワーク取得ステータス")
    print(f"{'='*65}")
    print(f"{'コード':8} {'市区町村':20} {'道路NW':8} {'A31a':20}")
    print(f"{'-'*65}")
    acquired = 0
    for code, name in MUNICIPALITIES:
        nw = "[OK]取得済" if is_acquired(code) else "[--]未取得"
        a31a = A31A_COVERAGE.get(code, [])
        a31a_str = "+".join(a31a) if a31a else A31A_EXCLUDED.get(code, "要調査")
        print(f"{code:8} {name:20} {nw:8} {a31a_str}")
        if is_acquired(code):
            acquired += 1
    print(f"{'-'*65}")
    print(f" 取得済み: {acquired} / {len(MUNICIPALITIES)} 市区町村")
    print(f"{'='*65}\n")


def main():
    parser = argparse.ArgumentParser(description="茨城県内市区町村別 道路ネットワーク取得")
    parser.add_argument("--code", nargs="*", metavar="CODE",
                        help="処理対象の市区町村コード（省略時は全市区町村）")
    parser.add_argument("--status", action="store_true",
                        help="取得状況を確認して終了（取得は行わない）")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    # 対象絞り込み
    if args.code:
        valid_codes = {c for c, _ in MUNICIPALITIES}
        targets = [(c, n) for c, n in MUNICIPALITIES if c in args.code]
        invalid = [c for c in args.code if c not in valid_codes]
        if invalid:
            print(f"[WARN] 不明なコード: {invalid}")
        if not targets:
            print("[ERROR] 処理対象がありません。コードを確認してください。")
            sys.exit(1)
    else:
        targets = MUNICIPALITIES

    ox, gpd = load_modules()

    print(f"\n対象: {len(targets)} 市区町村")
    print(f"出力先: {OUT_BASE}\n")

    results = []
    for i, (code, name) in enumerate(targets, 1):
        print(f"[{i:2d}/{len(targets)}] {code} {name}")
        result = fetch_city(code, name, ox, gpd)
        results.append(result)

    # 全体サマリをJSONで保存
    summary_name = (
        "ibaraki_network_summary_selected.json"
        if args.code
        else "ibaraki_network_summary.json"
    )
    summary_all = OUT_BASE / summary_name
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    with open(summary_all, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = sum(1 for r in results if r.get("status") in ("ok", "cached"))
    err = sum(1 for r in results if r.get("status") == "error")
    print(f"\n=== 完了 ===")
    print(f"  成功: {ok}市区町村 / エラー: {err}市区町村")
    print(f"  全体サマリ: {summary_all}")

    print_status()


if __name__ == "__main__":
    main()
