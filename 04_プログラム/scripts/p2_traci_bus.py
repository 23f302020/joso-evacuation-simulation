"""Phase 3 B系: シナリオB バスの TraCI ループ本体（B-c）。

`_Bc実装ブループリント_fable5.md` §1〜4 と判断確定（§6）に基づく。会計は
`p3_bus_accounting.py`（検証済み）を import して使う。`p2_traci_closure.py` は
一切変更しない（バス用の閉鎖ラッパは本モジュールに置く＝JB-1）。

往復制御は TraCI `setRoute` 動的方式（`route repeat` は SUMO で閉ループ要求のため
不可と実証済み・2026-07-08 スモーク）。停車検知は「busStop 停車（isStopped）＋
getRoadID 一致」。乗降滞在は `setBusStop(duration)` で与える（スモークで実証済み方式）。

確定判断（本ループに効くもの）：
- 6-2 二層報告（バス単独／バス+救出）／6-3 需要枯渇バスは早期terminate／
  6-4 閉鎖打切りの onboard 客は最寄避難所へ送届＝完了／6-6 congestion にバスを含める／
  6-7 バスは全台 t=0 同時投入。JB-1〜5 は §4。

── 乗降検証スモーク（Sonnet がSUMOで実行）──
  python scripts/p2_traci_bus.py smoke-bus --buses 1 [--closure]
  → bus_vtypes.add.xml と bus のみの sumocfg を生成し TraCI 実行、3ログを出力。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import config
from p2_sumo_env import configure_sumo_environment

configure_sumo_environment(require_tools=True)
import traci  # noqa: E402
import sumolib  # noqa: E402
import p2_traci_common as traci_common  # noqa: E402

from p3_bus_accounting import (  # noqa: E402
    BusUnit,
    BusRuntime,
    board_passengers,
    alight_passengers,
    init_queues,
    load_bus_units,
    settle_stranded_to_rescue,
    stop_meta_from_plan,
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
SUMO_DIR = PROGRAM_DIR / "output" / "sumo"
NET_XML_PATH = SUMO_DIR / "network" / "joso.net.xml"
DERIVED_DIR = SUMO_DIR / "derived"
SCENARIOS_DIR = SUMO_DIR / "scenarios"
RESULTS_DIR = SUMO_DIR / "results"

BUS_PLAN_CSV = DERIVED_DIR / "bus_plan.csv"
AGENT_TYPES_CSV = DERIVED_DIR / "agent_types.csv"
BUS_STOPS_ADD_XML = SCENARIOS_DIR / "bus_stops.add.xml"
BUS_VTYPES_ADD_XML = SCENARIOS_DIR / "bus_vtypes.add.xml"
SMOKE_BUS_SUMOCFG = SCENARIOS_DIR / "scenario_b_busonly.sumocfg"
CLOSURE_TIMELINE_JSON = DERIVED_DIR / "closure_timeline_sumo.json"

PASSENGER_LOG_CSV = RESULTS_DIR / "scenario_b_passenger_log.csv"
BUS_LOG_CSV = RESULTS_DIR / "scenario_b_bus_log.csv"
BUS_SUMMARY_JSON = RESULTS_DIR / "scenario_b_bus_summary.json"
VEHICLE_LOG_CSV = RESULTS_DIR / "scenario_b_vehicle_log.csv"
CLOSURE_LOG_CSV = RESULTS_DIR / "scenario_b_closure_log.csv"
CONGESTION_LOG_CSV = RESULTS_DIR / "scenario_b_congestion_log.csv"
TRACI_SUMMARY_JSON = RESULTS_DIR / "scenario_b_traci_summary.json"

SIM_END_SEC = 21600  # 6時間
BUS_STOP_SPEED = 0.1  # これ未満を「停車」とみなす
LONG_STOP_THRESHOLD_SEC = 600
CONGESTION_LOG_INTERVAL_SEC = 60
DEFAULT_SUMO_SEED = 23423
BOARDING_S = int(config.BUS_BOARDING_TIME_S)  # 300
# 6時間残りがこれ未満なら新しい往復を始めない（往復推定。空車往復2028s＋乗降＋余裕）。
CYCLE_EST_S = 3000

PASSENGER_FIELDS = [
    "passenger_id", "origin_id", "KEY_CODE", "person_type", "category",
    "welfare_priority", "bus_id", "bus_vtype", "trip_seq", "board_time_s",
    "shelter_id", "arrival_time_s", "duration_s", "arrived",
]
BUS_LOG_FIELDS = [
    "bus_id", "bus_vtype", "trip_seq", "pickup_stop_id", "shelter_id",
    "board_time_s", "boarded_count", "arrive_shelter_time_s", "alight_count",
    "trip_duration_s", "deadhead", "closure_encountered", "reroute_success", "terminated",
    "termination_reason",
]


def configure_paths(city_code: str | None = None) -> None:
    """出力先を旧単独ディレクトリまたは地域別ディレクトリへ切り替える。"""
    global NET_XML_PATH, DERIVED_DIR, SCENARIOS_DIR, RESULTS_DIR
    global BUS_PLAN_CSV, AGENT_TYPES_CSV, BUS_STOPS_ADD_XML, BUS_VTYPES_ADD_XML
    global SMOKE_BUS_SUMOCFG, SMOKE_BUS_TRIPINFO, SMOKE_BUS_FCD, CLOSURE_TIMELINE_JSON
    global PASSENGER_LOG_CSV, BUS_LOG_CSV, BUS_SUMMARY_JSON
    global VEHICLE_LOG_CSV, CLOSURE_LOG_CSV, CONGESTION_LOG_CSV, TRACI_SUMMARY_JSON

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

    BUS_PLAN_CSV = DERIVED_DIR / "bus_plan.csv"
    AGENT_TYPES_CSV = DERIVED_DIR / "agent_types.csv"
    BUS_STOPS_ADD_XML = SCENARIOS_DIR / "bus_stops.add.xml"
    BUS_VTYPES_ADD_XML = SCENARIOS_DIR / "bus_vtypes.add.xml"
    SMOKE_BUS_SUMOCFG = SCENARIOS_DIR / "scenario_b_busonly.sumocfg"
    SMOKE_BUS_TRIPINFO = RESULTS_DIR / "scenario_b_busonly_tripinfo.xml"
    SMOKE_BUS_FCD = RESULTS_DIR / "scenario_b_busonly_fcd.xml"
    CLOSURE_TIMELINE_JSON = DERIVED_DIR / "closure_timeline_sumo.json"
    PASSENGER_LOG_CSV = RESULTS_DIR / "scenario_b_passenger_log.csv"
    BUS_LOG_CSV = RESULTS_DIR / "scenario_b_bus_log.csv"
    BUS_SUMMARY_JSON = RESULTS_DIR / "scenario_b_bus_summary.json"
    VEHICLE_LOG_CSV = RESULTS_DIR / "scenario_b_vehicle_log.csv"
    CLOSURE_LOG_CSV = RESULTS_DIR / "scenario_b_closure_log.csv"
    CONGESTION_LOG_CSV = RESULTS_DIR / "scenario_b_congestion_log.csv"
    TRACI_SUMMARY_JSON = RESULTS_DIR / "scenario_b_traci_summary.json"


def sumo_relpath(path: Path, base_dir: Path) -> str:
    return os.path.relpath(path, base_dir).replace("\\", "/")


def resolve_sumo_binary() -> str:
    env_binary = os.environ.get("SUMO_BINARY")
    if env_binary:
        return env_binary
    binary = sumolib.checkBinary("sumo")
    if Path(binary).exists():
        return binary
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        exe = Path(sumo_home) / "bin" / "sumo.exe"
        if exe.exists():
            return str(exe)
    return binary


def path_for_sumo(path: Path, sumo_binary: str) -> str:
    """WSL上でWindows版sumo.exeを呼ぶ場合だけPOSIXパスをWindows形式へ変換する。"""
    path_str = str(path)
    if os.name != "nt" and sumo_binary.lower().endswith(".exe"):
        try:
            result = subprocess.run(
                ["wslpath", "-w", path_str],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return path_str
    return path_str


def build_sumo_command(sumocfg: Path, sumo_binary: str, sumo_seed: int) -> list[str]:
    return [
        sumo_binary,
        "-c",
        path_for_sumo(sumocfg, sumo_binary),
        "--no-step-log",
        "true",
        "--seed",
        str(sumo_seed),
    ]


# ---------------------------------------------------------------------------
# シナリオ生成（バスのみ・乗降検証スモーク用）
# ---------------------------------------------------------------------------
def write_bus_vtypes_add() -> None:
    """TraCI 投入バス用の vType を additional として書き出す。"""
    root = ET.Element("additional")
    for vtype_id, cap, length in (
        ("bus_standard", config.BUS_CAPACITY_STD, "12.0"),
        ("bus_welfare", config.BUS_CAPACITY_WELFARE, "7.0"),
    ):
        ET.SubElement(
            root, "vType",
            {
                "id": vtype_id, "vClass": "bus", "personCapacity": str(int(cap)),
                "length": length, "accel": "1.2", "decel": "4.0", "sigma": "0.5",
                "maxSpeed": str(config.BUS_MAXSPEED_MS),
            },
        )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(BUS_VTYPES_ADD_XML, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] saved: {BUS_VTYPES_ADD_XML}")


def write_bus_sumocfg(
    sumocfg_path: Path,
    route_file: Path | None = None,
    tripinfo_output: Path | None = None,
    fcd_output: Path | None = None,
) -> None:
    """バスTraCI用の sumocfg。route_file を渡すと車両ルートと同居する。"""
    root = ET.Element("configuration")
    input_el = ET.SubElement(root, "input")
    ET.SubElement(input_el, "net-file", {"value": sumo_relpath(NET_XML_PATH, SCENARIOS_DIR)})
    if route_file is not None:
        ET.SubElement(input_el, "route-files", {"value": sumo_relpath(route_file, SCENARIOS_DIR)})
    ET.SubElement(
        input_el, "additional-files",
        {
            "value": ",".join(
                [
                    sumo_relpath(BUS_VTYPES_ADD_XML, SCENARIOS_DIR),
                    sumo_relpath(BUS_STOPS_ADD_XML, SCENARIOS_DIR),
                ]
            )
        },
    )
    time_el = ET.SubElement(root, "time")
    ET.SubElement(time_el, "begin", {"value": "0"})
    ET.SubElement(time_el, "end", {"value": str(SIM_END_SEC)})
    if tripinfo_output is not None or fcd_output is not None:
        output_el = ET.SubElement(root, "output")
        if tripinfo_output is not None:
            ET.SubElement(
                output_el,
                "tripinfo-output",
                {"value": sumo_relpath(tripinfo_output, SCENARIOS_DIR)},
            )
        if fcd_output is not None:
            ET.SubElement(output_el, "fcd-output", {"value": sumo_relpath(fcd_output, SCENARIOS_DIR)})
            ET.SubElement(output_el, "device.fcd.period", {"value": "60"})
            ET.SubElement(output_el, "fcd-output.geo", {"value": "true"})
    processing_el = ET.SubElement(root, "processing")
    ET.SubElement(processing_el, "ignore-route-errors", {"value": "false"})
    ET.SubElement(processing_el, "time-to-teleport", {"value": "-1"})
    report_el = ET.SubElement(root, "report")
    ET.SubElement(report_el, "no-step-log", {"value": "true"})
    ET.SubElement(report_el, "duration-log.disable", {"value": "true"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(sumocfg_path, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] saved: {sumocfg_path}")


def write_bus_only_sumocfg() -> None:
    """バスのみ（車なし）の sumocfg。乗降会計の検証用スモーク。"""
    write_bus_sumocfg(
        SMOKE_BUS_SUMOCFG,
        tripinfo_output=SMOKE_BUS_TRIPINFO,
        fcd_output=SMOKE_BUS_FCD,
    )


# ---------------------------------------------------------------------------
# TraCI ヘルパ
# ---------------------------------------------------------------------------
def path_bus(net: Any, from_edge: str, to_edge: str) -> list[str] | None:
    """bus vClass の最短 edge 列。到達不能なら None。"""
    edges, _cost = net.getShortestPath(
        net.getEdge(from_edge), net.getEdge(to_edge), vClass="bus"
    )
    if not edges:
        return None
    return [edge.getID() for edge in edges]


def close_edges_with_bus(edge_ids: list[str]) -> int:
    """JB-1: 乗用車に加えバスも通行禁止にする。"""
    closed = 0
    for edge_id in edge_ids:
        try:
            traci.edge.setDisallowed(edge_id, ["passenger", "bus"])
            closed += 1
        except traci.TraCIException:
            continue
    return closed


def load_closures() -> list[dict[str, Any]]:
    """閉鎖タイムライン（既存 closure_timeline_sumo.json）を読む。無ければ空。

    JSON は `{"metadata": {...}, "closures": [{sim_time_sec, closed_sumo_edge_ids, ...}]}`
    形式（旧: 直接 list も許容）。
    """
    if not CLOSURE_TIMELINE_JSON.exists():
        return []
    data = json.loads(CLOSURE_TIMELINE_JSON.read_text(encoding="utf-8"))
    items = data["closures"] if isinstance(data, dict) else data
    return sorted(items, key=lambda item: int(item["sim_time_sec"]))


def inject_buses(units: list[BusUnit], net: Any) -> None:
    """全バスを t=0 で pickup edge に投入（判断6-7・同時投入）。"""
    for bus in units:
        route_id = f"binit_{bus.bus_id}"
        initial_route = path_bus(net, bus.pickup_edge, bus.shelter_edge) or [bus.pickup_edge]
        try:
            traci.route.add(route_id, initial_route)
        except traci.TraCIException:
            pass
        traci.vehicle.add(
            bus.bus_id,
            route_id,
            typeID=bus.vtype,
            depart="0",
            departLane="best",
            departPos="free",
        )


def _is_stopped_at(bus_id: str, edge_id: str) -> bool:
    """バスが指定 edge の busStop で停車中か（getRoadID + 低速）。"""
    try:
        if traci.vehicle.getRoadID(bus_id) != edge_id:
            return False
        return (
            traci.vehicle.isStopped(bus_id)
            or traci.vehicle.getSpeed(bus_id) < BUS_STOP_SPEED
        )
    except traci.TraCIException:
        return False


def _queue_exhausted(bus: BusUnit, queues: dict[str, dict[str, int]]) -> bool:
    return sum(queues.get(bus.pickup_stop_id, {}).values()) == 0


def _remaining_route(bus_id: str) -> list[str]:
    """バスの現在位置以降の残ルート edge 列。"""
    route = traci.vehicle.getRoute(bus_id)
    idx = traci.vehicle.getRouteIndex(bus_id)
    return list(route[max(idx, 0):])


def _traci_route_edges(from_edge: str, to_edge: str, vtype: str) -> list[str]:
    try:
        stage = traci.simulation.findRoute(from_edge, to_edge, vType=vtype)
        return list(stage.edges)
    except traci.TraCIException:
        return []


def mark_onboard_not_arrived(
    bus: BusUnit,
    rt: BusRuntime,
    sim_time: int,
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
    reason: str,
) -> None:
    for passenger in rt.onboard:
        passenger["arrival_time_s"] = ""
        passenger["duration_s"] = sim_time - int(passenger["board_time_s"])
        passenger["arrived"] = False
        passenger_rows.append(passenger)
    bus_rows.append(
        {
            "bus_id": bus.bus_id,
            "bus_vtype": bus.vtype,
            "trip_seq": rt.trip_seq,
            "pickup_stop_id": bus.pickup_stop_id,
            "shelter_id": bus.shelter_id,
            "board_time_s": rt.trip_board_time,
            "boarded_count": len(rt.onboard),
            "arrive_shelter_time_s": "",
            "alight_count": 0,
            "trip_duration_s": sim_time - rt.trip_board_time,
            "deadhead": len(rt.onboard) == 0,
            "closure_encountered": rt.closure_hit_this_trip,
            "reroute_success": False,
            "terminated": True,
            "termination_reason": reason,
        }
    )
    rt.onboard = []
    rt.trip_seq += 1
    rt.terminated = True


def handle_bus_closure(
    bus: BusUnit,
    rt: BusRuntime,
    applied_edges: set[str],
    sim_time: int,
    net: Any,
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
) -> None:
    """JB-2/JB-3: バス残ルートに閉鎖がある時の迂回／打切り（毎ステップ呼ぶ）。

    閉鎖適用時に走行中だったバスも、乗車後に閉鎖 edge を含む経路を張ったバスも捕捉する。
    迂回を試み、**迂回後も残ルートに閉鎖が残る（迂回路なし）なら当該便を打切り**、
    onboard 客を到着未確定として not_arrived 計上し、バスを撤収する。
    """
    bus_id = bus.bus_id
    if rt.terminated or not applied_edges or bus_id not in traci.vehicle.getIDList():
        return
    try:
        remaining = set(_remaining_route(bus_id))
    except traci.TraCIException:
        return
    if not (remaining & applied_edges):
        return  # 残ルートに閉鎖なし
    rt.closure_hit_this_trip = True
    # SUMOは到達不能なbusStopを設定するとFatal終了することがあるため、
    # 閉鎖edgeを残ルートに含む便は安全側に倒して打ち切る。
    rt.reroute_ok = False
    alight_passengers(
        bus,
        rt,
        sim_time,
        passenger_rows,
        bus_rows,
        terminated=True,
        termination_reason="closure_unreachable",
    )
    rt.terminated = True
    try:
        traci.vehicle.remove(bus_id)
    except traci.TraCIException:
        pass


def step_bus(
    bus: BusUnit,
    rt: BusRuntime,
    queues: dict[str, dict[str, int]],
    stop_meta: dict[str, dict[str, Any]],
    sim_time: int,
    net: Any,
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
    initialized: set[str],
    applied_edges: set[str],
) -> None:
    """1バスの状態機械を1ステップ進める（§2擬似コード）。"""
    bus_id = bus.bus_id
    if rt.terminated:
        return
    if bus_id not in traci.vehicle.getIDList():
        if bus_id not in initialized and sim_time < SIM_END_SEC:
            return
        if rt.onboard:
            mark_onboard_not_arrived(
                bus, rt, sim_time, passenger_rows, bus_rows, reason="despawn"
            )
        else:
            rt.terminated = True
            rt.termination_reason = "despawn"
        return

    # 投入直後：pickup busStop での停車を指示（loaded 後に一度だけ）。
    if bus_id not in initialized:
        try:
            traci.vehicle.setBusStop(bus_id, bus.pickup_stop_id, duration=BOARDING_S)
            initialized.add(bus_id)
        except traci.TraCIException:
            pass
        return

    # 毎ステップ：残ルートに閉鎖が乗っていれば迂回／打切り（JB-2/3）。
    # setRoute で後から閉鎖 edge を含む経路を張った場合もここで捕捉する。
    handle_bus_closure(bus, rt, applied_edges, sim_time, net, passenger_rows, bus_rows)
    if rt.terminated:
        return

    at_pickup = _is_stopped_at(bus_id, bus.pickup_edge)
    at_shelter = _is_stopped_at(bus_id, bus.shelter_edge)

    if rt.phase == "to_pickup" and at_pickup:
        if sim_time > SIM_END_SEC - CYCLE_EST_S:
            rt.terminated = True
            try:
                traci.vehicle.remove(bus_id)
            except traci.TraCIException:
                pass
            return
        rt.phase = "boarding"
        rt.trip_board_time = sim_time
        boarded = board_passengers(bus, rt, queues, stop_meta, sim_time)
        if not boarded and _queue_exhausted(bus, queues):
            # 需要枯渇 → 早期terminate（判断6-3）。空車便を1行記録して撤収。
            alight_passengers(
                bus,
                rt,
                sim_time,
                passenger_rows,
                bus_rows,
                terminated=True,
                termination_reason="queue_exhausted",
            )
            rt.terminated = True
            try:
                traci.vehicle.remove(bus_id)
            except traci.TraCIException:
                pass

    elif rt.phase == "boarding" and not at_pickup:
        # 乗車滞在終了 → shelter へ。changeTarget で閉鎖を回避して動的に経路計算する。
        # 直行路が閉鎖に当たるなら JB-2 遭遇として記録。迂回路も無ければ打切り＋未到着。
        route_edges = _traci_route_edges(bus.pickup_edge, bus.shelter_edge, bus.vtype)
        if not route_edges or (applied_edges and (set(route_edges) & applied_edges)):
            rt.closure_hit_this_trip = True
            rt.reroute_ok = False
            alight_passengers(
                bus,
                rt,
                sim_time,
                passenger_rows,
                bus_rows,
                terminated=True,
                termination_reason="route_unavailable",
            )
            rt.terminated = True
            try:
                traci.vehicle.remove(bus_id)
            except traci.TraCIException:
                pass
            return
        try:
            traci.vehicle.setRoute(bus_id, route_edges)
            traci.vehicle.setBusStop(bus_id, bus.shelter_stop_id, duration=BOARDING_S)
            rt.phase = "to_shelter"
        except traci.TraCIException:
            # shelter へ到達不能（全経路閉鎖）→ 当該便打切り＋onboard客を未到着確定
            rt.reroute_ok = False
            rt.closure_hit_this_trip = True
            alight_passengers(
                bus,
                rt,
                sim_time,
                passenger_rows,
                bus_rows,
                terminated=True,
                termination_reason="route_unavailable",
            )
            rt.terminated = True
            try:
                traci.vehicle.remove(bus_id)
            except traci.TraCIException:
                pass

    elif rt.phase == "to_shelter" and at_shelter:
        rt.phase = "alighting"
        alight_passengers(bus, rt, sim_time, passenger_rows, bus_rows)  # trip_seq += 1

    elif rt.phase == "alighting" and not at_shelter:
        if _queue_exhausted(bus, queues) or sim_time > SIM_END_SEC - CYCLE_EST_S:
            rt.terminated = True  # 早期terminate（判断6-3）/ 時間切れ
            try:
                traci.vehicle.remove(bus_id)
            except traci.TraCIException:
                pass
        else:
            # pickup へ戻る。changeTarget で閉鎖を回避。到達不能なら当該バス撤収。
            route_edges = _traci_route_edges(bus.shelter_edge, bus.pickup_edge, bus.vtype)
            if not route_edges or (applied_edges and (set(route_edges) & applied_edges)):
                rt.terminated = True
                try:
                    traci.vehicle.remove(bus_id)
                except traci.TraCIException:
                    pass
                return
            try:
                traci.vehicle.setRoute(bus_id, route_edges)
                traci.vehicle.setBusStop(bus_id, bus.pickup_stop_id, duration=BOARDING_S)
                rt.phase = "to_pickup"
            except traci.TraCIException:
                rt.terminated = True
                try:
                    traci.vehicle.remove(bus_id)
                except traci.TraCIException:
                    pass


# ---------------------------------------------------------------------------
# 本体ループ
# ---------------------------------------------------------------------------
def run_traci_scenario_b(
    sumocfg: Path,
    non_car_households_total: float = 0.0,
    apply_closures: bool = True,
    route_file: Path | None = None,
    assignments_path: Path | None = None,
    phase: str = "busonly",
    run_id: str | None = None,
    tripinfo_output: Path | None = None,
    fcd_output: Path | None = None,
    archived_outputs: dict[str, str] | None = None,
    sumo_seed: int = DEFAULT_SUMO_SEED,
) -> dict[str, Any]:
    """B-c 本体。バスを投入し6hまで動的往復させ、乗降を会計して3ログを出力する。

    車（private/rescue）の同時走行は sumocfg に route を含めれば同居可能（B-b後）。
    本関数はバス処理と、閉鎖の適用（車＝passenger、バス＝bus）を担う。
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    net = sumolib.net.readNet(str(NET_XML_PATH))
    units = load_bus_units(BUS_PLAN_CSV)
    queues = init_queues(BUS_PLAN_CSV, AGENT_TYPES_CSV)
    stop_meta = stop_meta_from_plan(BUS_PLAN_CSV)
    initial_queue_total = sum(sum(cat.values()) for cat in queues.values())
    closures = load_closures() if apply_closures else []
    run_id = run_id or f"{phase}_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
    started_at = datetime.now()
    planned_vehicles = (
        traci_common.load_planned_vehicles(assignments_path)
        if assignments_path is not None
        else {}
    )
    planned_by_source_edge = traci_common.group_planned_by_source_edge(planned_vehicles)

    runtime: dict[str, BusRuntime] = {bus.bus_id: BusRuntime() for bus in units}
    passenger_rows: list[dict[str, Any]] = []
    bus_rows: list[dict[str, Any]] = []
    initialized: set[str] = set()
    applied_edges: set[str] = set()
    closure_logs: list[dict[str, Any]] = []
    congestion_logs: list[dict[str, Any]] = []
    vehicle_state: dict[str, dict[str, Any]] = {}
    reroute_failed_vehicle_ids: set[str] = set()
    departed_vehicle_ids: set[str] = set()
    blocked_before_depart: dict[str, int] = {}
    closure_index = 0
    last_sim_time = 0

    sumo_binary = resolve_sumo_binary()
    traci.start(build_sumo_command(sumocfg, sumo_binary, sumo_seed))
    inject_buses(units, net)

    try:
        while traci.simulation.getTime() <= SIM_END_SEC and (
            traci.simulation.getMinExpectedNumber() > 0
            or closure_index < len(closures)
            or any(not rt.terminated for rt in runtime.values())
        ):
            traci.simulationStep()
            sim_time = int(traci.simulation.getTime())
            last_sim_time = sim_time
            traci_common.record_departed(sim_time, departed_vehicle_ids, vehicle_state)

            # 閉鎖適用（車＋バス＝JB-1）。バスの迂回/打切り(JB-2/3)は step_bus が
            # 毎ステップ handle_bus_closure を呼ぶため、ここでは適用のみでよい。
            while closure_index < len(closures) and sim_time >= int(
                closures[closure_index]["sim_time_sec"]
            ):
                item = closures[closure_index]
                new_edges = [
                    e for e in item.get("closed_sumo_edge_ids", []) if e not in applied_edges
                ]
                closure_row, failed_ids = traci_common.apply_closure_to_simulation(
                    item=item,
                    new_edges=new_edges,
                    applied_edges=applied_edges,
                    planned_by_source_edge=planned_by_source_edge,
                    departed_vehicle_ids=departed_vehicle_ids,
                    blocked_before_depart=blocked_before_depart,
                    sim_time=sim_time,
                    disallowed_classes=["passenger", "bus"],
                    reroute_exclude_prefixes=("bus_",),
                )
                closure_logs.append(closure_row)
                reroute_failed_vehicle_ids.update(failed_ids)
                closure_index += 1

            traci_common.record_arrived(sim_time, vehicle_state)
            traci_common.update_stop_states(
                sim_time,
                vehicle_state,
                BUS_STOP_SPEED,
                LONG_STOP_THRESHOLD_SEC,
                exclude_prefixes=("bus_",),
            )

            # 各バスの状態機械を進める（handle_bus_closure を内部で毎ステップ実行）
            for bus in units:
                step_bus(
                    bus, runtime[bus.bus_id], queues, stop_meta, sim_time, net,
                    passenger_rows, bus_rows, initialized, applied_edges,
                )

            if sim_time % CONGESTION_LOG_INTERVAL_SEC == 0:
                active_ids = [
                    vehicle_id
                    for vehicle_id in traci.vehicle.getIDList()
                    if not vehicle_id.startswith("bus_")
                ]
                speeds = [traci.vehicle.getSpeed(vehicle_id) for vehicle_id in active_ids]
                congestion_logs.append(
                    {
                        "sim_time_sec": sim_time,
                        "active_vehicle_count": len(active_ids),
                        "mean_speed_mps": round(sum(speeds) / len(speeds), 4) if speeds else "",
                        "stopped_vehicle_count": sum(1 for speed in speeds if speed <= BUS_STOP_SPEED),
                    }
                )
    finally:
        traci.close()

    # 終了時：まだ onboard の客がいれば到着未確定として arrived=False で確定
    for bus in units:
        rt = runtime[bus.bus_id]
        if rt.onboard:
            mark_onboard_not_arrived(
                bus,
                rt,
                last_sim_time or SIM_END_SEC,
                passenger_rows,
                bus_rows,
                reason="sim_end",
            )

    report = settle_stranded_to_rescue(queues, passenger_rows, non_car_households_total)
    vehicle_rows = traci_common.build_vehicle_log_rows(
        planned_vehicles,
        vehicle_state,
        reroute_failed_vehicle_ids,
        blocked_before_depart,
    )
    manifest = {
        "run_id": run_id,
        "phase": phase,
        "started_at": started_at.isoformat(timespec="seconds"),
        "sumocfg": str(sumocfg),
        "sumocfg_content": sumocfg.read_text(encoding="utf-8") if sumocfg.exists() else "",
        "route_file": str(route_file) if route_file else "",
        "route_sha256": traci_common.sha256_file(route_file) if route_file else "",
        "route_vehicle_counts": traci_common.count_route_vehicles(route_file) if route_file else {},
        "assignments": str(assignments_path) if assignments_path else "",
        "apply_closures": apply_closures,
        "sumo_seed": sumo_seed,
        "sim_end_sec": SIM_END_SEC,
        "last_sim_time": last_sim_time,
        "archived_outputs": archived_outputs or {},
    }
    summary = _build_summary(
        units,
        passenger_rows,
        bus_rows,
        report,
        initial_queue_total,
        vehicle_rows,
        closure_logs,
        applied_edges,
        manifest,
    )
    write_bus_outputs(
        passenger_rows,
        bus_rows,
        summary,
        vehicle_rows,
        closure_logs,
        congestion_logs,
        tripinfo_output=tripinfo_output,
        fcd_output=fcd_output,
    )
    return summary


