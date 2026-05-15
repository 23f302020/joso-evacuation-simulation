"""Phase 2: SUMOシナリオA route/config生成と基本走行確認。"""

from __future__ import annotations

import argparse
import csv
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd

from p2_sumo_env import configure_sumo_environment

configure_sumo_environment(require_tools=True)
import sumolib  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_DIR = PROGRAM_DIR / "output" / "sumo"
SUMO_NETWORK_DIR = SUMO_DIR / "network"
SUMO_DERIVED_DIR = SUMO_DIR / "derived"
SUMO_SCENARIOS_DIR = SUMO_DIR / "scenarios"
SUMO_RESULTS_DIR = SUMO_DIR / "results"

NET_XML_PATH = SUMO_NETWORK_DIR / "joso.net.xml"
AGENT_ORIGINS_SUMO_CSV = SUMO_DERIVED_DIR / "agent_origins_sumo.csv"
SHELTERS_SUMO_CSV = SUMO_DERIVED_DIR / "shelters_sumo.csv"

SMALL_ROU_XML = SUMO_SCENARIOS_DIR / "scenario_a_small.rou.xml"
SMALL_SUMOCFG = SUMO_SCENARIOS_DIR / "scenario_a_small.sumocfg"
SMALL_ASSIGNMENTS_CSV = SUMO_DERIVED_DIR / "scenario_a_small_vehicle_assignments.csv"
SMALL_TRIPINFO_XML = SUMO_RESULTS_DIR / "scenario_a_small_tripinfo.xml"
SMALL_SUMO_LOG = SUMO_RESULTS_DIR / "scenario_a_small_sumo.log"

SCENARIOS = {
    "small": {
        "count_column": "vehicle_count_small",
        "vehicle_prefix": "veh_small",
        "rou": SUMO_SCENARIOS_DIR / "scenario_a_small.rou.xml",
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a_small.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_small_vehicle_assignments.csv",
        "tripinfo": SUMO_RESULTS_DIR / "scenario_a_small_tripinfo.xml",
        "sumo_log": SUMO_RESULTS_DIR / "scenario_a_small_sumo.log",
        "fcd": SUMO_RESULTS_DIR / "scenario_a_small_fcd.xml",
        "fcd_period": "30",
    },
    "10pct": {
        "count_column": "vehicle_count_10pct",
        "vehicle_prefix": "veh_10pct",
        "rou": SUMO_SCENARIOS_DIR / "scenario_a_10pct.rou.xml",
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a_10pct.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_10pct_vehicle_assignments.csv",
        "tripinfo": SUMO_RESULTS_DIR / "scenario_a_10pct_tripinfo.xml",
        "sumo_log": SUMO_RESULTS_DIR / "scenario_a_10pct_sumo.log",
        "fcd": SUMO_RESULTS_DIR / "scenario_a_10pct_fcd.xml",
        "fcd_period": "30",
    },
    "full": {
        "count_column": "vehicle_count_full",
        "vehicle_prefix": "veh_full",
        "rou": SUMO_SCENARIOS_DIR / "scenario_a.rou.xml",
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_vehicle_assignments.csv",
        "tripinfo": SUMO_RESULTS_DIR / "scenario_a_tripinfo.xml",
        "sumo_log": SUMO_RESULTS_DIR / "scenario_a_sumo.log",
        "fcd": SUMO_RESULTS_DIR / "scenario_a_fcd.xml",
        "fcd_period": "60",
    },
}


def ensure_dirs() -> None:
    SUMO_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    SUMO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def read_net():
    return sumolib.net.readNet(str(NET_XML_PATH))


def xy(net: Any, lon: float, lat: float) -> tuple[float, float]:
    x, y = net.convertLonLat2XY(lon, lat)
    return float(x), float(y)


