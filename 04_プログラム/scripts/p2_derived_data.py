"""Phase 2: SUMO投入前の派生データ生成。"""

from __future__ import annotations

import argparse
import json
import math
import pickle
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_DERIVED_DIR = PROGRAM_DIR / "output" / "sumo" / "derived"
FLOOD_PKL_PATH = PROGRAM_DIR / "output" / "flood" / "flood_polygons.pkl"
ORIGINS_CSV_PATH = PROGRAM_DIR / "output" / "agents" / "origin_points.csv"
SHELTERS_CSV_PATH = PROGRAM_DIR / "output" / "agents" / "shelters.csv"

TIME_MAPPING_CSV = SUMO_DERIVED_DIR / "time_mapping_sumo.csv"
SHELTERS_SAFETY_CSV = SUMO_DERIVED_DIR / "shelters_safety.csv"
AGENT_ORIGINS_10PCT_CSV = SUMO_DERIVED_DIR / "agent_origins_10pct.csv"
DERIVED_VALIDATION_JSON = SUMO_DERIVED_DIR / "derived_data_validation.json"

HOUSEHOLD_SIZE = getattr(config, "HOUSEHOLD_SIZE", 2.3)


def ensure_dirs() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def parse_dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def generate_time_mapping() -> None:
    ensure_dirs()
    start = parse_dt(config.SIM_START_EPOCH)
    timestamps = [parse_dt(ts) for ts in config.KML_TIMESTAMPS]
    max_elapsed = int((timestamps[-1] - start).total_seconds())
    sim_duration_sec = int(config.SIM_DURATION_H * 3600)

    rows = []
    for idx, ts in enumerate(timestamps):
        elapsed = int((ts - start).total_seconds())
        sim_time = round(elapsed / max_elapsed * sim_duration_sec)
        rows.append(
            {
                "time_id": f"t{idx}",
                "source_timestamp": ts.isoformat(),
                "elapsed_sec_real": elapsed,
                "sim_time_sec": int(sim_time),
                "compression_ratio": sim_time / elapsed if elapsed else "",
                "notes": "linear_compression_to_6h",
            }
        )

    pd.DataFrame(rows).to_csv(TIME_MAPPING_CSV, index=False, encoding="utf-8")
    print(f"[INFO] saved: {TIME_MAPPING_CSV} ({len(rows)} rows)")


def load_flood_union() -> gpd.GeoDataFrame:
    with FLOOD_PKL_PATH.open("rb") as f:
        flood_by_time = pickle.load(f)
    frames = []
    for timestamp, gdf in flood_by_time.items():
        frame = gdf[["waterDepth", "geometry"]].copy()
        frame["source_timestamp"] = timestamp
        frames.append(frame)
    flood = pd.concat(frames, ignore_index=True)
    flood_gdf = gpd.GeoDataFrame(flood, geometry="geometry", crs=config.CRS_JGD2011)
    flood_gdf["waterDepth"] = pd.to_numeric(flood_gdf["waterDepth"], errors="coerce")
    return flood_gdf[flood_gdf["waterDepth"] >= config.FLOOD_DEPTH_THRESHOLD].copy()


def generate_shelters_safety() -> None:
    ensure_dirs()
    shelters = pd.read_csv(SHELTERS_CSV_PATH)
    shelters = shelters.reset_index(drop=True)
    shelters["shelter_id"] = [f"shelter_{idx + 1:03d}" for idx in range(len(shelters))]
    shelters_gdf = gpd.GeoDataFrame(
        shelters,
        geometry=[Point(lon, lat) for lon, lat in zip(shelters["lon"], shelters["lat"])],
        crs=config.CRS_WGS84,
    ).to_crs(config.CRS_JGD2011)

    flood = load_flood_union()
    joined = gpd.sjoin(
        shelters_gdf[["shelter_id", "geometry"]],
        flood[["waterDepth", "geometry"]],
        how="left",
        predicate="intersects",
    )
    max_depth = joined.groupby("shelter_id")["waterDepth"].max()

    rows = []
    for _, row in shelters.iterrows():
        shelter_id = row["shelter_id"]
        depth = max_depth.get(shelter_id)
        has_risk = not pd.isna(depth) and int(depth) >= config.FLOOD_DEPTH_THRESHOLD
        rows.append(
            {
                "shelter_id": shelter_id,
                "name": row["name"],
                "capacity": int(row["capacity"]) if not pd.isna(row["capacity"]) else "",
                "lon": row["lon"],
                "lat": row["lat"],
                "flood_risk": bool(has_risk),
                "max_water_depth_code": "" if pd.isna(depth) else int(depth),
                "is_safe_destination": not has_risk,
                "exclusion_reason": "flood_risk_water_depth_ge_2" if has_risk else "",
                "notes": "",
            }
        )

    pd.DataFrame(rows).to_csv(SHELTERS_SAFETY_CSV, index=False, encoding="utf-8")
    safe_count = sum(1 for row in rows if row["is_safe_destination"])
    print(f"[INFO] saved: {SHELTERS_SAFETY_CSV} ({len(rows)} shelters, {safe_count} safe)")