def _build_summary(
    units: list[BusUnit],
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
    report: dict[str, Any],
    initial_queue_total: int,
    vehicle_rows: list[dict[str, Any]],
    closure_logs: list[dict[str, Any]],
    applied_edges: set[str],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    arrived = sum(1 for p in passenger_rows if p.get("arrived"))
    not_arrived = sum(1 for p in passenger_rows if not p.get("arrived"))
    termination_by_reason: dict[str, int] = {}
    for row in bus_rows:
        if not row.get("terminated"):
            continue
        reason = str(row.get("termination_reason") or "unknown")
        termination_by_reason[reason] = termination_by_reason.get(reason, 0) + 1
    vehicle_summary = traci_common.build_traci_summary(
        city_code="08211",
        city_name="常総市",
        scenario="scenario_b",
        rows=vehicle_rows,
        closure_logs=closure_logs,
        applied_edges=applied_edges,
        vehicle_log_rel=str(VEHICLE_LOG_CSV),
        closure_log_rel=str(CLOSURE_LOG_CSV),
        congestion_log_rel=str(CONGESTION_LOG_CSV),
        summary_rel=str(TRACI_SUMMARY_JSON),
        extra={"run_id": manifest["run_id"], "phase": manifest["phase"]},
    )
    return {
        "bus_count": len(units),
        "welfare_bus_count": sum(1 for b in units if b.is_welfare),
        "initial_bus_candidate_total": initial_queue_total,
        "bus_boarded_passengers": len(passenger_rows),
        "bus_arrived_passengers": arrived,
        "bus_not_arrived_passengers": not_arrived,
        "total_trips": len(bus_rows),
        "deadhead_trips": sum(1 for r in bus_rows if r["deadhead"]),
        "terminated_trips": sum(1 for r in bus_rows if r["terminated"]),
        "termination_by_reason": termination_by_reason,
        "closure_encountered_trips": sum(1 for r in bus_rows if r["closure_encountered"]),
        # 二層報告の材料（判断6-2）。分母（全Type3/4）は評価側で車ログと結合。
        "two_layer_report": report,
        # 不変条件 I: 輸送 + 未到着 + 残 == 初期
        "conservation_ok": (
            arrived + not_arrived + report["residual_queue_total"] == initial_queue_total
        ),
        "run_manifest": manifest,
        "vehicle_summary": vehicle_summary,
    }


def write_bus_outputs(
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    vehicle_rows: list[dict[str, Any]],
    closure_logs: list[dict[str, Any]],
    congestion_logs: list[dict[str, Any]],
    tripinfo_output: Path | None,
    fcd_output: Path | None,
) -> None:
    _write_csv(PASSENGER_LOG_CSV, PASSENGER_FIELDS, passenger_rows)
    _write_csv(BUS_LOG_CSV, BUS_LOG_FIELDS, bus_rows)
    traci_common.write_vehicle_log(VEHICLE_LOG_CSV, vehicle_rows)
    _write_csv(
        CLOSURE_LOG_CSV,
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
    _write_csv(
        CONGESTION_LOG_CSV,
        ["sim_time_sec", "active_vehicle_count", "mean_speed_mps", "stopped_vehicle_count"],
        congestion_logs,
    )
    TRACI_SUMMARY_JSON.write_text(
        json.dumps(summary["vehicle_summary"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ended_at = datetime.now()
    summary["run_manifest"]["ended_at"] = ended_at.isoformat(timespec="seconds")
    summary["run_manifest"].update(traci_common.git_state(PROGRAM_DIR, SCRIPT_DIR))
    manifest_paths: dict[str, Path] = {
        "passenger_log": PASSENGER_LOG_CSV,
        "bus_log": BUS_LOG_CSV,
        "vehicle_log": VEHICLE_LOG_CSV,
        "closure_log": CLOSURE_LOG_CSV,
        "congestion_log": CONGESTION_LOG_CSV,
        "traci_summary": TRACI_SUMMARY_JSON,
    }
    for label, key in (
        ("sumocfg", "sumocfg"),
        ("route_file", "route_file"),
        ("assignments", "assignments"),
    ):
        value = summary["run_manifest"].get(key)
        if value:
            manifest_paths[label] = Path(str(value))
    if tripinfo_output is not None:
        manifest_paths["tripinfo"] = tripinfo_output
    if fcd_output is not None:
        manifest_paths["fcd"] = fcd_output
    summary["run_manifest"]["outputs"] = traci_common.file_manifest(
        manifest_paths
    )
    BUS_SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] saved: {PASSENGER_LOG_CSV} ({len(passenger_rows)} passengers)")
    print(f"[INFO] saved: {BUS_LOG_CSV} ({len(bus_rows)} trips)")
    print(f"[INFO] saved: {VEHICLE_LOG_CSV} ({len(vehicle_rows)} vehicles)")
    print(f"[INFO] saved: {BUS_SUMMARY_JSON}")
    print(f"[INFO] saved: {TRACI_SUMMARY_JSON}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    import csv

    # 余分キー（category/welfare_priority 等）を含む行もフィールド順で書く。
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_bus_smoke(n_bus: int, with_closure: bool) -> None:
    """乗降検証スモーク：bus_vtypes/sumocfg を生成し、バスのみで TraCI 実行。

    前提：先に `python p3_bus_scenario.py smoke --buses N` で bus_plan.csv と
    bus_stops.add.xml を生成しておくこと（build_bus_plan の出力を使う）。
    """
    if not BUS_STOPS_ADD_XML.exists() or not BUS_PLAN_CSV.exists():
        raise FileNotFoundError(
            "先に p3_bus_scenario.py smoke で bus_plan.csv / bus_stops.add.xml を生成してください"
        )
    archived_outputs = traci_common.archive_existing_outputs(
        {
            "sumocfg": SMOKE_BUS_SUMOCFG,
            "tripinfo": SMOKE_BUS_TRIPINFO,
            "fcd": SMOKE_BUS_FCD,
            "passenger_log": PASSENGER_LOG_CSV,
            "bus_log": BUS_LOG_CSV,
            "vehicle_log": VEHICLE_LOG_CSV,
            "closure_log": CLOSURE_LOG_CSV,
            "congestion_log": CONGESTION_LOG_CSV,
            "bus_summary": BUS_SUMMARY_JSON,
            "traci_summary": TRACI_SUMMARY_JSON,
        },
        RESULTS_DIR / "archive_runs",
        "scenario_b_busonly",
    )
    write_bus_vtypes_add()
    write_bus_only_sumocfg()
    summary = run_traci_scenario_b(
        SMOKE_BUS_SUMOCFG,
        non_car_households_total=0.0,
        apply_closures=with_closure,
        phase="busonly",
        tripinfo_output=SMOKE_BUS_TRIPINFO,
        fcd_output=SMOKE_BUS_FCD,
        archived_outputs=archived_outputs,
    )
    print("\n=== 乗降検証スモーク結果 ===")
    print(f"  投入バス {summary['bus_count']} 台／輸送 {summary['bus_arrived_passengers']} 人"
          f"／往復 {summary['total_trips']}（空車 {summary['deadhead_trips']}）")
    print(f"  人数保存 (輸送+残=初期): {summary['conservation_ok']}")


def read_non_car_households_total() -> float:
    rescue_od_path = DERIVED_DIR / "rescue_od.csv"
    if not rescue_od_path.exists():
        return 0.0
    import pandas as pd

    rescue_od = pd.read_csv(rescue_od_path)
    return float(rescue_od["non_car_households"].sum())


def assignments_for_phase(phase: str) -> Path:
    if phase == "measure":
        return DERIVED_DIR / "scenario_a_vehicle_assignments.csv"
    if phase == "final":
        return DERIVED_DIR / "scenario_b_vehicle_assignments.csv"
    raise ValueError(f"unknown phase: {phase}")


def validate_route_for_phase(route_file: Path, phase: str, assignments_path: Path) -> None:
    expected_name = "scenario_a.rou.xml" if phase == "measure" else "scenario_b.rou.xml"
    if route_file.name != expected_name:
        raise ValueError(f"{phase} phase requires {expected_name}, got {route_file.name}")
    if not route_file.exists():
        raise FileNotFoundError(route_file)
    if not assignments_path.exists():
        raise FileNotFoundError(assignments_path)
    route_counts = traci_common.count_route_vehicles(route_file)
    planned_count = len(traci_common.load_planned_vehicles(assignments_path))
    if int(route_counts["total"]) != planned_count:
        raise ValueError(
            f"route/assignments vehicle count mismatch: route={route_counts['total']} "
            f"assignments={planned_count} ({route_file}, {assignments_path})"
        )


def run_bus_for_scenario(
    route_file: Path,
    phase: str,
    apply_closures: bool,
    sumo_seed: int = DEFAULT_SUMO_SEED,
) -> None:
    if not BUS_STOPS_ADD_XML.exists() or not BUS_PLAN_CSV.exists():
        raise FileNotFoundError(
            "先に p3_bus_scenario.py smoke で bus_plan.csv / bus_stops.add.xml を生成してください"
        )
    assignments_path = assignments_for_phase(phase)
    validate_route_for_phase(route_file, phase, assignments_path)
    write_bus_vtypes_add()
    sumocfg = SCENARIOS_DIR / "scenario_b.sumocfg"
    tripinfo = RESULTS_DIR / "scenario_b_tripinfo.xml"
    fcd = RESULTS_DIR / "scenario_b_fcd.xml"
    archived_outputs = traci_common.archive_existing_outputs(
        {
            "sumocfg": sumocfg,
            "tripinfo": tripinfo,
            "fcd": fcd,
            "passenger_log": PASSENGER_LOG_CSV,
            "bus_log": BUS_LOG_CSV,
            "vehicle_log": VEHICLE_LOG_CSV,
            "closure_log": CLOSURE_LOG_CSV,
            "congestion_log": CONGESTION_LOG_CSV,
            "bus_summary": BUS_SUMMARY_JSON,
            "traci_summary": TRACI_SUMMARY_JSON,
        },
        RESULTS_DIR / "archive_runs",
        f"scenario_b_{phase}",
        copy_paths={"route_file": route_file},
    )
    write_bus_sumocfg(sumocfg, route_file=route_file, tripinfo_output=tripinfo, fcd_output=fcd)
    summary = run_traci_scenario_b(
        sumocfg,
        non_car_households_total=read_non_car_households_total(),
        apply_closures=apply_closures,
        route_file=route_file,
        assignments_path=assignments_path,
        phase=phase,
        tripinfo_output=tripinfo,
        fcd_output=fcd,
        archived_outputs=archived_outputs,
        sumo_seed=sumo_seed,
    )
    print("\n=== シナリオB TraCI結果 ===")
    print(f"  phase: {phase}")
    print(f"  route_file: {route_file}")
    print(f"  投入バス {summary['bus_count']} 台／輸送 {summary['bus_arrived_passengers']} 人"
          f"／往復 {summary['total_trips']}（空車 {summary['deadhead_trips']}）")
    print(f"  人数保存 (輸送+残=初期): {summary['conservation_ok']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("smoke-bus", help="バスのみの乗降検証スモーク（SUMO実行）")
    p.add_argument("--buses", type=int, default=1)
    p.add_argument("--closure", action="store_true", help="閉鎖タイムラインを適用しJB-2を検証")
    p.add_argument("--city-code", help="地域別SUMO出力を対象にする場合の市区町村コード（例: 08211）")
    p_run = sub.add_parser("run-bus", help="車両routeとバスTraCIを同時実行する")
    p_run.add_argument("--city-code", help="地域別SUMO出力を対象にする場合の市区町村コード（例: 08211）")
    p_run.add_argument(
        "--route-file",
        type=Path,
        required=True,
        help="同時走行させるroute XML。measure=scenario_a.rou.xml / final=scenario_b.rou.xml",
    )
    p_run.add_argument("--phase", choices=["measure", "final"], required=True)
    p_run.add_argument("--sumo-seed", type=int, default=DEFAULT_SUMO_SEED)
    p_run.add_argument("--no-closure", action="store_true", help="閉鎖タイムラインを適用しない")
    args = parser.parse_args()
    if args.command == "smoke-bus":
        configure_paths(args.city_code)
        run_bus_smoke(args.buses, args.closure)
    elif args.command == "run-bus":
        configure_paths(args.city_code)
        route_file = args.route_file
        if not route_file.is_absolute():
            route_file = (PROGRAM_DIR / route_file).resolve()
        run_bus_for_scenario(
            route_file,
            phase=args.phase,
            apply_closures=not args.no_closure,
            sumo_seed=args.sumo_seed,
        )


if __name__ == "__main__":
    main()
