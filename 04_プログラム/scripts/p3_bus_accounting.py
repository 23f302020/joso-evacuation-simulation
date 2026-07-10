"""Phase 3 B系: バス乗降会計のコアロジック（TraCI 非依存・単体テスト可能）。

`_Bc実装ブループリント_fable5.md` §1〜3 と判断確定（`_判断結果_2026-07-07.md` §6）に基づく。
本モジュールは **traci を import しない**（純粋なデータ変換のみ）ため、SUMO 実行環境が
無くても pandas だけで単体テストできる。TraCI ループ本体（inject_bus・
handle_bus_closure・run_traci_scenario_b）は `p2_traci_bus.py` 側でこれを利用する。

確定した判断（本モジュールに効くもの）：
- 6-1: queue は plan/候補データから確定（本モジュールで整数確定）。
- 6-5: 行動困難者(type3_mobility_limited)候補は**福祉優先枠**で乗車（type4に次ぐ優先）。
- JB-4: バス車両は逃げ遅れに数えない（人数は passenger 行でのみ数える）。
- 乗降は R3 方式（person を載せずログ側で会計）。福祉車は要支援層を優先乗車。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

import config


@dataclass(frozen=True)
class BusUnit:
    """1台のバスの静的属性（ループ中に変わらない）。"""

    bus_id: str
    vtype: str  # "bus_standard" | "bus_welfare"
    capacity: int  # 8 | 4
    pickup_stop_id: str
    pickup_edge: str
    shelter_id: str
    shelter_edge: str
    is_welfare: bool
    # shelter 側 busStop id。既存テストの後方互換のため末尾・デフォルト付き。
    shelter_stop_id: str = ""


@dataclass
class BusRuntime:
    """1台のバスの可変状態（ループ中に更新）。"""

    trip_seq: int = 0
    phase: str = "to_pickup"  # to_pickup | boarding | to_shelter | alighting
    onboard: list[dict[str, Any]] = field(default_factory=list)
    trip_board_time: int = 0
    boarding_started: int = -1  # boarding 開始時刻（乗車滞在の計測用）
    alighting_started: int = -1
    closure_hit_this_trip: bool = False
    reroute_ok: bool = True
    terminated: bool = False


def load_bus_units(bus_plan_path: Path) -> list[BusUnit]:
    """build_bus_plan の出力(bus_plan.csv)を BusUnit リストへ。

    福祉車の割当（is_welfare）は build_bus_plan 側で確定済み（type4 最大の停）。
    """
    df = pd.read_csv(bus_plan_path, dtype={"KEY_CODE": str})
    units: list[BusUnit] = []
    for _, row in df.iterrows():
        is_welfare = str(row["bus_vtype"]) == "bus_welfare"
        units.append(
            BusUnit(
                bus_id=str(row["bus_id"]),
                vtype=str(row["bus_vtype"]),
                capacity=int(config.BUS_CAPACITY_WELFARE if is_welfare else config.BUS_CAPACITY_STD),
                pickup_stop_id=str(row["pickup_stop_id"]),
                pickup_edge=str(row["pickup_edge"]),
                shelter_id=str(row["shelter_id"]),
                # 新列。build_bus_plan 出力には常に存在するが、無い場合は shelter_id から補う。
                shelter_stop_id=str(row.get("shelter_stop_id", f"bs_shelter_{row['shelter_id']}")),
                shelter_edge=str(row["shelter_edge"]),
                is_welfare=is_welfare,
            )
        )
    return units


def stop_meta_from_plan(bus_plan_path: Path) -> dict[str, dict[str, Any]]:
    """stop_id → {origin_id, KEY_CODE, shelter_id}。passenger 行の属性付与に使う。"""
    df = pd.read_csv(bus_plan_path, dtype={"KEY_CODE": str})
    meta: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        meta[str(row["pickup_stop_id"])] = {
            "origin_id": str(row["origin_id"]),
            "KEY_CODE": str(row["KEY_CODE"]),
            "shelter_id": str(row["shelter_id"]),
        }
    return meta


def init_queues(bus_plan_path: Path, agent_types_path: Path) -> dict[str, dict[str, int]]:
    """queue[stop_id] = {"type4": int, "type3_mob": int, "type3": int}。

    - type4      = type4_no_car_elderly_pop（要支援・福祉最優先）
    - type3_mob  = type3_mobility_limited_candidate_pop（行動困難＝福祉優先枠・判断6-5）
    - type3      = type3_no_car_non_elderly_pop − type3_mob（一般Type3。mobは type3_no_car の
                   部分集合＝bus_candidate_population = type3_no_car + type4 で整合）

    値は各メッシュで整数（人口カウント）。念のため非負整数へ丸める（6-1: plan時に確定）。
    """
    plan = pd.read_csv(bus_plan_path, dtype={"KEY_CODE": str})
    types = pd.read_csv(agent_types_path, dtype={"KEY_CODE": str})
    type_cols = [
        "origin_id",
        "type3_no_car_non_elderly_pop",
        "type4_no_car_elderly_pop",
        "type3_mobility_limited_candidate_pop",
    ]
    merged = plan[["origin_id", "pickup_stop_id"]].merge(
        types[type_cols], on="origin_id", how="left"
    )

    queues: dict[str, dict[str, int]] = {}
    for _, row in merged.iterrows():
        t4 = max(0, int(round(float(row["type4_no_car_elderly_pop"]))))
        t3_mob = max(0, int(round(float(row["type3_mobility_limited_candidate_pop"]))))
        t3_all = max(0, int(round(float(row["type3_no_car_non_elderly_pop"]))))
        t3_reg = max(0, t3_all - t3_mob)  # mob は type3_no_car の部分集合
        queues[str(row["pickup_stop_id"])] = {
            "type4": t4,
            "type3_mob": t3_mob,
            "type3": t3_reg,
        }
    return queues


def _person_rows_for_board(
    bus: BusUnit,
    rt: BusRuntime,
    take: dict[str, int],
    stop_meta: dict[str, dict[str, Any]],
    sim_time: int,
) -> list[dict[str, Any]]:
    """乗車確定した人数(take: カテゴリ→人数)から passenger 行を生成する。

    person_type は 3(type3・type3_mob) / 4(type4)。mob は要支援だが Type3 なので person_type=3、
    ただし welfare_priority フラグで由来を残す。
    """
    meta = stop_meta.get(bus.pickup_stop_id, {})
    rows: list[dict[str, Any]] = []
    seq = 0
    for category, ptype, welfare_priority in (
        ("type4", 4, True),
        ("type3_mob", 3, True),
        ("type3", 3, False),
    ):
        for _ in range(int(take.get(category, 0))):
            seq += 1
            rows.append(
                {
                    "passenger_id": f"pax_{bus.bus_id}_{rt.trip_seq}_{seq:03d}",
                    "origin_id": meta.get("origin_id", ""),
                    "KEY_CODE": meta.get("KEY_CODE", ""),
                    "person_type": ptype,
                    "category": category,
                    "welfare_priority": welfare_priority,
                    "bus_id": bus.bus_id,
                    "bus_vtype": bus.vtype,
                    "trip_seq": rt.trip_seq,
                    "board_time_s": sim_time,
                    "shelter_id": bus.shelter_id,
                    "arrival_time_s": "",
                    "duration_s": "",
                    "arrived": False,
                }
            )
    return rows


def board_passengers(
    bus: BusUnit,
    rt: BusRuntime,
    queues: dict[str, dict[str, int]],
    stop_meta: dict[str, dict[str, Any]],
    sim_time: int,
) -> list[dict[str, Any]]:
    """pickup 停車時：容量まで乗車させ、passenger 行を返す（queue を減算）。

    乗車優先順（判断6-5）：
      福祉車 → type4 → type3_mob → type3
      標準車 → type3 → type3_mob → type4（一般層を優先、余りで要支援も運ぶ）
    """
    cap = int(bus.capacity)
    q = queues[bus.pickup_stop_id]
    order = (
        ["type4", "type3_mob", "type3"]
        if bus.is_welfare
        else ["type3", "type3_mob", "type4"]
    )
    take: dict[str, int] = {}
    remaining = cap
    for category in order:
        n = min(remaining, int(q.get(category, 0)))
        take[category] = n
        q[category] -= n
        remaining -= n
        assert q[category] >= 0, f"queue負値: {bus.pickup_stop_id}/{category}"

    boarded = _person_rows_for_board(bus, rt, take, stop_meta, sim_time)
    rt.onboard.extend(boarded)
    assert len(boarded) <= cap, "容量超過乗車"
    return boarded


def alight_passengers(
    bus: BusUnit,
    rt: BusRuntime,
    sim_time: int,
    passenger_rows: list[dict[str, Any]],
    bus_rows: list[dict[str, Any]],
    terminated: bool = False,
    termination_reason: str = "",
) -> None:
    """shelter 停車時（または打切り送届時）：onboard 全員を降車確定し行を確定する。

    trip_seq を +1 する。deadhead（乗車0）も1往復として記録する。
    """
    for passenger in rt.onboard:
        passenger["arrival_time_s"] = "" if terminated else sim_time
        passenger["duration_s"] = sim_time - int(passenger["board_time_s"])
        passenger["arrived"] = not terminated
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
            "arrive_shelter_time_s": "" if terminated else sim_time,
            "alight_count": 0 if terminated else len(rt.onboard),
            "trip_duration_s": sim_time - rt.trip_board_time,
            "deadhead": len(rt.onboard) == 0,
            "closure_encountered": rt.closure_hit_this_trip,
            "reroute_success": rt.reroute_ok,
            "terminated": terminated,
            "termination_reason": termination_reason,
        }
    )
    rt.onboard = []
    rt.trip_seq += 1
    rt.closure_hit_this_trip = False
    rt.reroute_ok = True


def queue_total(queues: dict[str, dict[str, int]]) -> int:
    """全停・全カテゴリの残 queue 合計（＝バスに乗れていない Type3/4 人数）。"""
    return sum(sum(cat.values()) for cat in queues.values())


def settle_stranded_to_rescue(
    queues: dict[str, dict[str, int]],
    passenger_rows: list[dict[str, Any]],
    non_car_households_total: float,
) -> dict[str, Any]:
    """JB-5：終了時の残 queue と二層報告の材料を計算する（判断6-2＝完了率2種併記）。

    - bus_transport_total : バスが避難所へ運び切った人数（passenger の arrived==True）。
    - residual_queue_total: バスに乗れず残った Type3/4 人数（救出走行で救済される想定）。
    - rescue_after_bus    : バス実輸送を差し引いた救出走行の必要台数
                            （P3-IMPL-0 §2 会計。B4 の削減が妥当かの検算材料）。
    完了率そのもの（分母＝全Type3/4）は車側 vehicle_log と結合して評価側で算出するため、
    ここでは材料（バス寄与）だけを返す。
    """
    bus_transport_total = sum(1 for p in passenger_rows if p.get("arrived"))
    residual_total = queue_total(queues)
    k = float(getattr(config, "RESCUE_PER_VEHICLE_K", config.HOUSEHOLD_SIZE))
    rescue_rate = float(getattr(config, "RESCUE_RATE_R", 1.0))
    rescue_after_bus_raw = non_car_households_total * rescue_rate - bus_transport_total / k
    return {
        "bus_transport_total": bus_transport_total,
        "residual_queue_total": residual_total,
        "residual_queue_by_stop": {
            stop: dict(cat) for stop, cat in queues.items()
        },
        "rescue_after_bus_vehicles_raw": round(rescue_after_bus_raw, 3),
    }