def nearest_shelter(net: Any, origin: pd.Series, shelters: pd.DataFrame) -> pd.Series:
    ox, oy = xy(net, float(origin["lon"]), float(origin["lat"]))
    candidates = []
    for _, shelter in shelters.iterrows():
        sx, sy = xy(net, float(shelter["lon"]), float(shelter["lat"]))
        dist2 = (ox - sx) ** 2 + (oy - sy) ** 2
        same_edge_penalty = 1_000_000_000 if shelter["sumo_edge_id"] == origin["sumo_edge_id"] else 0
        candidates.append((dist2 + same_edge_penalty, shelter))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def write_xml(path: Path, root: ET.Element) -> None:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def generate_scenario(scenario_name: str) -> None:
    ensure_dirs()
    scenario = SCENARIOS[scenario_name]
    net = read_net()
    origins = pd.read_csv(AGENT_ORIGINS_SUMO_CSV, dtype={"KEY_CODE": str})
    shelters = pd.read_csv(SHELTERS_SUMO_CSV)
    safe_shelters = shelters[shelters["is_safe_destination"] == True].copy()  # noqa: E712
    if safe_shelters.empty:
        raise ValueError("No safe shelter is available for route generation.")

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
    for _, origin in origins.iterrows():
        shelter = nearest_shelter(net, origin, safe_shelters)
        vehicle_count = int(origin[scenario["count_column"]])
        for seq in range(vehicle_count):
            vehicle_id = f"{scenario['vehicle_prefix']}_{origin['origin_id']}_{seq + 1:04d}"
            ET.SubElement(
                routes,
                "trip",
                {
                    "id": vehicle_id,
                    "type": "passenger_car",
                    "depart": "0",
                    "from": str(origin["sumo_edge_id"]),
                    "to": str(shelter["sumo_edge_id"]),
                },
            )
            assignments.append(
                {
                    "vehicle_id": vehicle_id,
                    "origin_id": origin["origin_id"],
                    "KEY_CODE": origin["KEY_CODE"],
                    "from_sumo_edge_id": origin["sumo_edge_id"],
                    "shelter_id": shelter["shelter_id"],
                    "shelter_name": shelter["name"],
                    "to_sumo_edge_id": shelter["sumo_edge_id"],
                    "depart": 0,
                }
            )

    write_xml(scenario["rou"], routes)

    with scenario["assignments"].open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "vehicle_id",
            "origin_id",
            "KEY_CODE",
            "from_sumo_edge_id",
            "shelter_id",
            "shelter_name",
            "to_sumo_edge_id",
            "depart",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(assignments)

    config = ET.Element("configuration")
    input_el = ET.SubElement(config, "input")
    ET.SubElement(input_el, "net-file", {"value": "../network/joso.net.xml"})
    ET.SubElement(input_el, "route-files", {"value": scenario["rou"].name})
    time_el = ET.SubElement(config, "time")
    ET.SubElement(time_el, "begin", {"value": "0"})
    ET.SubElement(time_el, "end", {"value": "21600"})
    output_el = ET.SubElement(config, "output")
    ET.SubElement(output_el, "tripinfo-output", {"value": f"../results/{scenario['tripinfo'].name}"})
    ET.SubElement(output_el, "fcd-output", {"value": f"../results/{scenario['fcd'].name}"})
    processing_el = ET.SubElement(config, "processing")
    ET.SubElement(processing_el, "ignore-route-errors", {"value": "false"})
    report_el = ET.SubElement(config, "report")
    ET.SubElement(report_el, "no-step-log", {"value": "true"})
    ET.SubElement(report_el, "duration-log.disable", {"value": "true"})
    write_xml(scenario["sumocfg"], config)

    print(f"[INFO] saved: {scenario['rou']}")
    print(f"[INFO] saved: {scenario['sumocfg']}")
    print(f"[INFO] saved: {scenario['assignments']} ({len(assignments)} vehicles)")


def generate_small_scenario() -> None:
    generate_scenario("small")


def run_sumo_scenario(scenario_name: str = "small") -> None:
    ensure_dirs()
    scenario = SCENARIOS[scenario_name]
    if not scenario["sumocfg"].exists():
        generate_scenario(scenario_name)
    command = ["sumo", "-c", str(scenario["sumocfg"])]
    result = subprocess.run(command, cwd=SUMO_SCENARIOS_DIR, text=True, capture_output=True, check=False)
    scenario["sumo_log"].write_text(
        "\n".join(
            [
                "$ " + " ".join(command),
                "",
                "[stdout]",
                result.stdout,
                "[stderr]",
                result.stderr,
                f"[returncode] {result.returncode}",
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"SUMO scenario failed. See {scenario['sumo_log']}")
    print(f"[INFO] SUMO {scenario_name} scenario succeeded")
    print(f"[INFO] log: {scenario['sumo_log']}")
    print(f"[INFO] tripinfo: {scenario['tripinfo']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "small",
            "10pct",
            "full",
            "run-small",
            "run-10pct",
            "run-full",
            "all",
        ],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "small":
        generate_scenario("small")
    elif args.command == "10pct":
        generate_scenario("10pct")
    elif args.command == "full":
        generate_scenario("full")
    elif args.command == "run-small":
        run_sumo_scenario("small")
    elif args.command == "run-10pct":
        run_sumo_scenario("10pct")
    elif args.command == "run-full":
        run_sumo_scenario("full")
    elif args.command == "all":
        for scenario_name in SCENARIOS:
            generate_scenario(scenario_name)
            run_sumo_scenario(scenario_name)


if __name__ == "__main__":
    main()
