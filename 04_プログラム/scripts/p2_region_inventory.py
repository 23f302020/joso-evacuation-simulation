"""
Phase 2 全域拡張に向けた対象地域リスト・入力データ棚卸し生成スクリプト。

このスクリプトは SUMO 変換や TraCI 実行は行わず、Phase 1 対象地域全域へ
Phase 2 を広げるための管理ファイルを生成する。

出力先:
    04_プログラム/output/sumo/regions/_management/
        phase2_region_targets.csv
        phase2_region_inventory.csv
        phase2_region_inventory.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from p1_city_road_network import A31A_COVERAGE, A31A_EXCLUDED, MUNICIPALITIES


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"

SCENARIO_CITIES_DIR = OUTPUT_DIR / "scenario_cities"
UNIFIED_MANIFEST_JS = OUTPUT_DIR / "unified" / "assets" / "cities_manifest.js"
NETWORK_CITIES_DIR = OUTPUT_DIR / "network" / "cities"

SUMO_DIR = OUTPUT_DIR / "sumo"
REGIONS_DIR = SUMO_DIR / "regions"
MANAGEMENT_DIR = REGIONS_DIR / "_management"

TARGETS_CSV = MANAGEMENT_DIR / "phase2_region_targets.csv"
INVENTORY_CSV = MANAGEMENT_DIR / "phase2_region_inventory.csv"
INVENTORY_MD = MANAGEMENT_DIR / "phase2_region_inventory.md"


def rel(path: Path) -> str:
    """04_プログラムからの相対パスを返す。"""
    try:
        return path.relative_to(PROGRAM_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def exists_mark(path: Path) -> str:
    return "yes" if path.exists() else "no"


def load_manifest_codes() -> dict[str, str]:
    """統合HTML用 manifest から Phase 1 表示対象を抽出する。"""
    if not UNIFIED_MANIFEST_JS.exists():
        return {}

    text = UNIFIED_MANIFEST_JS.read_text(encoding="utf-8")
    return {
        code: name
        for code, name in re.findall(r'\{code:"(\d+)",name:"([^"]+)"', text)
    }


def read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"summary_json_error": "json_decode_error"}


def build_inventory_rows() -> list[dict[str, str]]:
    manifest_codes = load_manifest_codes()
    rows: list[dict[str, str]] = []

    for code, name in MUNICIPALITIES:
        scenario_dir = SCENARIO_CITIES_DIR / code
        scenario_html = scenario_dir / "scenario_route_simulation.html"
        data_js = scenario_dir / "assets" / "data.js"
        app_js = scenario_dir / "assets" / "app.js"
        style_css = scenario_dir / "assets" / "style.css"

        network_dir = NETWORK_CITIES_DIR / code
        graphml = network_dir / f"{code}_road_network.graphml"
        edges_gpkg = network_dir / f"{code}_edges.gpkg"
        summary_json = network_dir / f"{code}_summary.json"
        network_summary = read_summary(summary_json)

        region_dir = REGIONS_DIR / code
        expected_region_dirs = [
            region_dir / "network",
            region_dir / "derived",
            region_dir / "scenarios",
            region_dir / "results",
            region_dir / "viz",
        ]

        excluded_reason = A31A_EXCLUDED.get(code, "")
        has_phase1_city_output = scenario_html.exists() and data_js.exists()
        included_in_manifest = code in manifest_codes
        include_in_phase2 = (
            not excluded_reason
            and has_phase1_city_output
            and included_in_manifest
        )
        precheck_ready = (
            include_in_phase2
            and graphml.exists()
            and edges_gpkg.exists()
            and summary_json.exists()
            and app_js.exists()
            and style_css.exists()
        )

        if excluded_reason:
            phase1_status = "excluded_phase1"
        elif include_in_phase2:
            phase1_status = "phase1_target"
        elif has_phase1_city_output:
            phase1_status = "phase1_output_not_in_manifest"
        else:
            phase1_status = "missing_phase1_output"

        rows.append(
            {
                "city_code": code,
                "city_name": name,
                "phase1_status": phase1_status,
                "include_in_phase2_region": "yes" if include_in_phase2 else "no",
                "phase2_precheck_ready": "yes" if precheck_ready else "no",
                "a31a_sources": "+".join(A31A_COVERAGE.get(code, [])),
                "exclusion_reason": excluded_reason,
                "in_unified_manifest": "yes" if included_in_manifest else "no",
                "scenario_html": exists_mark(scenario_html),
                "scenario_data_js": exists_mark(data_js),
                "scenario_app_js": exists_mark(app_js),
                "scenario_style_css": exists_mark(style_css),
                "network_graphml": exists_mark(graphml),
                "network_edges_gpkg": exists_mark(edges_gpkg),
                "network_summary_json": exists_mark(summary_json),
                "network_summary_nodes": str(network_summary.get("nodes", "")),
                "network_summary_edges": str(network_summary.get("edges", "")),
                "phase1_scenario_dir": rel(scenario_dir),
                "phase2_region_dir": rel(region_dir),
                "expected_phase2_subdirs": ";".join(rel(path) for path in expected_region_dirs),
            }
        )

    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_targets_csv(rows: list[dict[str, str]]) -> None:
    target_rows = [
        {
            "city_code": row["city_code"],
            "city_name": row["city_name"],
            "target_scope": "phase1_target_region",
            "phase1_status": row["phase1_status"],
            "a31a_sources": row["a31a_sources"],
            "phase1_scenario_dir": row["phase1_scenario_dir"],
            "phase2_region_dir": row["phase2_region_dir"],
            "include_in_phase2_region": row["include_in_phase2_region"],
            "phase2_precheck_ready": row["phase2_precheck_ready"],
            "note": "Phase 2 全域拡張対象",
        }
        for row in rows
        if row["include_in_phase2_region"] == "yes"
    ]

    write_csv(
        TARGETS_CSV,
        target_rows,
        [
            "city_code",
            "city_name",
            "target_scope",
            "phase1_status",
            "a31a_sources",
            "phase1_scenario_dir",
            "phase2_region_dir",
            "include_in_phase2_region",
            "phase2_precheck_ready",
            "note",
        ],
    )


def write_inventory_csv(rows: list[dict[str, str]]) -> None:
    write_csv(
        INVENTORY_CSV,
        rows,
        [
            "city_code",
            "city_name",
            "phase1_status",
            "include_in_phase2_region",
            "phase2_precheck_ready",
            "a31a_sources",
            "exclusion_reason",
            "in_unified_manifest",
            "scenario_html",
            "scenario_data_js",
            "scenario_app_js",
            "scenario_style_css",
            "network_graphml",
            "network_edges_gpkg",
            "network_summary_json",
            "network_summary_nodes",
            "network_summary_edges",
            "phase1_scenario_dir",
            "phase2_region_dir",
            "expected_phase2_subdirs",
        ],
    )


def markdown_table(rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> list[str]:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(key, "") for key, _ in columns) + " |")
    return lines


def write_inventory_markdown(rows: list[dict[str, str]]) -> None:
    target_rows = [row for row in rows if row["include_in_phase2_region"] == "yes"]
    ready_rows = [row for row in target_rows if row["phase2_precheck_ready"] == "yes"]
    excluded_rows = [row for row in rows if row["phase1_status"] == "excluded_phase1"]
    missing_rows = [
        row
        for row in rows
        if row["include_in_phase2_region"] == "yes"
        and row["phase2_precheck_ready"] != "yes"
    ]

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        "# Phase 2 全域拡張 対象地域・入力データ棚卸し",
        "",
        f"- 生成日時: {generated_at}",
        f"- 全市区町村管理単位: {len(rows)} 件",
        f"- Phase 2 全域拡張対象: {len(target_rows)} 件",
        f"- 事前確認OK: {len(ready_rows)} 件",
        f"- Phase 1 対象外として保持: {len(excluded_rows)} 件",
        "",
        "## 採用判断",
        "",
        "Phase 2 の「対象地域全域」は、Phase 1 で成果物化した 41 市区町村とする。鹿嶋市・神栖市・東海村は Phase 1 で洪水浸水想定データの対象外として整理済みであるため、Phase 2 の初回全域拡張にも含めない。",
        "",
        "この判断は、Phase 2 の目的が自家用車避難を SUMO 上で再現し、Phase 1 の閉鎖道路・避難経路探索成果と比較可能にすることであるためである。Phase 1 に浸水シナリオと閉鎖道路が存在しない地域を混ぜると、交通挙動の差ではなく入力データ有無の差が比較結果に入る。",
        "",
        "## 出力管理方針",
        "",
        "- 地域別SUMO成果物は `output/sumo/regions/{city_code}/` に集約する。",
        "- 地域別ディレクトリ配下は `network/`, `derived/`, `scenarios/`, `results/`, `viz/` に分ける。",
        "- 既存の常総市単独SUMO成果物 `output/sumo/` は当面維持し、全域拡張版は `regions/` 以下に分離する。",
        "",
        "## 生成ファイル",
        "",
        f"- `{rel(TARGETS_CSV)}`",
        f"- `{rel(INVENTORY_CSV)}`",
        f"- `{rel(INVENTORY_MD)}`",
        "",
    ]

    if missing_rows:
        lines.extend(
            [
                "## 追加確認が必要な対象",
                "",
                *markdown_table(
                    missing_rows,
                    [
                        ("city_code", "コード"),
                        ("city_name", "市区町村"),
                        ("scenario_html", "HTML"),
                        ("scenario_data_js", "data.js"),
                        ("network_graphml", "GraphML"),
                        ("network_edges_gpkg", "edges.gpkg"),
                        ("network_summary_json", "summary"),
                    ],
                ),
                "",
            ]
        )
    else:
        lines.extend(["## 追加確認が必要な対象", "", "現時点では Phase 2 対象41件すべてで前提ファイルが揃っている。", ""])

    lines.extend(
        [
            "## Phase 2 対象地域",
            "",
            *markdown_table(
                target_rows,
                [
                    ("city_code", "コード"),
                    ("city_name", "市区町村"),
                    ("a31a_sources", "A31a"),
                    ("phase2_precheck_ready", "事前確認"),
                    ("phase2_region_dir", "Phase2出力先"),
                ],
            ),
            "",
            "## Phase 1 対象外として保持する地域",
            "",
            *markdown_table(
                excluded_rows,
                [
                    ("city_code", "コード"),
                    ("city_name", "市区町村"),
                    ("exclusion_reason", "理由"),
                ],
            ),
            "",
            "## 次に行う実装",
            "",
            "1. `phase2_region_targets.csv` を入力として、地域別に SUMO ネットワーク変換を行う。",
            "2. 地域別に閉鎖道路・人口重み付き出発需要・避難所目的地を SUMO 用データへ変換する。",
            "3. まず代表3地域で動作確認し、その後41市区町村のバッチ実行に広げる。",
        ]
    )

    MANAGEMENT_DIR.mkdir(parents=True, exist_ok=True)
    INVENTORY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_region_dirs(rows: list[dict[str, str]]) -> None:
    for row in rows:
        if row["include_in_phase2_region"] != "yes":
            continue
        for subdir in row["expected_phase2_subdirs"].split(";"):
            (PROGRAM_DIR / subdir).mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2 全域拡張の対象地域リスト・入力棚卸しを生成する"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["all", "targets", "inventory"],
        help="生成対象。既定値は all",
    )
    parser.add_argument(
        "--create-region-dirs",
        action="store_true",
        help="Phase 2 対象41件の地域別SUMO出力ディレクトリも作成する",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_inventory_rows()

    if args.mode in {"all", "targets"}:
        write_targets_csv(rows)
    if args.mode in {"all", "inventory"}:
        write_inventory_csv(rows)
        write_inventory_markdown(rows)
    if args.create_region_dirs:
        create_region_dirs(rows)

    target_count = sum(1 for row in rows if row["include_in_phase2_region"] == "yes")
    ready_count = sum(1 for row in rows if row["phase2_precheck_ready"] == "yes")
    excluded_count = sum(1 for row in rows if row["phase1_status"] == "excluded_phase1")
    print(
        f"[OK] Phase 2 region inventory generated: "
        f"targets={target_count}, ready={ready_count}, excluded={excluded_count}"
    )
    print(f"  - {rel(TARGETS_CSV)}")
    print(f"  - {rel(INVENTORY_CSV)}")
    print(f"  - {rel(INVENTORY_MD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
