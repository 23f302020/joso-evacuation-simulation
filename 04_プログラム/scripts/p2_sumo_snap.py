"""Phase 2: 出発地・避難所をSUMO edgeへスナップする。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from p2_sumo_env import configure_sumo_environment

configure_sumo_environment(require_tools=True)
import sumolib  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_NETWORK_DIR = PROGRAM_DIR / "output" / "sumo" / "network"
SUMO_DERIVED_DIR = PROGRAM_DIR / "output" / "sumo" / "derived"

NET_XML_PATH = SUMO_NETWORK_DIR / "joso.net.xml"
AGENT_ORIGINS_10PCT_CSV = SUMO_DERIVED_DIR / "agent_origins_10pct.csv"
SHELTERS_SAFETY_CSV = SUMO_DERIVED_DIR / "shelters_safety.csv"
AGENT_ORIGINS_SUMO_CSV = SUMO_DERIVED_DIR / "agent_origins_sumo.csv"
SHELTERS_SUMO_CSV = SUMO_DERIVED_DIR / "shelters_sumo.csv"
SNAP_VALIDATION_JSON = SUMO_DERIVED_DIR / "snap_validation.json"

SEARCH_RADII_M = [100, 250, 500, 1000, 3000, 5000]
FAR_THRESHOLD_M = 500.0


def read_net():
    return sumolib.net.readNet(str(NET_XML_PATH))


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


def snap_agent_origins() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    net = read_net()
    origins = pd.read_csv(AGENT_ORIGINS_10PCT_CSV, dtype={"KEY_CODE": str})
    rows = []
    for _, row in origins.iterrows():
        edge_id, distance, status = nearest_edge(net, float(row["lon"]), float(row["lat"]))
        rows.append(
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

    pd.DataFrame(rows).to_csv(AGENT_ORIGINS_SUMO_CSV, index=False, encoding="utf-8")
    print(f"[INFO] saved: {AGENT_ORIGINS_SUMO_CSV} ({len(rows)} origins)")


def snap_shelters() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    net = read_net()
    shelters = pd.read_csv(SHELTERS_SAFETY_CSV)
    rows = []
    for _, row in shelters.iterrows():
        is_safe = bool(row["is_safe_destination"])
        if is_safe:
            edge_id, distance, status = nearest_edge(net, float(row["lon"]), float(row["lat"]))
        else:
            edge_id, distance, status = "", float("nan"), "excluded_flood_risk"
        rows.append(
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

    pd.DataFrame(rows).to_csv(SHELTERS_SUMO_CSV, index=False, encoding="utf-8")
    print(f"[INFO] saved: {SHELTERS_SUMO_CSV} ({len(rows)} shelters)")


def status_counts(df: pd.DataFrame) -> dict[str, int]:
    return {str(k): int(v) for k, v in df["snap_status"].value_counts().sort_index().items()}


def validate_snap() -> None:
    if not AGENT_ORIGINS_SUMO_CSV.exists():
        snap_agent_origins()
    if not SHELTERS_SUMO_CSV.exists():
        snap_shelters()
    origins = pd.read_csv(AGENT_ORIGINS_SUMO_CSV)
    shelters = pd.read_csv(SHELTERS_SUMO_CSV)
    safe_shelters = shelters[shelters["is_safe_destination"] == True]  # noqa: E712

    summary = {
        "origin_count": int(len(origins)),
        "origin_status_counts": status_counts(origins),
        "origin_max_snap_distance_m": float(origins["snap_distance_m"].max()),
        "shelter_count": int(len(shelters)),
        "safe_shelter_count": int(len(safe_shelters)),
        "shelter_status_counts": status_counts(shelters),
        "safe_shelter_max_snap_distance_m": float(safe_shelters["snap_distance_m"].max())
        if len(safe_shelters)
        else None,
        "can_proceed_to_route_generation": bool(
            int((origins["snap_status"] == "unmatched").sum()) == 0
            and int((safe_shelters["snap_status"] == "unmatched").sum()) == 0
            and len(safe_shelters) > 0
        ),
    }
    SNAP_VALIDATION_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[INFO] saved: {SNAP_VALIDATION_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["origins", "shelters", "validate", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "origins":
        snap_agent_origins()
    elif args.command == "shelters":
        snap_shelters()
    elif args.command == "validate":
        validate_snap()
    elif args.command == "all":
        snap_agent_origins()
        snap_shelters()
        validate_snap()


if __name__ == "__main__":
    main()
