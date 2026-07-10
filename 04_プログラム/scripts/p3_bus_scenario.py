"""Phase 3 B系: シナリオB（バス）最小スモークテスト用シナリオ生成。

目的（最小スライス）：本体パイプライン(`p2_region_pipeline.py`)に統合する前に、
**SUMO 1.26.0 の最大の技術未検証点**を小規模で先に潰す：
  (1) `<route repeat>` × `<stop busStop duration>` がループ動作するか
      （＝バスがピストン輸送を複数往復するか）
  (2) netconvert 生成網で bus vClass が通行可能か（バス停 lane・バス最短路が成立するか）
  (3) 閉鎖対象化したバスに迂回が効くか（本スモークでは閉鎖なし。B-c で検証）

このスクリプトは自己完結（本体を汚さない）。検証OKなら、ここで確立した
generate_bus_plan / bus_stops.add.xml / route repeat の作り方を
`p2_region_pipeline.py` の generate_bus_plan / generate_bus_routes へ移植する。

確定仕様の正本＝`交通シミュレーション調査/_シナリオB実装仕様_fable5.md`、
決定＝`交通シミュレーション調査/_判断結果_2026-07-07.md`
（上位N停ピストン／往復実測(repeat+6h打切り)／福祉N=3で1台保証／空走許容）。

── Windows での実行手順（このスクリプトも SUMO 実行も Windows 側）──
  1) シナリオ生成:  python scripts/p3_bus_scenario.py smoke --buses 1
  2) SUMO 実行:     sumo -c output/sumo/scenarios/scenario_b_smoke.sumocfg
  3) 確認:
     - コンソール/`scenario_b_smoke_sumo.log` に bus vClass 由来の route エラーが無いか
     - `output/sumo/results/scenario_b_smoke_stopinfo.xml` の <stopinfo> 件数
       ＝バスが busStop に停車した回数。1台が pickup/shelter を往復するたびに
       2件ずつ増える。複数往復（repeat）ぶんの stopinfo が並べば (1) 成立。
     - stopinfo が1周（2件）で止まる＝repeat が stop を繰り返さない → TraCI setRoute
       方式へ切替（B-c で対応）。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import config
from p2_sumo_env import configure_sumo_environment

configure_sumo_environment(require_tools=True)
import sumolib  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_DIR = PROGRAM_DIR / "output" / "sumo"
NET_XML_PATH = SUMO_DIR / "network" / "joso.net.xml"
DERIVED_DIR = SUMO_DIR / "derived"
SCENARIOS_DIR = SUMO_DIR / "scenarios"
RESULTS_DIR = SUMO_DIR / "results"

BUS_DEMAND_CANDIDATES_CSV = DERIVED_DIR / "bus_demand_candidates.csv"
SHELTERS_SUMO_CSV = DERIVED_DIR / "shelters_sumo.csv"
BUS_PLAN_CSV = DERIVED_DIR / "bus_plan.csv"
BUS_STOPS_ADD_XML = SCENARIOS_DIR / "bus_stops.add.xml"
SMOKE_ROU_XML = SCENARIOS_DIR / "scenario_b_smoke.rou.xml"
SMOKE_SUMOCFG = SCENARIOS_DIR / "scenario_b_smoke.sumocfg"
SMOKE_TRIPINFO = RESULTS_DIR / "scenario_b_smoke_tripinfo.xml"
SMOKE_STOPINFO = RESULTS_DIR / "scenario_b_smoke_stopinfo.xml"
SCENARIO_B_ROU_XML = SCENARIOS_DIR / "scenario_b.rou.xml"
SCENARIO_B_ASSIGNMENTS_CSV = DERIVED_DIR / "scenario_b_vehicle_assignments.csv"
SCENARIO_B_REDUCTION_CSV = DERIVED_DIR / "scenario_b_rescue_reduction.csv"

SIM_END_SEC = 21600  # 6時間（H1: 運行時間）


def configure_paths(city_code: str | None = None) -> None:
    """出力先を旧単独ディレクトリまたは地域別ディレクトリへ切り替える。"""
    global NET_XML_PATH, DERIVED_DIR, SCENARIOS_DIR, RESULTS_DIR
    global BUS_DEMAND_CANDIDATES_CSV, SHELTERS_SUMO_CSV, BUS_PLAN_CSV, BUS_STOPS_ADD_XML
    global SMOKE_ROU_XML, SMOKE_SUMOCFG, SMOKE_TRIPINFO, SMOKE_STOPINFO
    global SCENARIO_B_ROU_XML, SCENARIO_B_ASSIGNMENTS_CSV, SCENARIO_B_REDUCTION_CSV

    if city_code:
        region_dir = SUMO_DIR / "regions" / city_code
        NET_XML_PATH = region_dir / "network" / f"{city_code}.net.xml"
        DERIVED_DIR = region_dir / "derived"
        SCENARIOS_DIR = region_dir / "scenarios"
        RESULTS_DIR = region_dir / "results"
    else:
        NET_XML_PATH = SUMO_DIR / "network" / "joso.net.xml"
        DERIVED_DIR = SUMO_DIR / "derived"
        SCENARIOS_DIR = SUMO_DIR / "scenarios"
        RESULTS_DIR = SUMO_DIR / "results"

    BUS_DEMAND_CANDIDATES_CSV = DERIVED_DIR / "bus_demand_candidates.csv"
    SHELTERS_SUMO_CSV = DERIVED_DIR / "shelters_sumo.csv"
    BUS_PLAN_CSV = DERIVED_DIR / "bus_plan.csv"
    BUS_STOPS_ADD_XML = SCENARIOS_DIR / "bus_stops.add.xml"
    SMOKE_ROU_XML = SCENARIOS_DIR / "scenario_b_smoke.rou.xml"
    SMOKE_SUMOCFG = SCENARIOS_DIR / "scenario_b_smoke.sumocfg"
    SMOKE_TRIPINFO = RESULTS_DIR / "scenario_b_smoke_tripinfo.xml"
    SMOKE_STOPINFO = RESULTS_DIR / "scenario_b_smoke_stopinfo.xml"
    SCENARIO_B_ROU_XML = SCENARIOS_DIR / "scenario_b.rou.xml"
    SCENARIO_B_ASSIGNMENTS_CSV = DERIVED_DIR / "scenario_b_vehicle_assignments.csv"
    SCENARIO_B_REDUCTION_CSV = DERIVED_DIR / "scenario_b_rescue_reduction.csv"


def sumo_relpath(path: Path, base_dir: Path) -> str:
    return os.path.relpath(path, base_dir).replace("\\", "/")


def ensure_dirs() -> None:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def read_net() -> Any:
    return sumolib.net.readNet(str(NET_XML_PATH))


def xy(net: Any, lon: float, lat: float) -> tuple[float, float]:
    x, y = net.convertLonLat2XY(lon, lat)
    return float(x), float(y)


def nearest_shelter(net: Any, origin: pd.Series, shelters: pd.DataFrame) -> pd.Series:
    """origin から最寄りの安全避難所を返す（p2_sumo_scenario.py と同ロジック）。"""
    ox, oy = xy(net, float(origin["lon"]), float(origin["lat"]))
    candidates: list[tuple[float, pd.Series]] = []
    for _, shelter in shelters.iterrows():
        sx, sy = xy(net, float(shelter["lon"]), float(shelter["lat"]))
        dist2 = (ox - sx) ** 2 + (oy - sy) ** 2
        same_edge_penalty = 1_000_000_000 if shelter["sumo_edge_id"] == origin["sumo_edge_id"] else 0
        candidates.append((dist2 + same_edge_penalty, shelter))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def pick_bus_lane(net: Any, edge_id: str) -> tuple[Any, bool]:
    """edge のうち bus vClass 通行可のレーンを返す。無ければ先頭レーン＋False。"""
    edge = net.getEdge(edge_id)
    for lane in edge.getLanes():
        if lane.allows("bus"):
            return lane, True
    return edge.getLanes()[0], False


def bus_stop_positions(lane: Any) -> tuple[float, float]:
    """lane 長に収まる busStop の startPos/endPos を返す（長 <=15m）。"""
    lane_len = float(lane.getLength())
    stop_len = min(float(config.BUS_STOP_LENGTH_M), max(1.0, lane_len - 1.0))
    start = 0.0
    end = start + stop_len
    if end > lane_len:
        end = lane_len
        start = max(0.0, end - stop_len)
    return round(start, 2), round(end, 2)


def bus_edge_path(net: Any, from_edge_id: str, to_edge_id: str) -> list[str] | None:
    """bus vClass での最短 edge 列。到達不能なら None。"""
    edges, _cost = net.getShortestPath(
        net.getEdge(from_edge_id), net.getEdge(to_edge_id), vClass="bus"
    )
    if edges is None:
        return None
    return [edge.getID() for edge in edges]


def welfare_bus_count(n_bus: int) -> int:
    """福祉車両台数。round(比率*N)。N>=3 では最低1台保証（決定 2026-07-07）。"""
    base = int(round(float(config.BUS_WELFARE_RATIO) * n_bus))
    if n_bus >= 3:
        return max(base, int(config.BUS_WELFARE_MIN_COUNT))
    return base


def build_bus_plan(net: Any, n_bus: int) -> list[dict[str, Any]]:
    """需要上位 n_bus 停のバス計画を作る（決定：上位N停ピストン）。

    各停：pickup edge（候補メッシュ）→最寄り安全避難所。bus 通行可レーンに
    pickup/shelter の busStop を敷設。福祉車は type4 最大の停へ割当。
    """
    cand = pd.read_csv(BUS_DEMAND_CANDIDATES_CSV, dtype={"KEY_CODE": str, "sumo_edge_id": str})
    cand = cand.sort_values("priority_rank", ascending=True).reset_index(drop=True)

    shelters = pd.read_csv(SHELTERS_SUMO_CSV, dtype={"sumo_edge_id": str})
    safe = shelters[
        (shelters["is_safe_destination"].astype(str).str.lower() == "true")
        & (shelters["snap_status"].astype(str) != "unmatched")
        & (shelters["sumo_edge_id"].fillna("").astype(str).str.len() > 0)
    ].copy()
    if safe.empty:
        raise ValueError("no routable safe shelter for bus plan")

    selected: list[dict[str, Any]] = []
    for _, row in cand.iterrows():
        pickup_edge = str(row["sumo_edge_id"])
        shelter = nearest_shelter(net, row, safe)
        shelter_edge = str(shelter["sumo_edge_id"])

        pickup_lane, pickup_bus_ok = pick_bus_lane(net, pickup_edge)
        shelter_lane, shelter_bus_ok = pick_bus_lane(net, shelter_edge)
        min_pickup_len = float(config.BUS_STOP_LENGTH_M) + 1.0
        if float(pickup_lane.getLength()) < min_pickup_len:
            continue
        if not bus_edge_path(net, pickup_edge, shelter_edge):
            continue
        if not bus_edge_path(net, shelter_edge, pickup_edge):
            continue
        pu_start, pu_end = bus_stop_positions(pickup_lane)
        sh_start, sh_end = bus_stop_positions(shelter_lane)

        selected.append(
            {
                "priority_rank": int(row["priority_rank"]),
                "origin_id": row["origin_id"],
                "KEY_CODE": row["KEY_CODE"],
                "pickup_edge": pickup_edge,
                "pickup_stop_id": f"bs_{row['origin_id']}",
                "pickup_lane": pickup_lane.getID(),
                "pickup_start_pos": pu_start,
                "pickup_end_pos": pu_end,
                "pickup_bus_lane_ok": pickup_bus_ok,
                "shelter_id": shelter["shelter_id"],
                "shelter_name": shelter["name"],
                "shelter_edge": shelter_edge,
                "shelter_stop_id": f"bs_shelter_{shelter['shelter_id']}",
                "shelter_lane": shelter_lane.getID(),
                "shelter_start_pos": sh_start,
                "shelter_end_pos": sh_end,
                "shelter_bus_lane_ok": shelter_bus_ok,
                "bus_candidate_population": int(row["bus_candidate_population"]),
                "type4_no_car_elderly_pop": int(row["type4_no_car_elderly_pop"]),
            }
        )
        if len(selected) >= n_bus:
            break

    if len(selected) < n_bus:
        raise ValueError(f"routable bus stops are fewer than requested: {len(selected)}/{n_bus}")

    n_welfare = welfare_bus_count(n_bus)
    welfare_ranks = {
        row["priority_rank"]
        for row in sorted(
            selected,
            key=lambda item: item["type4_no_car_elderly_pop"],
            reverse=True,
        )[:n_welfare]
    }
    plan: list[dict[str, Any]] = []
    for bus_index, row in enumerate(selected, start=1):
        is_welfare = row["priority_rank"] in welfare_ranks
        row = dict(row)
        row["bus_id"] = f"bus_{'wf' if is_welfare else 'std'}_{bus_index}"
        row["bus_vtype"] = "bus_welfare" if is_welfare else "bus_standard"
        plan.append(row)
    return plan


def write_bus_plan_csv(plan: list[dict[str, Any]]) -> None:
    fieldnames = list(plan[0].keys())
    with BUS_PLAN_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(plan)
    print(f"[INFO] saved: {BUS_PLAN_CSV} ({len(plan)} bus stops)")


def write_bus_stops_add(plan: list[dict[str, Any]]) -> None:
    """pickup 側と shelter 側の <busStop> を additional として書き出す。"""
    root = ET.Element("additional")
    seen: set[str] = set()
    for row in plan:
        for prefix in ("pickup", "shelter"):
            stop_id = row[f"{prefix}_stop_id"]
            if stop_id in seen:
                continue
            seen.add(stop_id)
            ET.SubElement(
                root,
                "busStop",
                {
                    "id": stop_id,
                    "lane": row[f"{prefix}_lane"],
                    "startPos": str(row[f"{prefix}_start_pos"]),
                    "endPos": str(row[f"{prefix}_end_pos"]),
                    "name": str(row.get("shelter_name", "")) if prefix == "shelter" else str(row["origin_id"]),
                },
            )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(BUS_STOPS_ADD_XML, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] saved: {BUS_STOPS_ADD_XML} ({len(seen)} busStops)")


def write_smoke_routes(net: Any, plan: list[dict[str, Any]]) -> list[str]:
    """バス vType と、各バス1台のピストン route(repeat)＋停車を書き出す。

    返り値：bus vClass で経路が作れなかった bus_id の警告リスト。
    """
    warnings: list[str] = []
    root = ET.Element("routes")
    std_cap = int(config.BUS_CAPACITY_STD)
    wf_cap = int(config.BUS_CAPACITY_WELFARE)
    max_speed = str(config.BUS_MAXSPEED_MS)
    boarding = str(int(config.BUS_BOARDING_TIME_S))
    # 【2026-07-08 スモーク結果】SUMOの <route repeat> は閉ループ（末尾edge→先頭edge
    # が連結）を要求するため、pickup→shelter の片道ピストンには使えない
    # （Disconnected route エラー）。本スモークは repeat を使わず「1往復
    # （pickup→shelter→pickup）＋busStop2停」だけを検証し、バス走行と busStop
    # 停車の基礎を確認する。多往復（実測往復数）は本実装 B-c で TraCI setRoute
    # 動的方式で制御する（`_判断結果_2026-07-07.md` 実装進捗参照）。

    for vtype_id, cap, length in (
        ("bus_standard", std_cap, "12.0"),
        ("bus_welfare", wf_cap, "7.0"),
    ):
        ET.SubElement(
            root,
            "vType",
            {
                "id": vtype_id,
                "vClass": "bus",
                "personCapacity": str(cap),
                "length": length,
                "accel": "1.2",
                "decel": "4.0",
                "sigma": "0.5",
                "maxSpeed": max_speed,
            },
        )

    for row in plan:
        forward = bus_edge_path(net, row["pickup_edge"], row["shelter_edge"])
        backward = bus_edge_path(net, row["shelter_edge"], row["pickup_edge"])
        if not forward or not backward:
            warnings.append(
                f"{row['bus_id']}: bus vClass path not found "
                f"({row['pickup_edge']} <-> {row['shelter_edge']})"
            )
            continue
        # 復路先頭が往路末尾と重複するなら除去（append_rescue_vehicle と同方針）。
        if backward and forward and backward[0] == forward[-1]:
            backward = backward[1:]
        route_edges = forward + backward

        vehicle = ET.SubElement(
            root,
            "vehicle",
            {"id": row["bus_id"], "type": row["bus_vtype"], "depart": "0"},
        )
        # 1往復ぶんの静的ルート（pickup→shelter→pickup）。repeat は付けない。
        ET.SubElement(vehicle, "route", {"edges": " ".join(route_edges)})
        # 1サイクル＝pickup で乗車、shelter で降車の2停のみ（往復1回）。
        ET.SubElement(
            vehicle, "stop", {"busStop": row["pickup_stop_id"], "duration": boarding}
        )
        ET.SubElement(
            vehicle, "stop", {"busStop": row["shelter_stop_id"], "duration": boarding}
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(SMOKE_ROU_XML, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] saved: {SMOKE_ROU_XML}")
    return warnings


def write_smoke_sumocfg() -> None:
    root = ET.Element("configuration")
    input_el = ET.SubElement(root, "input")
    ET.SubElement(input_el, "net-file", {"value": sumo_relpath(NET_XML_PATH, SCENARIOS_DIR)})
    ET.SubElement(input_el, "route-files", {"value": SMOKE_ROU_XML.name})
    ET.SubElement(input_el, "additional-files", {"value": BUS_STOPS_ADD_XML.name})
    time_el = ET.SubElement(root, "time")
    ET.SubElement(time_el, "begin", {"value": "0"})
    ET.SubElement(time_el, "end", {"value": str(SIM_END_SEC)})
    output_el = ET.SubElement(root, "output")
    # stop-output が (1) の判定材料：<stopinfo> の件数＝バスの停車回数。
    ET.SubElement(output_el, "stop-output", {"value": sumo_relpath(SMOKE_STOPINFO, SCENARIOS_DIR)})
    ET.SubElement(output_el, "tripinfo-output", {"value": sumo_relpath(SMOKE_TRIPINFO, SCENARIOS_DIR)})
    report_el = ET.SubElement(root, "report")
    ET.SubElement(report_el, "no-step-log", {"value": "true"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(SMOKE_SUMOCFG, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] saved: {SMOKE_SUMOCFG}")


def run_smoke(n_bus: int) -> None:
    ensure_dirs()
    net = read_net()
    plan = build_bus_plan(net, n_bus)
    write_bus_plan_csv(plan)
    write_bus_stops_add(plan)
    warnings = write_smoke_routes(net, plan)
    write_smoke_sumocfg()

    # bus vClass 通行可否のサマリ（要検証(2)の即時判定）。
    lane_issues = [
        row["bus_id"]
        for row in plan
        if not (row["pickup_bus_lane_ok"] and row["shelter_bus_lane_ok"])
    ]
    print("")
    print("=== スモークテスト生成サマリ ===")
    print(f"  バス台数: {len(plan)}  （うち福祉: {welfare_bus_count(n_bus)}）")
    if lane_issues:
        print(f"  [要検証(2)] bus非対応レーンに敷設したバス停あり: {lane_issues}")
        print("    → netconvert網でbus vClassが許可されていない可能性。SUMO実行で確認。")
    else:
        print("  [OK] 全バス停が bus vClass 通行可レーンに敷設できた。")
    if warnings:
        print(f"  [要検証(2)] bus最短路が作れないバス: {warnings}")
    print("")
    print("次に:  sumo(.exe) -c output/sumo/scenarios/scenario_b_smoke.sumocfg")
    print("確認: output/sumo/results/scenario_b_smoke_stopinfo.xml の <stopinfo> 件数")
    print("      本スモークは1往復のみ。1台につき pickup/shelter の2停＝<stopinfo>2件/台。")
    print("      2件出れば『バス走行＋busStop停車』の基礎はOK（多往復は本実装B-cのTraCI setRouteで）。")


def allocate_reductions(raw_by_origin: dict[str, float], caps: dict[str, int]) -> dict[str, int]:
    target = min(int(math.floor(sum(raw_by_origin.values()))), sum(caps.values()))
    reductions = {
        origin_id: min(int(math.floor(raw)), caps.get(origin_id, 0))
        for origin_id, raw in raw_by_origin.items()
    }
    current = sum(reductions.values())
    candidates = sorted(
        raw_by_origin,
        key=lambda origin_id: raw_by_origin[origin_id] - math.floor(raw_by_origin[origin_id]),
        reverse=True,
    )
    idx = 0
    while current < target and candidates:
        origin_id = candidates[idx % len(candidates)]
        if reductions[origin_id] < caps.get(origin_id, 0):
            reductions[origin_id] += 1
            current += 1
        idx += 1
        if idx > len(candidates) * 2 and all(
            reductions[o] >= caps.get(o, 0) for o in candidates
        ):
            break
    return reductions


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def route_vehicle_count(root: ET.Element) -> int:
    return sum(1 for child in root if child.tag in {"trip", "vehicle"})


def arrived_passengers_for_reduction(
    passenger_log: Path,
    bus_log: Path,
    *,
    sim_end_sec: int = SIM_END_SEC,
) -> pd.DataFrame:
    passengers = pd.read_csv(passenger_log, dtype={"origin_id": str, "bus_id": str, "trip_seq": str})
    buses = pd.read_csv(bus_log, dtype={"bus_id": str, "trip_seq": str})
    terminated = buses[
        buses["terminated"].astype(str).str.lower().isin(["true", "1", "yes"])
        & (buses["boarded_count"].astype(float) > 0)
    ]
    terminated_keys = set(zip(terminated["bus_id"], terminated["trip_seq"]))
    terminal_arrival = passengers["arrival_time_s"].astype(str).str.split(".", n=1).str[0] == str(sim_end_sec)
    arrived = passengers["arrived"].astype(str).str.lower().isin(["true", "1", "yes"])
    terminated_trip = [
        (str(row.bus_id), str(row.trip_seq)) in terminated_keys
        for row in passengers[["bus_id", "trip_seq"]].itertuples(index=False)
    ]
    return passengers[arrived & ~pd.Series(terminated_trip, index=passengers.index) & ~terminal_arrival].copy()


def build_scenario_b_routes(
    *,
    expected_reduction_count: int | None = None,
    expected_vehicle_count: int | None = None,
) -> None:
    """実測バス輸送人数を救出走行削減へ反映した scenario_b.rou.xml を作る。"""
    passenger_log = RESULTS_DIR / "scenario_b_passenger_log.csv"
    bus_log = RESULTS_DIR / "scenario_b_bus_log.csv"
    bus_summary = RESULTS_DIR / "scenario_b_bus_summary.json"
    scenario_a_rou = SCENARIOS_DIR / "scenario_a.rou.xml"
    scenario_a_assignments = DERIVED_DIR / "scenario_a_vehicle_assignments.csv"
    if not passenger_log.exists():
        raise FileNotFoundError(f"missing bus passenger log: {passenger_log}")
    if not bus_log.exists():
        raise FileNotFoundError(f"missing bus log: {bus_log}")
    if not scenario_a_rou.exists() or not scenario_a_assignments.exists():
        raise FileNotFoundError("scenario_a.rou.xml / scenario_a_vehicle_assignments.csv が必要です")

    sim_end_sec = SIM_END_SEC
    if bus_summary.exists():
        summary = json.loads(bus_summary.read_text(encoding="utf-8"))
        sim_end_sec = int(float(summary.get("run_manifest", {}).get("sim_end_sec", SIM_END_SEC)))
    arrived = arrived_passengers_for_reduction(passenger_log, bus_log, sim_end_sec=sim_end_sec)
    arrived_by_origin = arrived.groupby("origin_id").size().to_dict()

    assignments = pd.read_csv(scenario_a_assignments, dtype={"origin_id": str, "vehicle_id": str})
    rescue = assignments[assignments["vehicle_kind"] == "rescue_car"].copy()
    rescue_by_origin = rescue.groupby("origin_id").size().to_dict()
    k = float(getattr(config, "RESCUE_PER_VEHICLE_K", getattr(config, "HOUSEHOLD_SIZE", 2.3)))
    raw_by_origin = {origin_id: count / k for origin_id, count in arrived_by_origin.items()}
    reductions = allocate_reductions(raw_by_origin, rescue_by_origin)
    reduction_total = sum(reductions.values())
    if expected_reduction_count is not None and reduction_total != expected_reduction_count:
        raise AssertionError(
            f"rescue reduction mismatch: expected {expected_reduction_count}, got {reduction_total}"
        )

    remove_ids: set[str] = set()
    reduction_rows: list[dict[str, Any]] = []
    for origin_id, reduce_count in reductions.items():
        candidates = (
            rescue[rescue["origin_id"] == origin_id]
            .sort_values("vehicle_id")["vehicle_id"]
            .tolist()
        )
        selected = candidates[:reduce_count]
        remove_ids.update(selected)
        reduction_rows.append(
            {
                "origin_id": origin_id,
                "bus_arrived_passengers": int(arrived_by_origin.get(origin_id, 0)),
                "rescue_reduction_raw": round(float(raw_by_origin.get(origin_id, 0.0)), 3),
                "rescue_removed_count": int(reduce_count),
                "rescue_count_before": int(rescue_by_origin.get(origin_id, 0)),
                "rescue_count_after": int(rescue_by_origin.get(origin_id, 0) - reduce_count),
            }
        )

    tree = ET.parse(scenario_a_rou)
    root = tree.getroot()
    for child in list(root):
        if child.tag in {"trip", "vehicle"} and child.attrib.get("id") in remove_ids:
            root.remove(child)
    route_count = route_vehicle_count(root)
    ET.indent(tree, space="  ")
    tree.write(SCENARIO_B_ROU_XML, encoding="utf-8", xml_declaration=True)

    scenario_b_assignments = assignments[~assignments["vehicle_id"].isin(remove_ids)].copy()
    if route_count != len(scenario_b_assignments):
        raise AssertionError(
            f"AC3 route/assignment count mismatch: route={route_count}, assignments={len(scenario_b_assignments)}"
        )
    if expected_vehicle_count is not None and route_count != expected_vehicle_count:
        raise AssertionError(
            f"AC3 vehicle count mismatch: expected {expected_vehicle_count}, got {route_count}"
        )
    scenario_b_assignments.to_csv(SCENARIO_B_ASSIGNMENTS_CSV, index=False, encoding="utf-8")
    pd.DataFrame(reduction_rows).sort_values("origin_id").to_csv(
        SCENARIO_B_REDUCTION_CSV, index=False, encoding="utf-8"
    )

    print(f"[INFO] saved: {SCENARIO_B_ROU_XML}")
    print(f"[INFO] saved: {SCENARIO_B_ASSIGNMENTS_CSV}")
    print(f"[INFO] saved: {SCENARIO_B_REDUCTION_CSV}")
    print(
        "[INFO] scenario_b accounting: "
        f"bus_arrived={len(arrived)}, rescue_removed={len(remove_ids)}, "
        f"vehicles_before={len(assignments)}, vehicles_after={len(scenario_b_assignments)}, "
        f"route_vehicles={route_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_smoke = sub.add_parser("smoke", help="最小バスシナリオを生成（SUMO実行はWindows側）")
    p_smoke.add_argument(
        "--buses",
        type=int,
        default=1,
        help="バス台数＝上位N停（既定1。最初は1で repeat×busStop 挙動だけ確認）",
    )
    p_smoke.add_argument(
        "--city-code",
        help="地域別SUMO出力を対象にする場合の市区町村コード（例: 08211）",
    )
    p_build_b = sub.add_parser(
        "build-scenario-b",
        help="実測バス輸送ログから救出走行を削減したscenario_b.rou.xmlを生成",
    )
    p_build_b.add_argument(
        "--city-code",
        help="地域別SUMO出力を対象にする場合の市区町村コード（例: 08211）",
    )
    p_build_b.add_argument("--expected-reduction", type=int)
    p_build_b.add_argument("--expected-vehicles", type=int)
    args = parser.parse_args()
    if args.command == "smoke":
        configure_paths(args.city_code)
        run_smoke(args.buses)
    elif args.command == "build-scenario-b":
        configure_paths(args.city_code)
        build_scenario_b_routes(
            expected_reduction_count=args.expected_reduction,
            expected_vehicle_count=args.expected_vehicles,
        )


if __name__ == "__main__":
    main()