def full_vehicle_count(total_pop: int) -> int:
    if total_pop <= 0:
        return 0
    return max(1, math.ceil(total_pop / HOUSEHOLD_SIZE))


def ten_percent_vehicle_count(vehicle_count_full: int) -> int:
    if vehicle_count_full <= 0:
        return 0
    return max(1, math.ceil(vehicle_count_full / 10))


def generate_agent_origins_10pct() -> None:
    ensure_dirs()
    origins = pd.read_csv(ORIGINS_CSV_PATH, dtype={"KEY_CODE": str})
    rows = []
    for idx, row in origins.reset_index(drop=True).iterrows():
        total_pop = int(row["total_pop"])
        elderly_pop = int(row["elderly_pop"])
        households = total_pop / HOUSEHOLD_SIZE if total_pop > 0 else 0
        vehicles_full = full_vehicle_count(total_pop)
        vehicles_10_raw = vehicles_full / 10 if vehicles_full > 0 else 0
        rows.append(
            {
                "origin_id": f"origin_{idx + 1:04d}",
                "KEY_CODE": row["KEY_CODE"],
                "lon": row["lon"],
                "lat": row["lat"],
                "total_pop": total_pop,
                "elderly_pop": elderly_pop,
                "estimated_households": round(households, 3),
                "vehicle_count_full": vehicles_full,
                "vehicle_count_10pct_raw": round(vehicles_10_raw, 3),
                "vehicle_count_10pct": ten_percent_vehicle_count(vehicles_full),
                "vehicle_count_small": 1 if total_pop > 0 else 0,
                "notes": "ceil_household_and_10pct_min1_for_populated_mesh",
            }
        )

    pd.DataFrame(rows).to_csv(AGENT_ORIGINS_10PCT_CSV, index=False, encoding="utf-8")
    print(f"[INFO] saved: {AGENT_ORIGINS_10PCT_CSV} ({len(rows)} origins)")


def validate_derived_data() -> None:
    required = {
        "time_mapping_sumo": TIME_MAPPING_CSV,
        "shelters_safety": SHELTERS_SAFETY_CSV,
        "agent_origins_10pct": AGENT_ORIGINS_10PCT_CSV,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing derived files: {missing}")

    time_df = pd.read_csv(TIME_MAPPING_CSV)
    shelter_df = pd.read_csv(SHELTERS_SAFETY_CSV)
    origin_df = pd.read_csv(AGENT_ORIGINS_10PCT_CSV)

    summary = {
        "time_mapping_rows": int(len(time_df)),
        "time_mapping_min_sec": int(time_df["sim_time_sec"].min()),
        "time_mapping_max_sec": int(time_df["sim_time_sec"].max()),
        "shelter_count": int(len(shelter_df)),
        "safe_shelter_count": int(shelter_df["is_safe_destination"].sum()),
        "flood_risk_shelter_count": int(shelter_df["flood_risk"].sum()),
        "origin_count": int(len(origin_df)),
        "vehicle_count_small_total": int(origin_df["vehicle_count_small"].sum()),
        "vehicle_count_10pct_total": int(origin_df["vehicle_count_10pct"].sum()),
        "vehicle_count_full_total": int(origin_df["vehicle_count_full"].sum()),
        "can_proceed_to_sumo_snap": bool(
            len(time_df) == len(config.KML_TIMESTAMPS)
            and int(time_df["sim_time_sec"].max()) == config.SIM_DURATION_H * 3600
            and int(shelter_df["is_safe_destination"].sum()) > 0
            and int(origin_df["vehicle_count_small"].sum()) > 0
        ),
    }
    DERIVED_VALIDATION_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[INFO] saved: {DERIVED_VALIDATION_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["time", "shelters", "origins", "validate", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "time":
        generate_time_mapping()
    elif args.command == "shelters":
        generate_shelters_safety()
    elif args.command == "origins":
        generate_agent_origins_10pct()
    elif args.command == "validate":
        validate_derived_data()
    elif args.command == "all":
        generate_time_mapping()
        generate_shelters_safety()
        generate_agent_origins_10pct()
        validate_derived_data()


if __name__ == "__main__":
    main()
