"""
Phase 2 全域拡張: 市区町村別SUMO入力生成・試行実行パイプライン。

このスクリプトは P2-REGION-5〜9 を進めるための地域別実行器である。
常総市単独版の `output/sumo/` は変更せず、出力は
`output/sumo/regions/{city_code}/` に分離する。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

import config
from p2_sumo_env import configure_sumo_environment
from p2_sumo_network import build_region_target, export_osm, run_netconvert


configure_sumo_environment(require_tools=True)
import sumolib  # noqa: E402
import traci  # noqa: E402
import p2_traci_common as traci_common  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"
REGIONS_DIR = SUMO_DIR / "regions"
MANAGEMENT_DIR = REGIONS_DIR / "_management"
TARGETS_CSV = MANAGEMENT_DIR / "phase2_region_targets.csv"

POPULATION_MESH_TXT = (
    PROGRAM_DIR
    / "data"
    / "population_mesh"
    / "5歳階級別人口250メッシュ_茨城"
    / "tblT001178Q08.txt"
)

EDGE_MAPPING_SUMMARY_CSV = MANAGEMENT_DIR / "region_edge_mapping_summary.csv"
DERIVED_SUMMARY_CSV = MANAGEMENT_DIR / "region_derived_summary.csv"
RUN_SUMMARY_CSV = MANAGEMENT_DIR / "region_run_summary.csv"
FULL_PLAN_CSV = MANAGEMENT_DIR / "region_full_execution_plan.csv"
FULL_PLAN_MD = MANAGEMENT_DIR / "region_full_execution_plan.md"
BATCH_STATUS_CSV = MANAGEMENT_DIR / "region_batch_status.csv"
BATCH_STATUS_MD = MANAGEMENT_DIR / "region_batch_status.md"
BATCH_FAILURES_CSV = MANAGEMENT_DIR / "region_batch_failures.csv"
REGION_EVALUATION_CSV = SUMO_DIR / "evaluation" / "evacuation_summary_by_municipality.csv"
REGION_COMPARISON_CSV = SUMO_DIR / "evaluation" / "phase1_phase2_region_comparison.csv"
REGION_INDEX_HTML = REGIONS_DIR / "index.html"

HOUSEHOLD_SIZE = getattr(config, "HOUSEHOLD_SIZE", 2.3)
SEARCH_RADII_M = [100, 250, 500, 1000, 3000, 5000]
FAR_THRESHOLD_M = 500.0
STOP_SPEED_THRESHOLD = 0.1
LONG_STOP_THRESHOLD_SEC = 600
CONGESTION_LOG_INTERVAL_SEC = 60
SIM_DURATION_SEC = int(config.SIM_DURATION_H * 3600)

_MESH_250M_LAT_DEG = 7.5 / 3600
_MESH_250M_LON_DEG = 11.25 / 3600

SCENARIO_SETTINGS = {
    "small": {
        "count_column": "vehicle_count_small",
        "vehicle_prefix": "veh_small",
        "rou": "scenario_a_small.rou.xml",
        "sumocfg": "scenario_a_small.sumocfg",
        "assignments": "scenario_a_small_vehicle_assignments.csv",
        "tripinfo": "scenario_a_small_tripinfo.xml",
        "vehicle_log": "scenario_a_small_vehicle_log.csv",
        "closure_log": "scenario_a_small_closure_log.csv",
        "congestion_log": "scenario_a_small_congestion_log.csv",
        "summary": "scenario_a_small_traci_summary.json",
        "fcd": "scenario_a_small_fcd.xml",
        "fcd_period": "30",
    },
    "10pct": {
        "count_column": "vehicle_count_10pct",
        "vehicle_prefix": "veh_10pct",
        "rou": "scenario_a_10pct.rou.xml",
        "sumocfg": "scenario_a_10pct.sumocfg",
        "assignments": "scenario_a_10pct_vehicle_assignments.csv",
        "tripinfo": "scenario_a_10pct_tripinfo.xml",
        "vehicle_log": "scenario_a_10pct_vehicle_log.csv",
        "closure_log": "scenario_a_10pct_closure_log.csv",
        "congestion_log": "scenario_a_10pct_congestion_log.csv",
        "summary": "scenario_a_10pct_traci_summary.json",
        "fcd": "scenario_a_10pct_fcd.xml",
        "fcd_period": "30",
    },
    "full": {
        "count_column": "vehicle_count_full",
        "vehicle_prefix": "veh_full",
        "rou": "scenario_a.rou.xml",
        "sumocfg": "scenario_a.sumocfg",
        "assignments": "scenario_a_vehicle_assignments.csv",
        "tripinfo": "scenario_a_tripinfo.xml",
        "vehicle_log": "scenario_a_vehicle_log.csv",
        "closure_log": "scenario_a_closure_log.csv",
        "congestion_log": "scenario_a_congestion_log.csv",
        "summary": "scenario_a_traci_summary.json",
        "fcd": "scenario_a_fcd.xml",
        "fcd_period": "60",
    },
}


@dataclass(frozen=True)
class RegionContext:
    city_code: str
    city_name: str
    region_dir: Path
    network_dir: Path
    derived_dir: Path
    scenarios_dir: Path
    results_dir: Path
    viz_dir: Path
    scenario_data_js: Path

    @property
    def net_xml(self) -> Path:
        return self.network_dir / f"{self.city_code}.net.xml"

    @property
    def osm_way_mapping_csv(self) -> Path:
        return self.derived_dir / "phase1_edge_osm_way_mapping.csv"

    @property
    def sumo_edges_csv(self) -> Path:
        return self.derived_dir / "sumo_edges.csv"

    @property
    def phase1_closed_edges_csv(self) -> Path:
        return self.derived_dir / "phase1_closed_edges.csv"

    @property
    def edge_id_mapping_csv(self) -> Path:
        return self.derived_dir / "edge_id_mapping.csv"

    @property
    def edge_mapping_validation_json(self) -> Path:
        return self.derived_dir / "edge_mapping_validation.json"

    @property
    def edge_mapping_unmatched_inspection_csv(self) -> Path:
        return self.derived_dir / "edge_mapping_unmatched_inspection.csv"

    @property
    def edge_mapping_unmatched_inspection_md(self) -> Path:
        return self.derived_dir / "edge_mapping_unmatched_inspection.md"

    @property
    def time_mapping_csv(self) -> Path:
        return self.derived_dir / "time_mapping_sumo.csv"

    @property
    def shelters_safety_csv(self) -> Path:
        return self.derived_dir / "shelters_safety.csv"

    @property
    def agent_origins_csv(self) -> Path:
        return self.derived_dir / "agent_origins_10pct.csv"

    @property
    def agent_origins_sumo_csv(self) -> Path:
        return self.derived_dir / "agent_origins_sumo.csv"

    @property
    def shelters_sumo_csv(self) -> Path:
        return self.derived_dir / "shelters_sumo.csv"

    @property
    def rescue_od_csv(self) -> Path:
        return self.derived_dir / "rescue_od.csv"

    @property
    def snap_validation_json(self) -> Path:
        return self.derived_dir / "snap_validation.json"

    @property
    def closure_timeline_sumo_json(self) -> Path:
        return self.derived_dir / "closure_timeline_sumo.json"

    @property
    def derived_validation_json(self) -> Path:
        return self.derived_dir / "derived_data_validation.json"


def rel(path: Path) -> str:
    try:
        return path.relative_to(PROGRAM_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def read_csv_rows(path: Path, encoding: str = "utf-8-sig") -> list[dict[str, str]]:
    with path.open(newline="", encoding=encoding) as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def upsert_summary(path: Path, key_fields: list[str], row: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = read_csv_rows(path, encoding="utf-8")
    filtered = [
        item
        for item in rows
        if any(str(item.get(key, "")) != str(row.get(key, "")) for key in key_fields)
    ]
    filtered.append(row)
    fieldnames = list(row.keys())
    write_csv(path, fieldnames, filtered)


def load_targets() -> list[dict[str, str]]:
    if not TARGETS_CSV.exists():
        raise FileNotFoundError(f"target CSV not found: {TARGETS_CSV}")
    return read_csv_rows(TARGETS_CSV)


def target_row(city_code: str) -> dict[str, str]:
    for row in load_targets():
        if row["city_code"] == city_code:
            return row
    raise ValueError(f"{city_code} is not a Phase 2 region target")


def context_for(city_code: str) -> RegionContext:
    row = target_row(city_code)
    region_dir = REGIONS_DIR / city_code
    return RegionContext(
        city_code=city_code,
        city_name=row["city_name"],
        region_dir=region_dir,
        network_dir=region_dir / "network",
        derived_dir=region_dir / "derived",
        scenarios_dir=region_dir / "scenarios",
        results_dir=region_dir / "results",
        viz_dir=region_dir / "viz",
        scenario_data_js=OUTPUT_DIR / "scenario_cities" / city_code / "assets" / "data.js",
    )


def ensure_region_dirs(ctx: RegionContext) -> None:
    for path in [ctx.network_dir, ctx.derived_dir, ctx.scenarios_dir, ctx.results_dir, ctx.viz_dir]:
        path.mkdir(parents=True, exist_ok=True)


def load_city_data(ctx: RegionContext) -> dict[str, Any]:
    if not ctx.scenario_data_js.exists():
        raise FileNotFoundError(f"scenario data.js not found: {ctx.scenario_data_js}")
    text = ctx.scenario_data_js.read_text(encoding="utf-8")
    data_text = text.split("=", 1)[1].strip().rstrip(";")
    return json.loads(data_text)


def ensure_network(ctx: RegionContext, force: bool = False) -> None:
    ensure_region_dirs(ctx)
    if force or not ctx.osm_way_mapping_csv.exists():
        target = build_region_target(ctx.city_code)
        export_osm(target)
    if force or not ctx.net_xml.exists():
        target = build_region_target(ctx.city_code)
        run_netconvert(target)


def base_sumo_edge_id(edge_id: str) -> str:
    return edge_id.split("#", 1)[0]


def lane_lengths(edge: ET.Element) -> list[float]:
    values: list[float] = []
    for lane in edge.findall("lane"):
        length = lane.get("length")
        if length:
            values.append(float(length))
    return values


def extract_sumo_edges(ctx: RegionContext) -> list[dict[str, Any]]:
    root = ET.parse(ctx.net_xml).getroot()
    rows: list[dict[str, Any]] = []
    for edge in root.findall("edge"):
        if edge.get("function"):
            continue
        edge_id = edge.get("id", "")
        lengths = lane_lengths(edge)
        rows.append(
            {
                "sumo_edge_id": edge_id,
                "base_sumo_edge_id": base_sumo_edge_id(edge_id),
                "from": edge.get("from", ""),
                "to": edge.get("to", ""),
                "priority": edge.get("priority", ""),
                "lane_count": len(edge.findall("lane")),
                "length_m": max(lengths) if lengths else "",
            }
        )
    write_csv(
        ctx.sumo_edges_csv,
        ["sumo_edge_id", "base_sumo_edge_id", "from", "to", "priority", "lane_count", "length_m"],
        rows,
    )
    return rows


def extract_phase1_closed_edges(ctx: RegionContext, data: dict[str, Any]) -> list[dict[str, Any]]:
    times_by_id = {item["id"]: item for item in data["times"]}
    edge_times: dict[str, set[str]] = defaultdict(set)
    for time_id, edge_ids in data["closures"].items():
        for edge_id in edge_ids:
            edge_times[str(edge_id)].add(time_id)

    rows: list[dict[str, Any]] = []
    for edge_id in sorted(edge_times):
        time_ids = sorted(edge_times[edge_id])
        timestamps = [times_by_id[time_id]["timestamp"] for time_id in time_ids if time_id in times_by_id]
        rows.append(
            {
                "phase1_edge_id": edge_id,
                "closed_time_count": len(time_ids),
                "first_time_id": time_ids[0],
                "first_timestamp": timestamps[0] if timestamps else "",
                "time_ids": ";".join(time_ids),
                "timestamps": ";".join(timestamps),
            }
        )
    write_csv(
        ctx.phase1_closed_edges_csv,
        ["phase1_edge_id", "closed_time_count", "first_time_id", "first_timestamp", "time_ids", "timestamps"],
        rows,
    )
    return rows


def parse_phase1_edge_id(edge_id: str) -> tuple[str, str, str]:
    match = re.match(r"^(.+)_(.+)_([^_]+)$", edge_id)
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3)


def split_sumo_edge_ids(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split(";") if item]


def write_edge_mapping_validation(
    ctx: RegionContext,
    sumo_edge_count: int,
    phase1_closed_edge_count: int,
    mapping_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = defaultdict(int)
    total_sumo_segments = 0
    for row in mapping_rows:
        status_counts[str(row.get("mapping_status", ""))] += 1
        total_sumo_segments += int(float(row.get("sumo_edge_count") or 0))

    summary = {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "sumo_edge_count": sumo_edge_count,
        "phase1_closed_edge_count": phase1_closed_edge_count,
        "mapping_count": len(mapping_rows),
        "matched_count": status_counts.get("matched", 0),
        "unmatched_count": status_counts.get("unmatched", 0),
        "excluded_unmapped_count": status_counts.get("excluded_unmapped", 0),
        "total_mapped_sumo_edge_segments": total_sumo_segments,
        "can_proceed_to_region_closure": status_counts.get("unmatched", 0) == 0,
        "edge_id_mapping_csv": rel(ctx.edge_id_mapping_csv),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ctx.edge_mapping_validation_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    upsert_summary(EDGE_MAPPING_SUMMARY_CSV, ["city_code"], summary)
    return summary


def generate_edge_mapping(ctx: RegionContext, force_network: bool = False) -> dict[str, Any]:
    ensure_network(ctx, force=force_network)
    data = load_city_data(ctx)
    sumo_edges = extract_sumo_edges(ctx)
    closed_edges = extract_phase1_closed_edges(ctx, data)

    sumo_by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sumo_edges:
        sumo_by_base[str(row["base_sumo_edge_id"])].append(row)

    way_rows = read_csv_rows(ctx.osm_way_mapping_csv, encoding="utf-8")
    way_by_phase1 = {row["phase1_edge_id"]: row for row in way_rows}

    mapping_rows: list[dict[str, Any]] = []
    for closed in closed_edges:
        phase1_edge_id = closed["phase1_edge_id"]
        u, v, key = parse_phase1_edge_id(phase1_edge_id)
        way = way_by_phase1.get(phase1_edge_id)
        if not way:
            mapping_rows.append(
                {
                    "phase1_edge_id": phase1_edge_id,
                    "u": u,
                    "v": v,
                    "key": key,
                    "osmid": "",
                    "phase2_osm_way_id": "",
                    "sumo_edge_id": "",
                    "sumo_edge_count": 0,
                    "mapping_method": "synthetic_way_id_prefix",
                    "mapping_status": "unmatched",
                    "closed_time_count": closed["closed_time_count"],
                    "first_time_id": closed["first_time_id"],
                    "first_timestamp": closed["first_timestamp"],
                    "notes": "phase1 edge was not found in phase1_edge_osm_way_mapping.csv",
                }
            )
            continue
        way_id = way["phase2_osm_way_id"]
        matched_edges = sorted(sumo_by_base.get(way_id, []), key=lambda item: item["sumo_edge_id"])
        sumo_ids = [item["sumo_edge_id"] for item in matched_edges]
        status = "matched" if sumo_ids else "unmatched"
        mapping_rows.append(
            {
                "phase1_edge_id": phase1_edge_id,
                "u": way["u"],
                "v": way["v"],
                "key": way["key"],
                "osmid": way["osmid"],
                "phase2_osm_way_id": way_id,
                "sumo_edge_id": ";".join(sumo_ids),
                "sumo_edge_count": len(sumo_ids),
                "mapping_method": "synthetic_way_id_prefix",
                "mapping_status": status,
                "closed_time_count": closed["closed_time_count"],
                "first_time_id": closed["first_time_id"],
                "first_timestamp": closed["first_timestamp"],
                "notes": "" if status == "matched" else "SUMO edge with matching base ID was not found",
            }
        )

    write_csv(
        ctx.edge_id_mapping_csv,
        [
            "phase1_edge_id",
            "u",
            "v",
            "key",
            "osmid",
            "phase2_osm_way_id",
            "sumo_edge_id",
            "sumo_edge_count",
            "mapping_method",
            "mapping_status",
            "closed_time_count",
            "first_time_id",
            "first_timestamp",
            "notes",
        ],
        mapping_rows,
    )

    summary = write_edge_mapping_validation(ctx, len(sumo_edges), len(closed_edges), mapping_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def limited_join(values: list[str], limit: int = 20) -> str:
    unique = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    clipped = unique[:limit]
    suffix = f";...(+{len(unique) - limit})" if len(unique) > limit else ""
    return ";".join(clipped) + suffix


def inspect_unmatched_edge_mapping(ctx: RegionContext) -> dict[str, Any]:
    if not ctx.edge_id_mapping_csv.exists():
        generate_edge_mapping(ctx)
    if not ctx.sumo_edges_csv.exists():
        extract_sumo_edges(ctx)

    mapping_rows = read_csv_rows(ctx.edge_id_mapping_csv, encoding="utf-8")
    sumo_edges = read_csv_rows(ctx.sumo_edges_csv, encoding="utf-8")
    way_rows = read_csv_rows(ctx.osm_way_mapping_csv, encoding="utf-8") if ctx.osm_way_mapping_csv.exists() else []
    way_by_phase1 = {row["phase1_edge_id"]: row for row in way_rows}

    rows: list[dict[str, Any]] = []
    for row in mapping_rows:
        if row.get("mapping_status") != "unmatched":
            continue
        u = str(row.get("u", ""))
        v = str(row.get("v", ""))
        way = way_by_phase1.get(row.get("phase1_edge_id", ""), {})
        from_u = [edge["sumo_edge_id"] for edge in sumo_edges if str(edge.get("from", "")) == u]
        to_u = [edge["sumo_edge_id"] for edge in sumo_edges if str(edge.get("to", "")) == u]
        from_v = [edge["sumo_edge_id"] for edge in sumo_edges if str(edge.get("from", "")) == v]
        to_v = [edge["sumo_edge_id"] for edge in sumo_edges if str(edge.get("to", "")) == v]
        adjacent_count = len(set(from_u + to_u + from_v + to_v))
        recommendation = (
            "exclude_unmapped_edge"
            if adjacent_count > 0
            else "manual_review_required_no_adjacent_sumo_edge"
        )
        rationale = (
            "対象phase1 edgeのsynthetic way IDに対応する通常SUMO edgeが生成されていない。"
            "近接junctionには通常edgeがあるが、代替閉鎖すると過剰閉鎖になり得るため、"
            "Phase 2全域試行では未対応edgeとして明示除外する。"
            if adjacent_count > 0
            else "対応する通常SUMO edgeと近接通常edgeの双方が確認できないため、手動確認を要する。"
        )
        rows.append(
            {
                "city_code": ctx.city_code,
                "city_name": ctx.city_name,
                "phase1_edge_id": row.get("phase1_edge_id", ""),
                "u": u,
                "v": v,
                "key": row.get("key", ""),
                "osmid": row.get("osmid", ""),
                "phase2_osm_way_id": row.get("phase2_osm_way_id", ""),
                "closed_time_count": row.get("closed_time_count", ""),
                "first_time_id": row.get("first_time_id", ""),
                "first_timestamp": row.get("first_timestamp", ""),
                "way_highway": way.get("highway", ""),
                "way_length_m": way.get("length_m", ""),
                "way_geometry_point_count": way.get("geometry_point_count", ""),
                "adjacent_from_u": limited_join(from_u),
                "adjacent_to_u": limited_join(to_u),
                "adjacent_from_v": limited_join(from_v),
                "adjacent_to_v": limited_join(to_v),
                "adjacent_normal_edge_count": adjacent_count,
                "recommendation": recommendation,
                "rationale": rationale,
            }
        )

    fieldnames = [
        "city_code",
        "city_name",
        "phase1_edge_id",
        "u",
        "v",
        "key",
        "osmid",
        "phase2_osm_way_id",
        "closed_time_count",
        "first_time_id",
        "first_timestamp",
        "way_highway",
        "way_length_m",
        "way_geometry_point_count",
        "adjacent_from_u",
        "adjacent_to_u",
        "adjacent_from_v",
        "adjacent_to_v",
        "adjacent_normal_edge_count",
        "recommendation",
        "rationale",
    ]
    write_csv(ctx.edge_mapping_unmatched_inspection_csv, fieldnames, rows)

    lines = [
        f"# {ctx.city_name} ({ctx.city_code}) 未対応edge調査",
        "",
        f"- 生成日時: {datetime.now().isoformat(timespec='seconds')}",
        f"- 未対応edge数: {len(rows)}",
        "- 採用方針: 近隣edgeへの自動代替閉鎖は行わず、SUMO通常edgeが生成されなかった閉鎖edgeは `excluded_unmapped` として明示除外する。",
        "- 理由: junction周辺の別edgeを閉鎖すると本来閉鎖対象ではない流入・流出方向まで止める可能性があり、2件の欠落を補う効果より過剰閉鎖による歪みが大きい。",
        "",
    ]
    if rows:
        lines.extend(
            [
                "| phase1_edge_id | phase2_osm_way_id | 初回時点 | 閉鎖時点数 | 近接通常edge数 | 推奨 |",
                "|---|---|---|---:|---:|---|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['phase1_edge_id']} | {row['phase2_osm_way_id']} | {row['first_time_id']} | "
                f"{row['closed_time_count']} | {row['adjacent_normal_edge_count']} | {row['recommendation']} |"
            )
    else:
        lines.append("未対応edgeはありません。")
    ctx.edge_mapping_unmatched_inspection_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "unmatched_count": len(rows),
        "inspection_csv": rel(ctx.edge_mapping_unmatched_inspection_csv),
        "inspection_md": rel(ctx.edge_mapping_unmatched_inspection_md),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def apply_unmatched_policy(ctx: RegionContext, policy: str = "exclude") -> dict[str, Any]:
    if policy != "exclude":
        raise ValueError(f"unsupported unmatched policy: {policy}")
    if not ctx.edge_id_mapping_csv.exists():
        generate_edge_mapping(ctx)
    inspection = inspect_unmatched_edge_mapping(ctx)
    rows = read_csv_rows(ctx.edge_id_mapping_csv, encoding="utf-8")
    changed = 0
    for row in rows:
        if row.get("mapping_status") != "unmatched":
            continue
        row["mapping_status"] = "excluded_unmapped"
        row["mapping_method"] = "synthetic_way_id_prefix+exclude_unmapped_policy"
        row["sumo_edge_id"] = ""
        row["sumo_edge_count"] = "0"
        row["notes"] = (
            "excluded by Phase 2 policy: matching SUMO normal edge was not generated; "
            "adjacent-edge substitution was avoided to prevent over-closure"
        )
        changed += 1

    if rows:
        write_csv(ctx.edge_id_mapping_csv, list(rows[0].keys()), rows)

    previous = read_json_if_exists(ctx.edge_mapping_validation_json)
    sumo_edge_count = int(previous.get("sumo_edge_count", 0) or 0)
    if sumo_edge_count == 0 and ctx.sumo_edges_csv.exists():
        sumo_edge_count = len(read_csv_rows(ctx.sumo_edges_csv, encoding="utf-8"))
    phase1_closed_edge_count = int(previous.get("phase1_closed_edge_count", 0) or 0)
    if phase1_closed_edge_count == 0 and ctx.phase1_closed_edges_csv.exists():
        phase1_closed_edge_count = len(read_csv_rows(ctx.phase1_closed_edges_csv, encoding="utf-8"))
    validation = write_edge_mapping_validation(ctx, sumo_edge_count, phase1_closed_edge_count, rows)
    summary = {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "policy": policy,
        "changed_count": changed,
        "inspection": inspection,
        "validation": validation,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def generate_time_mapping(ctx: RegionContext, data: dict[str, Any]) -> list[dict[str, Any]]:
    start = parse_dt(config.SIM_START_EPOCH)
    times = data["times"]
    timestamps = [parse_dt(item["timestamp"]) for item in times]
    max_elapsed = int((timestamps[-1] - start).total_seconds())
    rows: list[dict[str, Any]] = []
    for item, ts in zip(times, timestamps):
        elapsed = int((ts - start).total_seconds())
        sim_time = round(elapsed / max_elapsed * SIM_DURATION_SEC)
        rows.append(
            {
                "time_id": item["id"],
                "source_timestamp": ts.isoformat(),
                "elapsed_sec_real": elapsed,
                "sim_time_sec": int(sim_time),
                "compression_ratio": sim_time / elapsed if elapsed else "",
                "notes": "linear_compression_to_6h",
            }
        )
    write_csv(
        ctx.time_mapping_csv,
        ["time_id", "source_timestamp", "elapsed_sec_real", "sim_time_sec", "compression_ratio", "notes"],
        rows,
    )
    return rows


def flood_union(data: dict[str, Any], time_id: str = "t7"):
    features = data["floods"][time_id]["features"]
    if not features:
        return None
    return unary_union([shape(feature["geometry"]) for feature in features])


def generate_shelters_safety(ctx: RegionContext, data: dict[str, Any]) -> list[dict[str, Any]]:
    flood = flood_union(data, "t7")
    rows: list[dict[str, Any]] = []
    for idx, shelter in enumerate(data["shelters"], start=1):
        shelter_id = str(shelter.get("id") or f"shelter_{idx:03d}")
        lon = float(shelter["lon"])
        lat = float(shelter["lat"])
        flood_risk = bool(flood is not None and flood.intersects(Point(lon, lat)))
        rows.append(
            {
                "shelter_id": shelter_id,
                "name": shelter.get("name", shelter_id),
                "capacity": shelter.get("capacity", ""),
                "lon": lon,
                "lat": lat,
                "flood_risk": flood_risk,
                "max_water_depth_code": "",
                "is_safe_destination": not flood_risk,
                "exclusion_reason": "inside_max_scenario_flood" if flood_risk else "",
                "notes": "from_city_scenario_data",
            }
        )

    if rows and not any(bool(row["is_safe_destination"]) for row in rows):
        for row in rows:
            row["is_safe_destination"] = True
            row["exclusion_reason"] = ""
            row["notes"] = "retained_because_no_safe_shelter_after_scenario_flood_check"

    write_csv(
        ctx.shelters_safety_csv,
        [
            "shelter_id",
            "name",
            "capacity",
            "lon",
            "lat",
            "flood_risk",
            "max_water_depth_code",
            "is_safe_destination",
            "exclusion_reason",
            "notes",
        ],
        rows,
    )
    return rows


def meshcode_to_lon_lat(key_code: str) -> tuple[float, float]:
    key = str(key_code).zfill(10)
    p, u = int(key[0:2]), int(key[2:4])
    q, v = int(key[4]), int(key[5])
    r, w = int(key[6]), int(key[7])
    s, x = int(key[8]), int(key[9])
    lat = p / 1.5 + q * 5 / 60 + (r * 30 + s * 7.5 + 3.75) / 3600
    lon = 100 + u + v * 0.125 + (w * 45 + x * 11.25 + 5.625) / 3600
    return lon, lat


def read_mesh_table() -> pd.DataFrame:
    raw = pd.read_csv(POPULATION_MESH_TXT, encoding="shift_jis", header=None, dtype=str)
    header = raw.iloc[0].tolist()
    if any(("KEY_CODE" in str(x)) or ("メッシュ" in str(x)) for x in header):
        df = raw.iloc[2:].copy()
        df.columns = header
    else:
        df = raw.copy()
        df.columns = [f"col_{i}" for i in range(df.shape[1])]
    return df


def find_col(candidates: list[str], columns: list[str], default: str) -> str:
    for column in columns:
        if any(key in str(column) for key in candidates):
            return column
    return default


def full_vehicle_count(total_pop: int) -> int:
    if total_pop <= 0:
        return 0
    return max(1, math.ceil(total_pop / HOUSEHOLD_SIZE))


def ten_percent_vehicle_count(vehicle_count_full: int) -> int:
    if vehicle_count_full <= 0:
        return 0
    return max(1, math.ceil(vehicle_count_full / 10))


def generate_agent_origins(ctx: RegionContext, data: dict[str, Any]) -> list[dict[str, Any]]:
    flood = flood_union(data, "t7")
    if flood is None or flood.is_empty:
        rows: list[dict[str, Any]] = []
        write_csv(
            ctx.agent_origins_csv,
            [
                "origin_id",
                "KEY_CODE",
                "lon",
                "lat",
                "total_pop",
                "elderly_pop",
                "estimated_households",
                "vehicle_count_full",
                "vehicle_count_10pct_raw",
                "vehicle_count_10pct",
                "vehicle_count_small",
                "notes",
            ],
            rows,
        )
        return rows

    prepared_flood = prep(flood)
    minx, miny, maxx, maxy = flood.bounds
    df = read_mesh_table()
    key_col = find_col(["KEY_CODE", "メッシュ"], list(df.columns), "col_0")
    total_col = "T001178001" if "T001178001" in df.columns else "col_4"
    elderly_cols = [
        c for c in ["T001178043", "T001178046", "T001178049", "T001178052", "T001178055"]
        if c in df.columns
    ]
    if not elderly_cols:
        elderly_cols = ["col_46", "col_49", "col_52", "col_55", "col_58"]

    work = df[[key_col, total_col, *elderly_cols]].copy()
    work = work.rename(columns={key_col: "KEY_CODE", total_col: "total_pop"})
    work["KEY_CODE"] = work["KEY_CODE"].astype(str).str.zfill(10)
    work[["lon", "lat"]] = work["KEY_CODE"].apply(lambda key: pd.Series(meshcode_to_lon_lat(key)))
    work = work[
        (work["lon"] >= minx - _MESH_250M_LON_DEG)
        & (work["lon"] <= maxx + _MESH_250M_LON_DEG)
        & (work["lat"] >= miny - _MESH_250M_LAT_DEG)
        & (work["lat"] <= maxy + _MESH_250M_LAT_DEG)
    ].copy()
    work["total_pop"] = pd.to_numeric(work["total_pop"], errors="coerce").fillna(0).astype(int)
    work["elderly_pop"] = (
        work[elderly_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1).astype(int)
    )

    rows: list[dict[str, Any]] = []
    seq = 1
    for row in work.itertuples():
        cell = box(
            row.lon - _MESH_250M_LON_DEG / 2,
            row.lat - _MESH_250M_LAT_DEG / 2,
            row.lon + _MESH_250M_LON_DEG / 2,
            row.lat + _MESH_250M_LAT_DEG / 2,
        )
        if not prepared_flood.intersects(cell):
            continue
        total_pop = int(row.total_pop)
        elderly_pop = int(row.elderly_pop)
        vehicles_full = full_vehicle_count(total_pop)
        vehicles_10_raw = vehicles_full / 10 if vehicles_full > 0 else 0
        rows.append(
            {
                "origin_id": f"origin_{seq:04d}",
                "KEY_CODE": row.KEY_CODE,
                "lon": float(row.lon),
                "lat": float(row.lat),
                "total_pop": total_pop,
                "elderly_pop": elderly_pop,
                "estimated_households": round(total_pop / HOUSEHOLD_SIZE, 3) if total_pop > 0 else 0,
                "vehicle_count_full": vehicles_full,
                "vehicle_count_10pct_raw": round(vehicles_10_raw, 3),
                "vehicle_count_10pct": ten_percent_vehicle_count(vehicles_full),
                "vehicle_count_small": 1 if total_pop > 0 else 0,
                "notes": "mesh_intersects_max_city_scenario_flood",
            }
        )
        seq += 1

    write_csv(
        ctx.agent_origins_csv,
        [
            "origin_id",
            "KEY_CODE",
            "lon",
            "lat",
            "total_pop",
            "elderly_pop",
            "estimated_households",
            "vehicle_count_full",
            "vehicle_count_10pct_raw",
            "vehicle_count_10pct",
            "vehicle_count_small",
            "notes",
        ],
        rows,
    )
    return rows


def nearest_edge(net: Any, lon: float, lat: float) -> tuple[str, float, str]:
    x, y = net.convertLonLat2XY(lon, lat)
    candidates = []
    for radius in SEARCH_RADII_M:
        candidates = net.getNeighboringEdges(x, y, r=radius)
        if candidates:
            break
    if not candidates:
        return "", float("nan"), "unmatched"
    edge, distance = min(candidates, key=lambda item: item[1])
    status = "matched" if distance <= FAR_THRESHOLD_M else "far"
    return edge.getID(), float(distance), status


def max_numeric_or_none(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.max())


def snap_points(ctx: RegionContext) -> dict[str, Any]:
    net = sumolib.net.readNet(str(ctx.net_xml))
    origins = pd.read_csv(ctx.agent_origins_csv, dtype={"KEY_CODE": str})
    shelters = pd.read_csv(ctx.shelters_safety_csv)

    origin_rows: list[dict[str, Any]] = []
    for _, row in origins.iterrows():
        edge_id, distance, status = nearest_edge(net, float(row["lon"]), float(row["lat"]))
        origin_rows.append(
            {
                "origin_id": row["origin_id"],
                "KEY_CODE": row["KEY_CODE"],
                "lon": row["lon"],
                "lat": row["lat"],
                "sumo_edge_id": edge_id,
                "snap_distance_m": round(distance, 3) if pd.notna(distance) else "",
                "vehicle_count_small": int(row["vehicle_count_small"]),
                "vehicle_count_10pct": int(row["vehicle_count_10pct"]),
                "vehicle_count_full": int(row["vehicle_count_full"]),
                "snap_status": status,
            }
        )
    write_csv(
        ctx.agent_origins_sumo_csv,
        [
            "origin_id",
            "KEY_CODE",
            "lon",
            "lat",
            "sumo_edge_id",
            "snap_distance_m",
            "vehicle_count_small",
            "vehicle_count_10pct",
            "vehicle_count_full",
            "snap_status",
        ],
        origin_rows,
    )

    shelter_rows: list[dict[str, Any]] = []
    for _, row in shelters.iterrows():
        is_safe = str(row["is_safe_destination"]).lower() == "true"
        if is_safe:
            edge_id, distance, status = nearest_edge(net, float(row["lon"]), float(row["lat"]))
        else:
            edge_id, distance, status = "", float("nan"), "excluded_flood_risk"
        shelter_rows.append(
            {
                "shelter_id": row["shelter_id"],
                "name": row["name"],
                "lon": row["lon"],
                "lat": row["lat"],
                "capacity": row["capacity"],
                "is_safe_destination": is_safe,
                "sumo_edge_id": edge_id,
                "snap_distance_m": round(distance, 3) if pd.notna(distance) else "",
                "snap_status": status,
            }
        )
    write_csv(
        ctx.shelters_sumo_csv,
        [
            "shelter_id",
            "name",
            "lon",
            "lat",
            "capacity",
            "is_safe_destination",
            "sumo_edge_id",
            "snap_distance_m",
            "snap_status",
        ],
        shelter_rows,
    )

    origins_df = pd.DataFrame(origin_rows)
    shelters_df = pd.DataFrame(shelter_rows)
    safe_shelters = shelters_df[shelters_df["is_safe_destination"] == True]  # noqa: E712
    routable_origins = origins_df[
        (origins_df["snap_status"] != "unmatched") & (origins_df["sumo_edge_id"].astype(str).str.len() > 0)
    ] if len(origins_df) else origins_df
    routable_safe_shelters = safe_shelters[
        (safe_shelters["snap_status"] != "unmatched")
        & (safe_shelters["sumo_edge_id"].astype(str).str.len() > 0)
    ] if len(safe_shelters) else safe_shelters
    summary = {
        "origin_count": int(len(origins_df)),
        "origin_unmatched_count": int((origins_df["snap_status"] == "unmatched").sum()) if len(origins_df) else 0,
        "origin_far_count": int((origins_df["snap_status"] == "far").sum()) if len(origins_df) else 0,
        "origin_routable_count": int(len(routable_origins)),
        "origin_max_snap_distance_m": max_numeric_or_none(origins_df["snap_distance_m"]) if len(origins_df) else None,
        "shelter_count": int(len(shelters_df)),
        "safe_shelter_count": int(len(safe_shelters)),
        "safe_shelter_unmatched_count": int((safe_shelters["snap_status"] == "unmatched").sum())
        if len(safe_shelters)
        else 0,
        "safe_shelter_routable_count": int(len(routable_safe_shelters)),
        "safe_shelter_max_snap_distance_m": max_numeric_or_none(safe_shelters["snap_distance_m"])
        if len(safe_shelters)
        else None,
        "can_proceed_to_route_generation": bool(
            len(routable_origins) > 0
            and len(routable_safe_shelters) > 0
        ),
        "snap_exclusion_policy": (
            "unmatched origins/shelters are excluded from SUMO route generation when at least one routable "
            "origin and safe shelter remain"
        ),
    }
    ctx.snap_validation_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def generate_closure_timeline_sumo(ctx: RegionContext, data: dict[str, Any]) -> dict[str, Any]:
    time_mapping = pd.read_csv(ctx.time_mapping_csv)
    edge_mapping = pd.read_csv(ctx.edge_id_mapping_csv)
    mapping_by_phase1 = {
        row["phase1_edge_id"]: {
            "sumo_ids": split_sumo_edge_ids(row["sumo_edge_id"]),
            "mapping_status": str(row.get("mapping_status", "")),
        }
        for _, row in edge_mapping.iterrows()
    }
    closures = []
    for _, time_row in time_mapping.iterrows():
        time_id = time_row["time_id"]
        phase1_ids = data["closures"].get(time_id, [])
        closed_sumo_ids: set[str] = set()
        unmapped: list[str] = []
        excluded_unmapped: list[str] = []
        for phase1_edge_id in phase1_ids:
            mapping = mapping_by_phase1.get(phase1_edge_id)
            if not mapping:
                unmapped.append(phase1_edge_id)
                continue
            sumo_ids = mapping["sumo_ids"]
            if not sumo_ids:
                if mapping["mapping_status"] == "excluded_unmapped":
                    excluded_unmapped.append(phase1_edge_id)
                    continue
                unmapped.append(phase1_edge_id)
                continue
            closed_sumo_ids.update(sumo_ids)
        closures.append(
            {
                "time_id": time_id,
                "source_timestamp": time_row["source_timestamp"],
                "sim_time_sec": int(time_row["sim_time_sec"]),
                "phase1_edge_count": len(phase1_ids),
                "closed_sumo_edge_ids": sorted(closed_sumo_ids),
                "closed_sumo_edge_count": len(closed_sumo_ids),
                "unmapped_phase1_edge_ids": sorted(unmapped),
                "unmapped_phase1_edge_count": len(unmapped),
                "excluded_unmapped_phase1_edge_ids": sorted(excluded_unmapped),
                "excluded_unmapped_phase1_edge_count": len(excluded_unmapped),
            }
        )
    output = {
        "metadata": {
            "city_code": ctx.city_code,
            "city_name": ctx.city_name,
            "source": rel(ctx.scenario_data_js),
            "edge_mapping": rel(ctx.edge_id_mapping_csv),
            "time_mapping": rel(ctx.time_mapping_csv),
            "closure_rule": "city_scenario_closure_edges",
            "sim_duration_sec": SIM_DURATION_SEC,
        },
        "closures": closures,
    }
    ctx.closure_timeline_sumo_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def generate_region_derived(ctx: RegionContext) -> dict[str, Any]:
    if not ctx.edge_id_mapping_csv.exists():
        generate_edge_mapping(ctx)
    data = load_city_data(ctx)
    time_rows = generate_time_mapping(ctx, data)
    shelter_rows = generate_shelters_safety(ctx, data)
    origin_rows = generate_agent_origins(ctx, data)
    closure_timeline = generate_closure_timeline_sumo(ctx, data)
    snap_summary = snap_points(ctx)
    rescue_summary = generate_rescue_od(ctx)
    closure_unmapped_time_steps = sum(
        1 for item in closure_timeline["closures"] if item["unmapped_phase1_edge_ids"]
    )
    closure_excluded_unmapped_time_steps = sum(
        1 for item in closure_timeline["closures"] if item.get("excluded_unmapped_phase1_edge_ids")
    )
    closure_excluded_unmapped_edge_count = len(
        {
            edge_id
            for item in closure_timeline["closures"]
            for edge_id in item.get("excluded_unmapped_phase1_edge_ids", [])
        }
    )

    summary = {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "time_mapping_rows": len(time_rows),
        "shelter_count": len(shelter_rows),
        "safe_shelter_count": sum(1 for row in shelter_rows if bool(row["is_safe_destination"])),
        "origin_count": len(origin_rows),
        "vehicle_count_small_total": sum(int(row["vehicle_count_small"]) for row in origin_rows),
        "vehicle_count_10pct_total": sum(int(row["vehicle_count_10pct"]) for row in origin_rows),
        "vehicle_count_full_total": sum(int(row["vehicle_count_full"]) for row in origin_rows),
        "phase3_private_vehicle_count_total": rescue_summary["private_vehicle_count_total"],
        "phase3_rescue_vehicle_count_total": rescue_summary["rescue_vehicle_count_total"],
        "phase3_non_car_households_total": rescue_summary["non_car_households_total"],
        "closure_time_steps": len(closure_timeline["closures"]),
        "closure_unmapped_time_steps": closure_unmapped_time_steps,
        "closure_excluded_unmapped_time_steps": closure_excluded_unmapped_time_steps,
        "closure_excluded_unmapped_edge_count": closure_excluded_unmapped_edge_count,
        "origin_unmatched_count": snap_summary["origin_unmatched_count"],
        "origin_routable_count": snap_summary["origin_routable_count"],
        "safe_shelter_unmatched_count": snap_summary["safe_shelter_unmatched_count"],
        "safe_shelter_routable_count": snap_summary["safe_shelter_routable_count"],
        "can_proceed_to_small": bool(
            snap_summary["can_proceed_to_route_generation"] and closure_unmapped_time_steps == 0
        ),
        "derived_validation_json": rel(ctx.derived_validation_json),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ctx.derived_validation_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    upsert_summary(DERIVED_SUMMARY_CSV, ["city_code"], summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def read_net(ctx: RegionContext):
    return sumolib.net.readNet(str(ctx.net_xml))


def net_xy(net: Any, lon: float, lat: float) -> tuple[float, float]:
    x, y = net.convertLonLat2XY(lon, lat)
    return float(x), float(y)


def nearest_shelter(net: Any, origin: pd.Series, shelters: pd.DataFrame) -> pd.Series:
    ox, oy = net_xy(net, float(origin["lon"]), float(origin["lat"]))
    candidates = []
    for _, shelter in shelters.iterrows():
        sx, sy = net_xy(net, float(shelter["lon"]), float(shelter["lat"]))
        dist2 = (ox - sx) ** 2 + (oy - sy) ** 2
        same_edge_penalty = 1_000_000_000 if shelter["sumo_edge_id"] == origin["sumo_edge_id"] else 0
        candidates.append((dist2 + same_edge_penalty, shelter))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def allocate_integer_counts(raw_values: pd.Series, target_total: int) -> list[int]:
    floors = raw_values.apply(math.floor).astype(int)
    remainder_count = max(0, int(target_total) - int(floors.sum()))
    if remainder_count == 0:
        return floors.tolist()

    fractions = raw_values - floors
    order = fractions.sort_values(ascending=False, kind="mergesort").index[:remainder_count]
    counts = floors.copy()
    counts.loc[order] = counts.loc[order] + 1
    return counts.tolist()


def generate_rescue_od(ctx: RegionContext) -> dict[str, Any]:
    net = read_net(ctx)
    origins = pd.read_csv(ctx.agent_origins_csv, dtype={"KEY_CODE": str})
    origin_edges = pd.read_csv(
        ctx.agent_origins_sumo_csv,
        dtype={"KEY_CODE": str, "sumo_edge_id": str},
    )
    shelters = pd.read_csv(ctx.shelters_sumo_csv)
    safe_shelters = shelters[
        (shelters["is_safe_destination"].astype(str).str.lower() == "true")
        & (shelters["snap_status"].astype(str) != "unmatched")
        & (shelters["sumo_edge_id"].fillna("").astype(str).str.len() > 0)
    ].copy()
    if safe_shelters.empty:
        raise ValueError(f"{ctx.city_code}: no routable safe shelter is available for rescue OD")

    merged = origins.merge(
        origin_edges[
            [
                "origin_id",
                "sumo_edge_id",
                "snap_distance_m",
                "snap_status",
            ]
        ],
        on="origin_id",
        how="left",
        suffixes=("", "_snap"),
    )
    merged = merged[merged["snap_status"].astype(str) != "unmatched"].copy()

    household_size = float(getattr(config, "HOUSEHOLD_SIZE", HOUSEHOLD_SIZE))
    non_car_rate = float(getattr(config, "NON_CAR_RATE", 0.15))
    rescue_rate = float(getattr(config, "RESCUE_RATE_R", 1.0))
    cars_per_household = float(getattr(config, "CARS_PER_HOUSEHOLD", 1.0))

    merged["estimated_households_phase3"] = merged["total_pop"].astype(float) / household_size
    merged["car_owning_households"] = merged["estimated_households_phase3"] * (1 - non_car_rate)
    merged["non_car_households"] = merged["estimated_households_phase3"] * non_car_rate
    merged["rescue_vehicle_count_raw"] = merged["non_car_households"] * rescue_rate
    rescue_total = int(round(float(merged["rescue_vehicle_count_raw"].sum())))
    merged["rescue_vehicle_count"] = allocate_integer_counts(
        merged["rescue_vehicle_count_raw"],
        rescue_total,
    )
    merged["private_vehicle_count_raw"] = merged["car_owning_households"] * cars_per_household
    merged["private_vehicle_count"] = (
        merged["vehicle_count_full"].astype(int) - merged["rescue_vehicle_count"].astype(int)
    ).clip(lower=0)

    rows: list[dict[str, Any]] = []
    for _, origin in merged.iterrows():
        shelter = nearest_shelter(net, origin, safe_shelters)
        rows.append(
            {
                "origin_id": origin["origin_id"],
                "KEY_CODE": origin["KEY_CODE"],
                "lon": origin["lon"],
                "lat": origin["lat"],
                "total_pop": int(origin["total_pop"]),
                "elderly_pop": int(origin["elderly_pop"]),
                "estimated_households": round(float(origin["estimated_households_phase3"]), 3),
                "car_owning_households": round(float(origin["car_owning_households"]), 3),
                "non_car_households": round(float(origin["non_car_households"]), 3),
                "private_vehicle_count_raw": round(float(origin["private_vehicle_count_raw"]), 3),
                "private_vehicle_count": int(origin["private_vehicle_count"]),
                "rescue_vehicle_count_raw": round(float(origin["rescue_vehicle_count_raw"]), 3),
                "rescue_vehicle_count": int(origin["rescue_vehicle_count"]),
                "rescue_start_edge_id": origin["sumo_edge_id"],
                "pickup_edge_id": origin["sumo_edge_id"],
                "pickup_stop_duration_s": int(getattr(config, "RESCUE_STOP_DURATION_S", 60)),
                "shelter_id": shelter["shelter_id"],
                "shelter_name": shelter["name"],
                "shelter_edge_id": shelter["sumo_edge_id"],
                "snap_status": origin["snap_status"],
                "notes": "same_mesh_rescue_start_largest_remainder_rounding",
            }
        )

    write_csv(
        ctx.rescue_od_csv,
        [
            "origin_id",
            "KEY_CODE",
            "lon",
            "lat",
            "total_pop",
            "elderly_pop",
            "estimated_households",
            "car_owning_households",
            "non_car_households",
            "private_vehicle_count_raw",
            "private_vehicle_count",
            "rescue_vehicle_count_raw",
            "rescue_vehicle_count",
            "rescue_start_edge_id",
            "pickup_edge_id",
            "pickup_stop_duration_s",
            "shelter_id",
            "shelter_name",
            "shelter_edge_id",
            "snap_status",
            "notes",
        ],
        rows,
    )
    return {
        "rescue_od_rows": len(rows),
        "non_car_households_total": round(float(merged["non_car_households"].sum()), 3),
        "private_vehicle_count_total": int(merged["private_vehicle_count"].sum()),
        "rescue_vehicle_count_total": int(merged["rescue_vehicle_count"].sum()),
        "rescue_od_csv": rel(ctx.rescue_od_csv),
    }


def write_xml(path: Path, root: ET.Element) -> None:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def edge_lane_id(net: Any, edge_id: str) -> str:
    edge = net.getEdge(str(edge_id))
    lanes = edge.getLanes()
    if not lanes:
        raise ValueError(f"SUMO edge has no lanes: {edge_id}")
    return lanes[0].getID()


def shortest_edge_path(net: Any, from_edge_id: str, to_edge_id: str) -> list[str]:
    from_edge = net.getEdge(str(from_edge_id))
    to_edge = net.getEdge(str(to_edge_id))
    path, _cost = net.getShortestPath(from_edge, to_edge, vClass="passenger")
    if not path:
        raise ValueError(f"no SUMO route from {from_edge_id} to {to_edge_id}")
    return [edge.getID() for edge in path]


def append_rescue_vehicle(
    routes: ET.Element,
    net: Any,
    route_cache: dict[tuple[str, str], list[str]],
    vehicle_id: str,
    from_edge_id: str,
    pickup_edge_id: str,
    to_edge_id: str,
    stop_duration_s: int,
) -> None:
    first_leg_key = (str(from_edge_id), str(pickup_edge_id))
    second_leg_key = (str(pickup_edge_id), str(to_edge_id))
    if first_leg_key[0] == first_leg_key[1]:
        first_leg = [str(from_edge_id)]
    else:
        first_leg = route_cache.setdefault(first_leg_key, shortest_edge_path(net, *first_leg_key))
    second_leg = route_cache.setdefault(second_leg_key, shortest_edge_path(net, *second_leg_key))
    route_edges = first_leg + second_leg[1:] if first_leg[-1] == second_leg[0] else first_leg + second_leg

    vehicle = ET.SubElement(
        routes,
        "vehicle",
        {
            "id": vehicle_id,
            "type": "passenger_car",
            "depart": "0",
        },
    )
    ET.SubElement(vehicle, "route", {"edges": " ".join(route_edges)})
    ET.SubElement(
        vehicle,
        "stop",
        {
            "lane": edge_lane_id(net, pickup_edge_id),
            "duration": str(int(stop_duration_s)),
        },
    )


def scenario_paths(ctx: RegionContext, scenario_name: str) -> dict[str, Path]:
    settings = SCENARIO_SETTINGS[scenario_name]
    return {
        "rou": ctx.scenarios_dir / settings["rou"],
        "sumocfg": ctx.scenarios_dir / settings["sumocfg"],
        "assignments": ctx.derived_dir / settings["assignments"],
        "tripinfo": ctx.results_dir / settings["tripinfo"],
        "vehicle_log": ctx.results_dir / settings["vehicle_log"],
        "closure_log": ctx.results_dir / settings["closure_log"],
        "congestion_log": ctx.results_dir / settings["congestion_log"],
        "summary": ctx.results_dir / settings["summary"],
        "fcd": ctx.results_dir / settings["fcd"],
    }


def generate_region_scenario(ctx: RegionContext, scenario_name: str) -> dict[str, Any]:
    ensure_region_dirs(ctx)
    if not ctx.snap_validation_json.exists():
        generate_region_derived(ctx)
    settings = SCENARIO_SETTINGS[scenario_name]
    paths = scenario_paths(ctx, scenario_name)
    net = read_net(ctx)
    origins = pd.read_csv(ctx.agent_origins_sumo_csv, dtype={"KEY_CODE": str})
    rescue_od = (
        pd.read_csv(ctx.rescue_od_csv, dtype={"KEY_CODE": str})
        if scenario_name == "full" and ctx.rescue_od_csv.exists()
        else pd.DataFrame()
    )
    shelters = pd.read_csv(ctx.shelters_sumo_csv)
    safe_shelters = shelters[
        (shelters["is_safe_destination"].astype(str).str.lower() == "true")
        & (shelters["snap_status"].astype(str) != "unmatched")
        & (shelters["sumo_edge_id"].fillna("").astype(str).str.len() > 0)
    ].copy()
    if safe_shelters.empty:
        raise ValueError(f"{ctx.city_code}: no routable safe shelter is available for route generation")

    routes = ET.Element("routes")
    ET.SubElement(
        routes,
        "vType",
        {
            "id": "passenger_car",
            "vClass": "passenger",
            "accel": "2.6",
            "decel": "4.5",
            "sigma": "0.5",
            "length": "5.0",
            "maxSpeed": "13.89",
        },
    )

    assignments: list[dict[str, Any]] = []
    private_source = rescue_od if scenario_name == "full" and not rescue_od.empty else origins
    private_count_column = "private_vehicle_count" if scenario_name == "full" and not rescue_od.empty else settings["count_column"]
    for _, origin in private_source.iterrows():
        if str(origin["snap_status"]) == "unmatched":
            continue
        shelter = (
            pd.Series(
                {
                    "shelter_id": origin["shelter_id"],
                    "name": origin["shelter_name"],
                    "sumo_edge_id": origin["shelter_edge_id"],
                }
            )
            if scenario_name == "full" and not rescue_od.empty
            else nearest_shelter(net, origin, safe_shelters)
        )
        vehicle_count = int(origin[private_count_column])
        from_edge_id = origin.get("sumo_edge_id", origin.get("rescue_start_edge_id", ""))
        for seq in range(vehicle_count):
            vehicle_id = f"{settings['vehicle_prefix']}_{origin['origin_id']}_{seq + 1:04d}"
            ET.SubElement(
                routes,
                "trip",
                {
                    "id": vehicle_id,
                    "type": "passenger_car",
                    "depart": "0",
                    "from": str(from_edge_id),
                    "to": str(shelter["sumo_edge_id"]),
                },
            )
            assignments.append(
                {
                    "vehicle_id": vehicle_id,
                    "vehicle_kind": "private_car",
                    "origin_id": origin["origin_id"],
                    "KEY_CODE": origin["KEY_CODE"],
                    "from_sumo_edge_id": from_edge_id,
                    "pickup_edge_id": "",
                    "shelter_id": shelter["shelter_id"],
                    "shelter_name": shelter["name"],
                    "to_sumo_edge_id": shelter["sumo_edge_id"],
                    "depart": 0,
                    "passenger_equivalent": getattr(config, "HOUSEHOLD_SIZE", HOUSEHOLD_SIZE),
                }
            )

    route_cache: dict[tuple[str, str], list[str]] = {}
    rescue_vehicle_count = 0
    if scenario_name == "full" and not rescue_od.empty:
        for _, row in rescue_od.iterrows():
            vehicle_count = int(row["rescue_vehicle_count"])
            for seq in range(vehicle_count):
                vehicle_id = f"rescue_{row['origin_id']}_{seq + 1:04d}"
                append_rescue_vehicle(
                    routes,
                    net,
                    route_cache,
                    vehicle_id,
                    str(row["rescue_start_edge_id"]),
                    str(row["pickup_edge_id"]),
                    str(row["shelter_edge_id"]),
                    int(row["pickup_stop_duration_s"]),
                )
                assignments.append(
                    {
                        "vehicle_id": vehicle_id,
                        "vehicle_kind": "rescue_car",
                        "origin_id": row["origin_id"],
                        "KEY_CODE": row["KEY_CODE"],
                        "from_sumo_edge_id": row["rescue_start_edge_id"],
                        "pickup_edge_id": row["pickup_edge_id"],
                        "shelter_id": row["shelter_id"],
                        "shelter_name": row["shelter_name"],
                        "to_sumo_edge_id": row["shelter_edge_id"],
                        "depart": 0,
                        "passenger_equivalent": getattr(config, "RESCUE_PER_VEHICLE_K", HOUSEHOLD_SIZE),
                    }
                )
                rescue_vehicle_count += 1

    write_xml(paths["rou"], routes)
    write_csv(
        paths["assignments"],
        [
            "vehicle_id",
            "vehicle_kind",
            "origin_id",
            "KEY_CODE",
            "from_sumo_edge_id",
            "pickup_edge_id",
            "shelter_id",
            "shelter_name",
            "to_sumo_edge_id",
            "depart",
            "passenger_equivalent",
        ],
        assignments,
    )

    config_el = ET.Element("configuration")
    input_el = ET.SubElement(config_el, "input")
    ET.SubElement(input_el, "net-file", {"value": f"../network/{ctx.city_code}.net.xml"})
    ET.SubElement(input_el, "route-files", {"value": paths["rou"].name})
    time_el = ET.SubElement(config_el, "time")
    ET.SubElement(time_el, "begin", {"value": "0"})
    ET.SubElement(time_el, "end", {"value": str(SIM_DURATION_SEC)})
    output_el = ET.SubElement(config_el, "output")
    ET.SubElement(output_el, "tripinfo-output", {"value": f"../results/{paths['tripinfo'].name}"})
    ET.SubElement(output_el, "fcd-output", {"value": f"../results/{paths['fcd'].name}"})
    ET.SubElement(output_el, "device.fcd.period", {"value": settings["fcd_period"]})
    ET.SubElement(output_el, "fcd-output.geo", {"value": "true"})
    processing_el = ET.SubElement(config_el, "processing")
    ET.SubElement(processing_el, "ignore-route-errors", {"value": "false"})
    ET.SubElement(processing_el, "time-to-teleport", {"value": "-1"})
    report_el = ET.SubElement(config_el, "report")
    ET.SubElement(report_el, "no-step-log", {"value": "true"})
    ET.SubElement(report_el, "duration-log.disable", {"value": "true"})
    write_xml(paths["sumocfg"], config_el)

    summary = {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "scenario": scenario_name,
        "vehicle_count": len(assignments),
        "private_vehicle_count": sum(1 for row in assignments if row.get("vehicle_kind") == "private_car"),
        "rescue_vehicle_count": rescue_vehicle_count,
        "rou": rel(paths["rou"]),
        "sumocfg": rel(paths["sumocfg"]),
        "assignments": rel(paths["assignments"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def load_closure_timeline(ctx: RegionContext) -> list[dict[str, Any]]:
    if not ctx.closure_timeline_sumo_json.exists():
        generate_region_derived(ctx)
    data = json.loads(ctx.closure_timeline_sumo_json.read_text(encoding="utf-8"))
    return sorted(data["closures"], key=lambda item: int(item["sim_time_sec"]))


def parse_int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def run_region_traci(ctx: RegionContext, scenario_name: str) -> dict[str, Any]:
    if not scenario_paths(ctx, scenario_name)["sumocfg"].exists():
        generate_region_scenario(ctx, scenario_name)
    settings = SCENARIO_SETTINGS[scenario_name]
    paths = scenario_paths(ctx, scenario_name)
    closures = load_closure_timeline(ctx)
    if any(item["unmapped_phase1_edge_ids"] for item in closures):
        raise ValueError(f"{ctx.city_code}: closure_timeline_sumo.json contains unmapped phase1 edges")

    planned_vehicles = traci_common.load_planned_vehicles(paths["assignments"])
    planned_by_source_edge = traci_common.group_planned_by_source_edge(planned_vehicles)
    archived_outputs = traci_common.archive_existing_outputs(
        {
            "tripinfo": paths["tripinfo"],
            "fcd": paths["fcd"],
            "vehicle_log": paths["vehicle_log"],
            "closure_log": paths["closure_log"],
            "congestion_log": paths["congestion_log"],
            "summary": paths["summary"],
        },
        ctx.results_dir / "archive_runs",
        f"scenario_a_{scenario_name}",
    )
    run_id = f"{scenario_name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
    started_at = datetime.now()

    sumo_binary = sumolib.checkBinary("sumo")
    command = [
        sumo_binary,
        "-c",
        str(paths["sumocfg"]),
        "--no-step-log",
        "true",
        "--duration-log.disable",
        "true",
        "--ignore-route-errors",
        "true",
        "--fcd-output.geo",
        "true",
        "--device.fcd.period",
        settings["fcd_period"],
    ]
    traci.start(command)

    closure_index = 0
    applied_edges: set[str] = set()
    closure_logs: list[dict[str, Any]] = []
    congestion_logs: list[dict[str, Any]] = []
    vehicle_state: dict[str, dict[str, Any]] = {}
    reroute_failed_vehicle_ids: set[str] = set()
    departed_vehicle_ids: set[str] = set()
    blocked_before_depart: dict[str, int] = {}

    try:
        while traci.simulation.getTime() <= SIM_DURATION_SEC and (
            traci.simulation.getMinExpectedNumber() > 0 or closure_index < len(closures)
        ):
            traci.simulationStep()
            sim_time = int(traci.simulation.getTime())

            traci_common.record_departed(sim_time, departed_vehicle_ids, vehicle_state)

            while closure_index < len(closures) and sim_time >= int(closures[closure_index]["sim_time_sec"]):
                item = closures[closure_index]
                new_edges = [edge_id for edge_id in item["closed_sumo_edge_ids"] if edge_id not in applied_edges]
                closure_row, failed_ids = traci_common.apply_closure_to_simulation(
                    item=item,
                    new_edges=new_edges,
                    applied_edges=applied_edges,
                    planned_by_source_edge=planned_by_source_edge,
                    departed_vehicle_ids=departed_vehicle_ids,
                    blocked_before_depart=blocked_before_depart,
                    sim_time=sim_time,
                    disallowed_classes=["passenger"],
                )
                reroute_failed_vehicle_ids.update(failed_ids)
                closure_logs.append(closure_row)
                closure_index += 1

            traci_common.record_arrived(sim_time, vehicle_state)
            traci_common.update_stop_states(
                sim_time,
                vehicle_state,
                STOP_SPEED_THRESHOLD,
                LONG_STOP_THRESHOLD_SEC,
            )

            if sim_time % CONGESTION_LOG_INTERVAL_SEC == 0:
                active_ids = list(traci.vehicle.getIDList())
                speeds = [traci.vehicle.getSpeed(vehicle_id) for vehicle_id in active_ids]
                congestion_logs.append(
                    {
                        "sim_time_sec": sim_time,
                        "active_vehicle_count": len(active_ids),
                        "mean_speed_mps": round(sum(speeds) / len(speeds), 4) if speeds else "",
                        "stopped_vehicle_count": sum(1 for speed in speeds if speed <= STOP_SPEED_THRESHOLD),
                    }
                )
    finally:
        traci.close()

    rows = traci_common.build_vehicle_log_rows(
        planned_vehicles,
        vehicle_state,
        reroute_failed_vehicle_ids,
        blocked_before_depart,
    )
    traci_common.write_vehicle_log(paths["vehicle_log"], rows)
    write_csv(
        paths["closure_log"],
        [
            "time_id",
            "source_timestamp",
            "sim_time_sec",
            "phase1_edge_count",
            "excluded_unmapped_phase1_edge_count",
            "new_sumo_edge_count",
            "closed_sumo_edge_count",
            "cumulative_closed_sumo_edge_count",
            "active_vehicle_count",
            "reroute_success_count",
            "reroute_failed_count",
            "departure_blocked_count",
        ],
        closure_logs,
    )
    write_csv(
        paths["congestion_log"],
        ["sim_time_sec", "active_vehicle_count", "mean_speed_mps", "stopped_vehicle_count"],
        congestion_logs,
    )
    ended_at = datetime.now()
    manifest_paths = {
        "sumocfg": paths["sumocfg"],
        "route_file": paths["rou"],
        "assignments": paths["assignments"],
        "tripinfo": paths["tripinfo"],
        "fcd": paths["fcd"],
        "vehicle_log": paths["vehicle_log"],
        "closure_log": paths["closure_log"],
        "congestion_log": paths["congestion_log"],
    }
    run_manifest = {
        "run_id": run_id,
        "phase": "scenario_a",
        "scenario": scenario_name,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
        "sumocfg": str(paths["sumocfg"]),
        "sumocfg_content": paths["sumocfg"].read_text(encoding="utf-8") if paths["sumocfg"].exists() else "",
        "route_file": str(paths["rou"]),
        "route_sha256": traci_common.sha256_file(paths["rou"]) if paths["rou"].exists() else "",
        "route_vehicle_counts": traci_common.count_route_vehicles(paths["rou"]) if paths["rou"].exists() else {},
        "assignments": str(paths["assignments"]),
        "apply_closures": True,
        "sim_end_sec": SIM_DURATION_SEC,
        "archived_outputs": archived_outputs,
        "outputs": traci_common.file_manifest(manifest_paths),
    }
    run_manifest.update(traci_common.git_state(PROGRAM_DIR))

    summary = traci_common.build_traci_summary(
        city_code=ctx.city_code,
        city_name=ctx.city_name,
        scenario=scenario_name,
        rows=rows,
        closure_logs=closure_logs,
        applied_edges=applied_edges,
        vehicle_log_rel=rel(paths["vehicle_log"]),
        closure_log_rel=rel(paths["closure_log"]),
        congestion_log_rel=rel(paths["congestion_log"]),
        summary_rel=rel(paths["summary"]),
        extra={
            "updated_at": ended_at.isoformat(timespec="seconds"),
            "run_id": run_id,
            "run_manifest": run_manifest,
        },
    )
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_for_csv = dict(summary)
    summary_for_csv.pop("run_manifest", None)
    upsert_summary(RUN_SUMMARY_CSV, ["city_code", "scenario"], summary_for_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def write_full_execution_plan() -> dict[str, Any]:
    targets = load_targets()
    derived_rows = {row["city_code"]: row for row in read_csv_rows(DERIVED_SUMMARY_CSV, "utf-8")} if DERIVED_SUMMARY_CSV.exists() else {}
    run_rows = read_csv_rows(RUN_SUMMARY_CSV, "utf-8") if RUN_SUMMARY_CSV.exists() else []
    run_by_city_scenario = {(row["city_code"], row["scenario"]): row for row in run_rows}

    plan_rows: list[dict[str, Any]] = []
    for target in targets:
        code = target["city_code"]
        derived = derived_rows.get(code, {})
        tenpct = run_by_city_scenario.get((code, "10pct"), {})
        full_vehicle_count_value = int(float(derived.get("vehicle_count_full_total", 0) or 0))
        tenpct_ok = tenpct and str(tenpct.get("not_arrived_count", "0")) != ""
        stranded_10pct = int(float(tenpct.get("stranded_main_count", 0) or 0)) if tenpct else ""
        if not tenpct:
            recommendation = "wait_for_10pct"
            reason = "10pct結果が未生成のためfull実行判断を保留"
        elif full_vehicle_count_value <= 1000:
            recommendation = "run_full"
            reason = "full車両数が1000台以下で実行負荷が比較的小さい"
        elif stranded_10pct not in ("", 0):
            recommendation = "run_full_priority"
            reason = "10pctで逃げ遅れ主指標が発生しており詳細確認を優先"
        else:
            recommendation = "representative_or_defer"
            reason = "10pctで大きな問題が見えず、full車両数が多いため代表地域方式を優先"
        plan_rows.append(
            {
                "city_code": code,
                "city_name": target["city_name"],
                "origin_count": derived.get("origin_count", ""),
                "vehicle_count_10pct_total": derived.get("vehicle_count_10pct_total", ""),
                "vehicle_count_full_total": full_vehicle_count_value if derived else "",
                "tenpct_available": "yes" if tenpct_ok else "no",
                "tenpct_stranded_main_count": stranded_10pct,
                "recommendation": recommendation,
                "reason": reason,
            }
        )

    write_csv(
        FULL_PLAN_CSV,
        [
            "city_code",
            "city_name",
            "origin_count",
            "vehicle_count_10pct_total",
            "vehicle_count_full_total",
            "tenpct_available",
            "tenpct_stranded_main_count",
            "recommendation",
            "reason",
        ],
        plan_rows,
    )

    counts = defaultdict(int)
    for row in plan_rows:
        counts[row["recommendation"]] += 1
    lines = [
        "# Phase 2 全域拡張 full試行 実行計画",
        "",
        f"- 生成日時: {datetime.now().isoformat(timespec='seconds')}",
        "- 判断方針: small / 10pct は全41市区町村で実行し、fullは10pct結果と車両数を見て実行範囲を決める。",
        "- 現時点の推奨: 10pct結果がない市区町村は保留、10pctで逃げ遅れが出た地域またはfull車両数1000台以下の地域を優先する。",
        "",
        "## 推奨区分集計",
        "",
        "| 推奨区分 | 件数 |",
        "|---|---:|",
    ]
    for key in sorted(counts):
        lines.append(f"| {key} | {counts[key]} |")
    lines.extend(["", "## 市区町村別計画", "", "| コード | 市区町村 | full車両数 | 10pct有無 | 10pct逃げ遅れ | 推奨 | 理由 |", "|---|---|---:|---|---:|---|---|"])
    for row in plan_rows:
        lines.append(
            "| {city_code} | {city_name} | {vehicle_count_full_total} | {tenpct_available} | "
            "{tenpct_stranded_main_count} | {recommendation} | {reason} |".format(**row)
        )
    FULL_PLAN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "plan_csv": rel(FULL_PLAN_CSV),
        "plan_md": rel(FULL_PLAN_MD),
        "recommendation_counts": dict(counts),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def row_map(path: Path, key: str = "city_code") -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row[key]: row for row in read_csv_rows(path, "utf-8")}


def run_row_map() -> dict[tuple[str, str], dict[str, str]]:
    if not RUN_SUMMARY_CSV.exists():
        return {}
    return {(row["city_code"], row["scenario"]): row for row in read_csv_rows(RUN_SUMMARY_CSV, "utf-8")}


def value(row: dict[str, Any], key: str, default: Any = "") -> Any:
    item = row.get(key, default)
    if item is None:
        return default
    if isinstance(item, str) and item.strip() == "":
        return default
    return item


def write_region_evaluation() -> dict[str, Any]:
    targets = load_targets()
    derived_rows = row_map(DERIVED_SUMMARY_CSV)
    mapping_rows = row_map(EDGE_MAPPING_SUMMARY_CSV)
    plan_rows = row_map(FULL_PLAN_CSV)
    runs = run_row_map()

    summary_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    for target in targets:
        code = target["city_code"]
        name = target["city_name"]
        derived = derived_rows.get(code, {})
        mapping = mapping_rows.get(code, {})
        plan = plan_rows.get(code, {})
        small = runs.get((code, "small"), {})
        tenpct = runs.get((code, "10pct"), {})
        full = runs.get((code, "full"), {})

        note_parts: list[str] = []
        if parse_int(derived.get("origin_unmatched_count", 0)) > 0:
            note_parts.append(f"origin_unmatched_excluded={derived.get('origin_unmatched_count')}")
        if parse_int(derived.get("safe_shelter_unmatched_count", 0)) > 0:
            note_parts.append(f"safe_shelter_unmatched_excluded={derived.get('safe_shelter_unmatched_count')}")
        if parse_int(mapping.get("excluded_unmapped_count", 0)) > 0:
            note_parts.append(f"closure_edge_excluded={mapping.get('excluded_unmapped_count')}")
        if plan and not full and plan.get("recommendation") != "run_full":
            note_parts.append("full_deferred_by_plan")

        summary_rows.append(
            {
                "city_code": code,
                "city_name": name,
                "origin_count": value(derived, "origin_count"),
                "origin_routable_count": value(derived, "origin_routable_count", value(derived, "origin_count")),
                "origin_unmatched_count": value(derived, "origin_unmatched_count"),
                "safe_shelter_count": value(derived, "safe_shelter_count"),
                "safe_shelter_routable_count": value(
                    derived,
                    "safe_shelter_routable_count",
                    value(derived, "safe_shelter_count"),
                ),
                "safe_shelter_unmatched_count": value(derived, "safe_shelter_unmatched_count"),
                "phase1_closed_edge_count": value(mapping, "phase1_closed_edge_count"),
                "mapping_matched_count": value(mapping, "matched_count"),
                "mapping_excluded_unmapped_count": value(mapping, "excluded_unmapped_count", 0),
                "small_vehicle_count": value(small, "vehicle_count"),
                "small_arrived_count": value(small, "arrived_count"),
                "small_not_arrived_count": value(small, "not_arrived_count"),
                "small_stranded_main_count": value(small, "stranded_main_count"),
                "tenpct_vehicle_count": value(tenpct, "vehicle_count"),
                "tenpct_arrived_count": value(tenpct, "arrived_count"),
                "tenpct_not_arrived_count": value(tenpct, "not_arrived_count"),
                "tenpct_stranded_main_count": value(tenpct, "stranded_main_count"),
                "full_recommendation": value(plan, "recommendation"),
                "full_vehicle_count_total": value(plan, "vehicle_count_full_total", value(derived, "vehicle_count_full_total")),
                "full_vehicle_count_run": value(full, "vehicle_count"),
                "full_arrived_count": value(full, "arrived_count"),
                "full_not_arrived_count": value(full, "not_arrived_count"),
                "full_stranded_main_count": value(full, "stranded_main_count"),
                "notes": ";".join(note_parts),
            }
        )

        base = {
            "city_code": code,
            "city_name": name,
            "phase1_closed_edge_count": value(mapping, "phase1_closed_edge_count"),
            "origin_count": value(derived, "origin_count"),
            "origin_routable_count": value(derived, "origin_routable_count", value(derived, "origin_count")),
            "full_recommendation": value(plan, "recommendation"),
        }
        comparison_rows.append(
            {
                **base,
                "analysis_type": "phase1_static_city_scenario",
                "scenario_name": "city_scenario_t0_to_t7",
                "unit": "closed_edges_and_origin_meshes",
                "vehicle_count": "",
                "arrived_count": "",
                "not_arrived_vehicle_count": "",
                "stranded_main_vehicle_count": "",
                "note": "Phase 1 city scenario input scale; not a dynamic vehicle simulation.",
            }
        )
        for scenario, row in [("small", small), ("10pct", tenpct), ("full", full)]:
            if not row:
                if scenario == "full":
                    comparison_rows.append(
                        {
                            **base,
                            "analysis_type": "phase2_full_plan",
                            "scenario_name": "full",
                            "unit": "vehicle_plan",
                            "vehicle_count": value(plan, "vehicle_count_full_total", value(derived, "vehicle_count_full_total")),
                            "arrived_count": "",
                            "not_arrived_vehicle_count": "",
                            "stranded_main_vehicle_count": "",
                            "note": f"Full run deferred by plan: {value(plan, 'reason')}",
                        }
                    )
                continue
            comparison_rows.append(
                {
                    **base,
                    "analysis_type": "phase2_dynamic_sumo",
                    "scenario_name": scenario,
                    "unit": "vehicle",
                    "vehicle_count": value(row, "vehicle_count"),
                    "arrived_count": value(row, "arrived_count"),
                    "not_arrived_vehicle_count": value(row, "not_arrived_count"),
                    "stranded_main_vehicle_count": value(row, "stranded_main_count"),
                    "note": "Dynamic SUMO/TraCI result; teleport warnings are retained as SUMO runtime notes and summary metrics are counted after simulation.",
                }
            )

    summary_fields = [
        "city_code",
        "city_name",
        "origin_count",
        "origin_routable_count",
        "origin_unmatched_count",
        "safe_shelter_count",
        "safe_shelter_routable_count",
        "safe_shelter_unmatched_count",
        "phase1_closed_edge_count",
        "mapping_matched_count",
        "mapping_excluded_unmapped_count",
        "small_vehicle_count",
        "small_arrived_count",
        "small_not_arrived_count",
        "small_stranded_main_count",
        "tenpct_vehicle_count",
        "tenpct_arrived_count",
        "tenpct_not_arrived_count",
        "tenpct_stranded_main_count",
        "full_recommendation",
        "full_vehicle_count_total",
        "full_vehicle_count_run",
        "full_arrived_count",
        "full_not_arrived_count",
        "full_stranded_main_count",
        "notes",
    ]
    comparison_fields = [
        "city_code",
        "city_name",
        "analysis_type",
        "scenario_name",
        "unit",
        "phase1_closed_edge_count",
        "origin_count",
        "origin_routable_count",
        "vehicle_count",
        "arrived_count",
        "not_arrived_vehicle_count",
        "stranded_main_vehicle_count",
        "full_recommendation",
        "note",
    ]
    write_csv(REGION_EVALUATION_CSV, summary_fields, summary_rows)
    write_csv(REGION_COMPARISON_CSV, comparison_fields, comparison_rows)

    counts = {
        "municipality_count": len(summary_rows),
        "small_completed": sum(1 for row in summary_rows if str(row["small_vehicle_count"]) != ""),
        "tenpct_completed": sum(1 for row in summary_rows if str(row["tenpct_vehicle_count"]) != ""),
        "full_completed": sum(1 for row in summary_rows if str(row["full_vehicle_count_run"]) != ""),
        "tenpct_stranded_total": sum(parse_int(row["tenpct_stranded_main_count"]) for row in summary_rows),
        "full_stranded_total": sum(parse_int(row["full_stranded_main_count"]) for row in summary_rows),
    }
    result = {
        **counts,
        "evaluation_csv": rel(REGION_EVALUATION_CSV),
        "comparison_csv": rel(REGION_COMPARISON_CSV),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def write_region_index_html() -> dict[str, Any]:
    if not REGION_EVALUATION_CSV.exists() or not REGION_COMPARISON_CSV.exists():
        write_region_evaluation()
    rows = read_csv_rows(REGION_EVALUATION_CSV, "utf-8")
    small_completed = sum(1 for row in rows if row.get("small_vehicle_count"))
    tenpct_completed = sum(1 for row in rows if row.get("tenpct_vehicle_count"))
    full_completed = sum(1 for row in rows if row.get("full_vehicle_count_run"))
    tenpct_stranded = sum(parse_int(row.get("tenpct_stranded_main_count")) for row in rows)
    full_stranded = sum(parse_int(row.get("full_stranded_main_count")) for row in rows)

    def link_or_dash(city_code: str, scenario: str, label: str) -> str:
        file_name = SCENARIO_SETTINGS[scenario]["summary"]
        path = REGIONS_DIR / city_code / "results" / file_name
        if not path.exists():
            return "-"
        return f'<a href="{escape(city_code)}/results/{escape(file_name)}">{escape(label)}</a>'

    table_rows = []
    for row in rows:
        full_display = (
            f"{escape(str(row['full_arrived_count']))}/{escape(str(row['full_vehicle_count_run']))}"
            if row["full_vehicle_count_run"]
            else "-"
        )
        table_rows.append(
            "<tr>"
            f"<td>{escape(row['city_code'])}</td>"
            f"<td>{escape(row['city_name'])}</td>"
            f"<td>{escape(str(row['origin_routable_count']))}/{escape(str(row['origin_count']))}</td>"
            f"<td>{escape(str(row['phase1_closed_edge_count']))}</td>"
            f"<td>{escape(str(row['small_arrived_count']))}/{escape(str(row['small_vehicle_count']))}</td>"
            f"<td>{escape(str(row['tenpct_arrived_count']))}/{escape(str(row['tenpct_vehicle_count']))}</td>"
            f"<td>{escape(str(row['tenpct_stranded_main_count']))}</td>"
            f"<td>{escape(str(row['full_recommendation']))}</td>"
            f"<td>{full_display}</td>"
            f"<td>{link_or_dash(row['city_code'], 'small', 'small')} / {link_or_dash(row['city_code'], '10pct', '10pct')} / {link_or_dash(row['city_code'], 'full', 'full')}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 2 全域SUMO結果</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933;
      --muted: #52616f;
      --line: #d8dee6;
      --panel: #f6f8fa;
      --accent: #0f766e;
      --accent-2: #7c2d12;
      font-family: "Segoe UI", "Yu Gothic", Meiryo, sans-serif;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.55;
    }}
    header {{
      padding: 32px clamp(18px, 4vw, 48px) 22px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8fbfb 0%, #fff 100%);
    }}
    main {{
      padding: 24px clamp(18px, 4vw, 48px) 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    p {{
      margin: 0;
      color: var(--muted);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin: 22px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
      background: var(--panel);
    }}
    .metric strong {{
      display: block;
      font-size: 24px;
      color: var(--accent);
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 18px 0 26px;
    }}
    a {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
    }}
    .links a {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      background: #fff;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      background: #edf3f2;
      color: #24413f;
      position: sticky;
      top: 0;
    }}
    tr:nth-child(even) td {{
      background: #fafafa;
    }}
    .note {{
      margin-top: 18px;
      max-width: 980px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>Phase 2 全域SUMO結果</h1>
    <p>Phase 1対象41市区町村に対する、市区町村別SUMO/TraCI試行の集計です。</p>
  </header>
  <main>
    <section class="metrics" aria-label="集計">
      <div class="metric"><strong>{len(rows)}</strong><span>対象市区町村</span></div>
      <div class="metric"><strong>{small_completed}</strong><span>small完了</span></div>
      <div class="metric"><strong>{tenpct_completed}</strong><span>10pct完了</span></div>
      <div class="metric"><strong>{full_completed}</strong><span>full実行</span></div>
      <div class="metric"><strong>{tenpct_stranded}</strong><span>10pct逃げ遅れ主指標</span></div>
      <div class="metric"><strong>{full_stranded}</strong><span>full逃げ遅れ主指標</span></div>
    </section>
    <nav class="links" aria-label="成果物">
      <a href="../evaluation/evacuation_summary_by_municipality.csv">市区町村別サマリCSV</a>
      <a href="../evaluation/phase1_phase2_region_comparison.csv">Phase 1/2全域比較CSV</a>
      <a href="_management/region_batch_status.md">バッチ状態</a>
      <a href="_management/region_full_execution_plan.md">full実行計画</a>
    </nav>
    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>コード</th>
            <th>市区町村</th>
            <th>経路化出発地/全出発地</th>
            <th>Phase 1閉鎖edge</th>
            <th>small到着/車両</th>
            <th>10pct到着/車両</th>
            <th>10pct逃げ遅れ</th>
            <th>full方針</th>
            <th>full到着/車両</th>
            <th>summary</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </section>
    <p class="note">Phase 1は静的な閉鎖道路・経路探索の入力規模、Phase 2はSUMO/TraCIによる動的車両試行です。単位が異なるため、比較CSVでは列を分けています。</p>
  </main>
</body>
</html>
"""
    REGION_INDEX_HTML.parent.mkdir(parents=True, exist_ok=True)
    REGION_INDEX_HTML.write_text(html, encoding="utf-8")
    result = {
        "region_index_html": rel(REGION_INDEX_HTML),
        "municipality_count": len(rows),
        "small_completed": small_completed,
        "tenpct_completed": tenpct_completed,
        "full_completed": full_completed,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"json_error": "decode_error"}


