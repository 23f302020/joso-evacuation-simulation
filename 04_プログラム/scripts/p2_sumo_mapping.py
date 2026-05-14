"""Phase 2: Phase 1 edge ID と SUMO edge ID の対応表生成。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_NETWORK_DIR = PROGRAM_DIR / "output" / "sumo" / "network"
SUMO_DERIVED_DIR = PROGRAM_DIR / "output" / "sumo" / "derived"
CLOSURE_JSON_PATH = PROGRAM_DIR / "output" / "closure" / "road_closure_timeline.json"

NET_XML_PATH = SUMO_NETWORK_DIR / "joso.net.xml"
OSM_WAY_MAPPING_CSV = SUMO_DERIVED_DIR / "phase1_edge_osm_way_mapping.csv"
SUMO_EDGES_CSV = SUMO_DERIVED_DIR / "sumo_edges.csv"
PHASE1_CLOSED_EDGES_CSV = SUMO_DERIVED_DIR / "phase1_closed_edges.csv"
EDGE_ID_MAPPING_CSV = SUMO_DERIVED_DIR / "edge_id_mapping.csv"
EDGE_MAPPING_VALIDATION_JSON = SUMO_DERIVED_DIR / "edge_mapping_validation.json"


def ensure_dirs() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def base_sumo_edge_id(edge_id: str) -> str:
    return edge_id.split("#", 1)[0]


def read_csv_dict(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_dict(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def lane_lengths(edge: ET.Element) -> list[float]:
    values: list[float] = []
    for lane in edge.findall("lane"):
        length = lane.get("length")
        if length:
            values.append(float(length))
    return values


def extract_sumo_edges() -> None:
    ensure_dirs()
    root = ET.parse(NET_XML_PATH).getroot()
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

    write_csv_dict(
        SUMO_EDGES_CSV,
        ["sumo_edge_id", "base_sumo_edge_id", "from", "to", "priority", "lane_count", "length_m"],
        rows,
    )
    print(f"[INFO] saved: {SUMO_EDGES_CSV} ({len(rows)} edges)")


def extract_phase1_closed_edges() -> None:
    ensure_dirs()
    closure = json.loads(CLOSURE_JSON_PATH.read_text(encoding="utf-8"))
    edge_times: dict[str, set[str]] = defaultdict(set)
    for timestamp, edge_ids in closure.items():
        for edge_id in edge_ids:
            edge_times[edge_id].add(timestamp)

    rows: list[dict[str, Any]] = []
    for edge_id in sorted(edge_times):
        timestamps = sorted(edge_times[edge_id])
        rows.append(
            {
                "phase1_edge_id": edge_id,
                "closed_time_count": len(timestamps),
                "first_timestamp": timestamps[0],
                "timestamps": ";".join(timestamps),
            }
        )

    write_csv_dict(
        PHASE1_CLOSED_EDGES_CSV,
        ["phase1_edge_id", "closed_time_count", "first_timestamp", "timestamps"],
        rows,
    )
    print(f"[INFO] saved: {PHASE1_CLOSED_EDGES_CSV} ({len(rows)} unique closed edges)")


def parse_phase1_edge_id(edge_id: str) -> tuple[str, str, str]:
    match = re.match(r"^(.+)_(.+)_([^_]+)$", edge_id)
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3)


def build_edge_mapping() -> None:
    ensure_dirs()
    if not SUMO_EDGES_CSV.exists():
        extract_sumo_edges()
    if not PHASE1_CLOSED_EDGES_CSV.exists():
        extract_phase1_closed_edges()

    sumo_edges = read_csv_dict(SUMO_EDGES_CSV)
    sumo_by_base: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sumo_edges:
        sumo_by_base[row["base_sumo_edge_id"]].append(row)

    way_rows = read_csv_dict(OSM_WAY_MAPPING_CSV)
    way_by_phase1 = {row["phase1_edge_id"]: row for row in way_rows}
    closed_rows = read_csv_dict(PHASE1_CLOSED_EDGES_CSV)

    mapping_rows: list[dict[str, Any]] = []
    for closed in closed_rows:
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
                "first_timestamp": closed["first_timestamp"],
                "notes": "" if status == "matched" else "SUMO edge with matching base ID was not found",
            }
        )

    write_csv_dict(
        EDGE_ID_MAPPING_CSV,
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
            "first_timestamp",
            "notes",
        ],
        mapping_rows,
    )
    print(f"[INFO] saved: {EDGE_ID_MAPPING_CSV} ({len(mapping_rows)} mappings)")


def validate_edge_mapping() -> None:
    if not EDGE_ID_MAPPING_CSV.exists():
        build_edge_mapping()
    rows = read_csv_dict(EDGE_ID_MAPPING_CSV)
    status_counts: dict[str, int] = defaultdict(int)
    total_sumo_edges = 0
    for row in rows:
        status_counts[row["mapping_status"]] += 1
        total_sumo_edges += int(row["sumo_edge_count"] or 0)

    summary = {
        "mapping_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "total_mapped_sumo_edge_segments": total_sumo_edges,
        "can_proceed_to_traci_closure": status_counts.get("unmatched", 0) == 0,
    }
    EDGE_MAPPING_VALIDATION_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[INFO] saved: {EDGE_MAPPING_VALIDATION_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["sumo-edges", "closed-edges", "mapping", "validate", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "sumo-edges":
        extract_sumo_edges()
    elif args.command == "closed-edges":
        extract_phase1_closed_edges()
    elif args.command == "mapping":
        build_edge_mapping()
    elif args.command == "validate":
        validate_edge_mapping()
    elif args.command == "all":
        extract_sumo_edges()
        extract_phase1_closed_edges()
        build_edge_mapping()
        validate_edge_mapping()


if __name__ == "__main__":
    main()