def scenario_summary(ctx: RegionContext, scenario_name: str) -> dict[str, Any]:
    return read_json_if_exists(scenario_paths(ctx, scenario_name)["summary"])


def region_status_row(ctx: RegionContext) -> dict[str, Any]:
    mapping = read_json_if_exists(ctx.edge_mapping_validation_json)
    derived = read_json_if_exists(ctx.derived_validation_json)
    small = scenario_summary(ctx, "small")
    tenpct = scenario_summary(ctx, "10pct")

    network_ready = ctx.net_xml.exists() and ctx.osm_way_mapping_csv.exists()
    mapping_exists = bool(mapping)
    mapping_unmatched_count = int(mapping.get("unmatched_count", 0) or 0) if mapping_exists else 0
    mapping_excluded_unmapped_count = (
        int(mapping.get("excluded_unmapped_count", 0) or 0) if mapping_exists else 0
    )
    mapping_ready = mapping_exists and bool(mapping.get("can_proceed_to_region_closure", False))
    derived_ready = bool(derived) and bool(derived.get("can_proceed_to_small", False))
    small_ready = bool(small) and str(small.get("vehicle_count", "")) != ""
    tenpct_ready = bool(tenpct) and str(tenpct.get("vehicle_count", "")) != ""

    if not network_ready or not mapping_exists:
        next_action = "mapping"
    elif mapping_unmatched_count > 0 or not mapping_ready:
        next_action = "inspect_mapping"
    elif not derived_ready:
        next_action = "derived"
    elif int(derived.get("origin_count", 0) or 0) == 0:
        next_action = "inspect_no_origin"
    elif int(derived.get("safe_shelter_count", 0) or 0) == 0:
        next_action = "inspect_no_safe_shelter"
    elif not small_ready:
        next_action = "run_small"
    elif not tenpct_ready:
        next_action = "run_10pct"
    else:
        next_action = "full_plan_or_eval"

    return {
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "network_ready": "yes" if network_ready else "no",
        "mapping_ready": "yes" if mapping_ready else "no",
        "mapping_count": mapping.get("mapping_count", ""),
        "mapping_unmatched_count": mapping.get("unmatched_count", ""),
        "mapping_excluded_unmapped_count": mapping_excluded_unmapped_count if mapping_exists else "",
        "derived_ready": "yes" if derived_ready else "no",
        "origin_count": derived.get("origin_count", ""),
        "safe_shelter_count": derived.get("safe_shelter_count", ""),
        "vehicle_count_small_total": derived.get("vehicle_count_small_total", ""),
        "vehicle_count_10pct_total": derived.get("vehicle_count_10pct_total", ""),
        "vehicle_count_full_total": derived.get("vehicle_count_full_total", ""),
        "origin_unmatched_count": derived.get("origin_unmatched_count", ""),
        "safe_shelter_unmatched_count": derived.get("safe_shelter_unmatched_count", ""),
        "small_ready": "yes" if small_ready else "no",
        "small_vehicle_count": small.get("vehicle_count", ""),
        "small_arrived_count": small.get("arrived_count", ""),
        "small_stranded_main_count": small.get("stranded_main_count", ""),
        "tenpct_ready": "yes" if tenpct_ready else "no",
        "tenpct_vehicle_count": tenpct.get("vehicle_count", ""),
        "tenpct_arrived_count": tenpct.get("arrived_count", ""),
        "tenpct_stranded_main_count": tenpct.get("stranded_main_count", ""),
        "next_action": next_action,
    }


def write_batch_status() -> dict[str, Any]:
    rows = [region_status_row(context_for(row["city_code"])) for row in load_targets()]
    fieldnames = [
        "city_code",
        "city_name",
        "network_ready",
        "mapping_ready",
        "mapping_count",
        "mapping_unmatched_count",
        "mapping_excluded_unmapped_count",
        "derived_ready",
        "origin_count",
        "safe_shelter_count",
        "vehicle_count_small_total",
        "vehicle_count_10pct_total",
        "vehicle_count_full_total",
        "origin_unmatched_count",
        "safe_shelter_unmatched_count",
        "small_ready",
        "small_vehicle_count",
        "small_arrived_count",
        "small_stranded_main_count",
        "tenpct_ready",
        "tenpct_vehicle_count",
        "tenpct_arrived_count",
        "tenpct_stranded_main_count",
        "next_action",
    ]
    write_csv(BATCH_STATUS_CSV, fieldnames, rows)

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["next_action"]] += 1

    lines = [
        "# Phase 2 全域拡張 バッチ状態",
        "",
        f"- 生成日時: {datetime.now().isoformat(timespec='seconds')}",
        f"- 対象市区町村: {len(rows)} 件",
        "",
        "## 次アクション集計",
        "",
        "| 次アクション | 件数 |",
        "|---|---:|",
    ]
    for key in sorted(counts):
        lines.append(f"| {key} | {counts[key]} |")
    lines.extend(
        [
            "",
            "## 市区町村別状態",
            "",
            "| コード | 市区町村 | mapping | derived | small | 10pct | 次アクション |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['city_code']} | {row['city_name']} | {row['mapping_ready']} | "
            f"{row['derived_ready']} | {row['small_ready']} | {row['tenpct_ready']} | {row['next_action']} |"
        )
    BATCH_STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "status_csv": rel(BATCH_STATUS_CSV),
        "status_md": rel(BATCH_STATUS_MD),
        "next_action_counts": dict(sorted(counts.items())),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def is_step_complete(ctx: RegionContext, command: str, scenario: str | None = None) -> bool:
    status = region_status_row(ctx)
    if command == "mapping":
        return bool(read_json_if_exists(ctx.edge_mapping_validation_json))
    if command == "derived":
        return status["derived_ready"] == "yes"
    if command == "scenario":
        if scenario is None:
            return False
        paths = scenario_paths(ctx, scenario)
        return paths["rou"].exists() and paths["sumocfg"].exists() and paths["assignments"].exists()
    if command == "run":
        if scenario == "small":
            return status["small_ready"] == "yes"
        if scenario == "10pct":
            return status["tenpct_ready"] == "yes"
        if scenario == "full":
            return bool(scenario_summary(ctx, "full"))
    return False


def append_batch_failure(command: str, ctx: RegionContext, error: Exception, scenario: str | None = None) -> None:
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "scenario": scenario or "",
        "city_code": ctx.city_code,
        "city_name": ctx.city_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    rows: list[dict[str, Any]] = []
    if BATCH_FAILURES_CSV.exists():
        rows = read_csv_rows(BATCH_FAILURES_CSV, encoding="utf-8")
    rows.append(row)
    write_csv(
        BATCH_FAILURES_CSV,
        ["timestamp", "command", "scenario", "city_code", "city_name", "error_type", "error_message"],
        rows,
    )


def select_target_rows(codes: list[str] | None = None, limit: int | None = None) -> list[dict[str, str]]:
    rows = load_targets()
    if codes:
        code_set = set(codes)
        rows = [row for row in rows if row["city_code"] in code_set]
    if limit is not None:
        rows = rows[:limit]
    return rows


def run_for_targets(
    command: str,
    scenario: str | None = None,
    limit: int | None = None,
    max_process: int | None = None,
    codes: list[str] | None = None,
    skip_completed: bool = False,
    continue_on_error: bool = False,
) -> None:
    processed = 0
    skipped = 0
    failed = 0
    for row in select_target_rows(codes=codes, limit=limit):
        ctx = context_for(row["city_code"])
        if skip_completed and is_step_complete(ctx, command, scenario):
            skipped += 1
            print(f"[SKIP] {command}: {ctx.city_code} {ctx.city_name}")
            continue
        if max_process is not None and processed >= max_process:
            print(f"[INFO] max_process reached: {max_process}")
            break
        print(f"[INFO] {command}: {ctx.city_code} {ctx.city_name}")
        try:
            if command == "mapping":
                generate_edge_mapping(ctx)
            elif command == "derived":
                generate_region_derived(ctx)
            elif command == "scenario":
                if scenario is None:
                    raise ValueError("scenario is required")
                generate_region_scenario(ctx, scenario)
            elif command == "run":
                if scenario is None:
                    raise ValueError("scenario is required")
                run_region_traci(ctx, scenario)
            else:
                raise ValueError(command)
            processed += 1
        except Exception as error:
            failed += 1
            append_batch_failure(command, ctx, error, scenario)
            print(f"[ERROR] {ctx.city_code} {ctx.city_name}: {type(error).__name__}: {error}")
            if not continue_on_error:
                raise
    print(f"[INFO] batch finished: processed={processed}, skipped={skipped}, failed={failed}")
    write_batch_status()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "status",
            "mapping-city",
            "inspect-mapping-city",
            "resolve-unmatched-city",
            "derived-city",
            "scenario-city",
            "run-city",
            "full-plan",
            "region-eval",
            "region-html",
            "region-finalize",
            "all-five-city",
            "mapping-targets",
            "derived-targets",
            "scenario-targets",
            "run-targets",
        ],
    )
    parser.add_argument("--city-code", help="対象市区町村コード")
    parser.add_argument("--scenario", choices=["small", "10pct", "full"], default="small")
    parser.add_argument("--limit", type=int, help="targets系コマンドの先頭N件だけ処理する")
    parser.add_argument("--max-process", type=int, help="targets系コマンドで未完了を最大N件だけ処理する")
    parser.add_argument("--codes", nargs="+", help="targets系コマンドで処理する市区町村コードを限定する")
    parser.add_argument("--skip-completed", action="store_true", help="targets系コマンドで完了済み市区町村をスキップする")
    parser.add_argument("--continue-on-error", action="store_true", help="targets系コマンドで失敗を記録し、次の市区町村へ進む")
    parser.add_argument("--force-network", action="store_true", help="地域別OSM/net.xmlを再生成する")
    parser.add_argument("--policy", choices=["exclude"], default="exclude", help="未対応edgeの解決方針")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command.endswith("-city") and not args.city_code:
        raise ValueError("--city-code is required")

    if args.command == "status":
        write_batch_status()
    elif args.command == "mapping-city":
        generate_edge_mapping(context_for(args.city_code), force_network=args.force_network)
    elif args.command == "inspect-mapping-city":
        inspect_unmatched_edge_mapping(context_for(args.city_code))
    elif args.command == "resolve-unmatched-city":
        apply_unmatched_policy(context_for(args.city_code), args.policy)
        write_batch_status()
    elif args.command == "derived-city":
        generate_region_derived(context_for(args.city_code))
    elif args.command == "scenario-city":
        generate_region_scenario(context_for(args.city_code), args.scenario)
    elif args.command == "run-city":
        run_region_traci(context_for(args.city_code), args.scenario)
    elif args.command == "full-plan":
        write_full_execution_plan()
    elif args.command == "region-eval":
        write_region_evaluation()
    elif args.command == "region-html":
        write_region_index_html()
    elif args.command == "region-finalize":
        write_full_execution_plan()
        write_region_evaluation()
        write_region_index_html()
        write_batch_status()
    elif args.command == "all-five-city":
        ctx = context_for(args.city_code)
        generate_edge_mapping(ctx, force_network=args.force_network)
        generate_region_derived(ctx)
        generate_region_scenario(ctx, "small")
        run_region_traci(ctx, "small")
        generate_region_scenario(ctx, "10pct")
        run_region_traci(ctx, "10pct")
        write_full_execution_plan()
    elif args.command == "mapping-targets":
        run_for_targets(
            "mapping",
            limit=args.limit,
            max_process=args.max_process,
            codes=args.codes,
            skip_completed=args.skip_completed,
            continue_on_error=args.continue_on_error,
        )
    elif args.command == "derived-targets":
        run_for_targets(
            "derived",
            limit=args.limit,
            max_process=args.max_process,
            codes=args.codes,
            skip_completed=args.skip_completed,
            continue_on_error=args.continue_on_error,
        )
    elif args.command == "scenario-targets":
        run_for_targets(
            "scenario",
            scenario=args.scenario,
            limit=args.limit,
            max_process=args.max_process,
            codes=args.codes,
            skip_completed=args.skip_completed,
            continue_on_error=args.continue_on_error,
        )
    elif args.command == "run-targets":
        run_for_targets(
            "run",
            scenario=args.scenario,
            limit=args.limit,
            max_process=args.max_process,
            codes=args.codes,
            skip_completed=args.skip_completed,
            continue_on_error=args.continue_on_error,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
