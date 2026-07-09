"""p3_bus_accounting.py の pytest 単体テスト。

正本：`交通シミュレーション調査/_Bc実装ブループリント_fable5.md` §3（乗降会計）・
§5（品質担保・不変条件I1〜I8・乗降検証スモーク）。

対象モジュールは traci 非依存・pandas のみで完結するため、CSV フィクスチャ
（tmp_path 上に bus_plan.csv / agent_types.csv 相当を作成）または直接
dict/DataFrame 経由で board_passengers / alight_passengers / init_queues /
settle_stranded_to_rescue を検証する。

注意：本テストファイルは検証専用。p3_bus_accounting.py 本体は編集しない
（不具合を見つけても修正せずコメント/報告に留める）。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

import p3_bus_accounting as acc


# ---------------------------------------------------------------------------
# 共通フィクスチャ・ヘルパー
# ---------------------------------------------------------------------------

BUS_PLAN_FIELDS = [
    "bus_id",
    "bus_vtype",
    "origin_id",
    "KEY_CODE",
    "pickup_edge",
    "pickup_stop_id",
    "shelter_id",
    "shelter_edge",
]

AGENT_TYPES_FIELDS = [
    "origin_id",
    "KEY_CODE",
    "type3_no_car_non_elderly_pop",
    "type4_no_car_elderly_pop",
    "type3_mobility_limited_candidate_pop",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def make_bus_plan_csv(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    filename: str = "bus_plan.csv",
) -> Path:
    path = tmp_path / filename
    write_csv(path, BUS_PLAN_FIELDS, rows)
    return path


def make_agent_types_csv(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    filename: str = "agent_types.csv",
) -> Path:
    path = tmp_path / filename
    write_csv(path, AGENT_TYPES_FIELDS, rows)
    return path


def make_bus_unit(
    bus_id: str = "bus_std_1",
    vtype: str = "bus_standard",
    capacity: int | None = None,
    pickup_stop_id: str = "bs_1",
    shelter_id: str = "shelter_1",
) -> acc.BusUnit:
    is_welfare = vtype == "bus_welfare"
    if capacity is None:
        capacity = acc.config.BUS_CAPACITY_WELFARE if is_welfare else acc.config.BUS_CAPACITY_STD
    return acc.BusUnit(
        bus_id=bus_id,
        vtype=vtype,
        capacity=capacity,
        pickup_stop_id=pickup_stop_id,
        pickup_edge="edge_pickup",
        shelter_id=shelter_id,
        shelter_edge="edge_shelter",
        is_welfare=is_welfare,
    )


def make_stop_meta(stop_id: str = "bs_1") -> dict[str, dict[str, Any]]:
    return {stop_id: {"origin_id": "origin_1", "KEY_CODE": "08211001", "shelter_id": "shelter_1"}}


# ---------------------------------------------------------------------------
# init_queues
# ---------------------------------------------------------------------------


class TestInitQueues:
    def test_basic_split_type3_excludes_mob(self, tmp_path: Path) -> None:
        """type3 = type3_no_car_non_elderly_pop - type3_mob（mobはtype3_no_carの部分集合）。"""
        bus_plan = make_bus_plan_csv(
            tmp_path,
            [
                {
                    "bus_id": "bus_std_1",
                    "bus_vtype": "bus_standard",
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "pickup_edge": "e1",
                    "pickup_stop_id": "bs_1",
                    "shelter_id": "shelter_1",
                    "shelter_edge": "e_shelter",
                }
            ],
        )
        agent_types = make_agent_types_csv(
            tmp_path,
            [
                {
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "type3_no_car_non_elderly_pop": 20,
                    "type4_no_car_elderly_pop": 5,
                    "type3_mobility_limited_candidate_pop": 6,
                }
            ],
        )
        queues = acc.init_queues(bus_plan, agent_types)
        assert queues["bs_1"] == {"type4": 5, "type3_mob": 6, "type3": 14}

    def test_rounds_and_clamps_non_negative(self, tmp_path: Path) -> None:
        """負値・非整数はround後max(0,...)でクランプされる（6-1）。"""
        bus_plan = make_bus_plan_csv(
            tmp_path,
            [
                {
                    "bus_id": "bus_std_1",
                    "bus_vtype": "bus_standard",
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "pickup_edge": "e1",
                    "pickup_stop_id": "bs_1",
                    "shelter_id": "shelter_1",
                    "shelter_edge": "e_shelter",
                }
            ],
        )
        agent_types = make_agent_types_csv(
            tmp_path,
            [
                {
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "type3_no_car_non_elderly_pop": -3.4,
                    "type4_no_car_elderly_pop": 2.6,
                    "type3_mobility_limited_candidate_pop": 0,
                }
            ],
        )
        queues = acc.init_queues(bus_plan, agent_types)
        # -3.4 -> round(-3.4) = -3 -> max(0, -3) = 0 ; 2.6 -> round -> 3
        assert queues["bs_1"]["type3"] == 0
        assert queues["bs_1"]["type4"] == 3
        assert queues["bs_1"]["type3_mob"] == 0

    def test_mob_greater_than_type3_all_produces_negative_type3_uncla_mped(
        self, tmp_path: Path
    ) -> None:
        """異常値：type3_mob > type3_no_car_non_elderly_pop の場合、
        t3_reg = max(0, t3_all - t3_mob) でtype3は0にクランプされる想定。
        本テストで実装の実際の挙動を確認する（不具合があればここで検出）。
        """
        bus_plan = make_bus_plan_csv(
            tmp_path,
            [
                {
                    "bus_id": "bus_std_1",
                    "bus_vtype": "bus_standard",
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "pickup_edge": "e1",
                    "pickup_stop_id": "bs_1",
                    "shelter_id": "shelter_1",
                    "shelter_edge": "e_shelter",
                }
            ],
        )
        agent_types = make_agent_types_csv(
            tmp_path,
            [
                {
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "type3_no_car_non_elderly_pop": 5,
                    "type4_no_car_elderly_pop": 0,
                    "type3_mobility_limited_candidate_pop": 9,  # mob > type3_all（異常値）
                }
            ],
        )
        queues = acc.init_queues(bus_plan, agent_types)
        # t3_reg = max(0, 5 - 9) = 0 （クランプされ負値にはならない）
        assert queues["bs_1"]["type3"] == 0
        assert queues["bs_1"]["type3_mob"] == 9
        # 各カテゴリ非負であること（I2の初期化版）
        assert all(v >= 0 for v in queues["bs_1"].values())

    def test_multiple_stops_sum_matches_source(self, tmp_path: Path) -> None:
        """I5: 整数化後のqueue合計が元データ（丸め・クランプ前提込み）と一致する。"""
        bus_plan = make_bus_plan_csv(
            tmp_path,
            [
                {
                    "bus_id": "bus_std_1",
                    "bus_vtype": "bus_standard",
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "pickup_edge": "e1",
                    "pickup_stop_id": "bs_1",
                    "shelter_id": "shelter_1",
                    "shelter_edge": "e_shelter",
                },
                {
                    "bus_id": "bus_std_2",
                    "bus_vtype": "bus_standard",
                    "origin_id": "origin_2",
                    "KEY_CODE": "08211002",
                    "pickup_edge": "e2",
                    "pickup_stop_id": "bs_2",
                    "shelter_id": "shelter_1",
                    "shelter_edge": "e_shelter",
                },
            ],
        )
        agent_types = make_agent_types_csv(
            tmp_path,
            [
                {
                    "origin_id": "origin_1",
                    "KEY_CODE": "08211001",
                    "type3_no_car_non_elderly_pop": 10,
                    "type4_no_car_elderly_pop": 3,
                    "type3_mobility_limited_candidate_pop": 2,
                },
                {
                    "origin_id": "origin_2",
                    "KEY_CODE": "08211002",
                    "type3_no_car_non_elderly_pop": 7,
                    "type4_no_car_elderly_pop": 1,
                    "type3_mobility_limited_candidate_pop": 0,
                },
            ],
        )
        queues = acc.init_queues(bus_plan, agent_types)
        assert acc.queue_total(queues) == (10 + 3) + (7 + 1)


# ---------------------------------------------------------------------------
# board_passengers: 優先順位・容量境界
# ---------------------------------------------------------------------------


class TestBoardPassengersPriority:
    def test_welfare_bus_prioritizes_type4_then_mob_then_type3(self) -> None:
        """判断6-5：福祉車 → type4 → type3_mob → type3。"""
        bus = make_bus_unit(vtype="bus_welfare", capacity=4)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 2, "type3_mob": 5, "type3": 5}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert len(boarded) == 4
        categories = [p["category"] for p in boarded]
        # type4を2人使い切り、残り2枠をtype3_mobで埋める
        assert categories.count("type4") == 2
        assert categories.count("type3_mob") == 2
        assert categories.count("type3") == 0
        assert queues["bs_1"] == {"type4": 0, "type3_mob": 3, "type3": 5}

    def test_standard_bus_prioritizes_type3_then_mob_then_type4(self) -> None:
        """判断6-5：標準車 → type3 → type3_mob → type4。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 5, "type3_mob": 5, "type3": 5}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert len(boarded) == 8
        categories = [p["category"] for p in boarded]
        assert categories.count("type3") == 5
        assert categories.count("type3_mob") == 3
        assert categories.count("type4") == 0
        assert queues["bs_1"] == {"type4": 5, "type3_mob": 2, "type3": 0}

    def test_person_type_mapping_type3_mob_is_person_type_3(self) -> None:
        """person_type: type3/type3_mob→3, type4→4。mobはwelfare_priority=Trueで由来を残す。"""
        bus = make_bus_unit(vtype="bus_welfare", capacity=4)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 1, "type3_mob": 3, "type3": 0}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        type4_rows = [p for p in boarded if p["category"] == "type4"]
        mob_rows = [p for p in boarded if p["category"] == "type3_mob"]
        assert all(p["person_type"] == 4 for p in type4_rows)
        assert all(p["welfare_priority"] is True for p in type4_rows)
        assert all(p["person_type"] == 3 for p in mob_rows)
        assert all(p["welfare_priority"] is True for p in mob_rows)

    def test_capacity_not_exceeded_when_demand_exceeds_capacity(self) -> None:
        """容量超過需要：需要 > capacity でも乗車人数はcapacity以下。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 100, "type3_mob": 100, "type3": 100}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert len(boarded) == 8
        assert acc.queue_total(queues) == 292  # 300 - 8

    def test_zero_queue_at_stop_produces_deadhead_board(self) -> None:
        """queue=0の停：乗車0人（board側）。alightでdeadhead判定されることは別テストで確認。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 0}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert boarded == []
        assert queues["bs_1"] == {"type4": 0, "type3_mob": 0, "type3": 0}

    def test_welfare_zero_demand_stop(self) -> None:
        """福祉0人の停：福祉車がtype4=0の停に来ても他カテゴリで埋める。"""
        bus = make_bus_unit(vtype="bus_welfare", capacity=4)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 10}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert len(boarded) == 4
        assert all(p["category"] == "type3" for p in boarded)
        assert queues["bs_1"]["type3"] == 6

    def test_exact_capacity_match_empties_queue(self) -> None:
        """queue<capacity: ちょうど1往復で完了（queueが空になる）。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 5}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        assert len(boarded) == 5
        assert queues["bs_1"] == {"type4": 0, "type3_mob": 0, "type3": 0}

    def test_passenger_id_unique_across_multiple_boardings(self) -> None:
        """I3: 複数回の乗車を跨いでpassenger_idが一意であること。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 20}}
        stop_meta = make_stop_meta()

        all_ids: list[str] = []
        bus_rows: list[dict[str, Any]] = []
        passenger_rows: list[dict[str, Any]] = []
        for trip in range(3):
            boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=trip * 1000)
            all_ids.extend(p["passenger_id"] for p in boarded)
            acc.alight_passengers(bus, rt, trip * 1000 + 500, passenger_rows, bus_rows)

        assert len(all_ids) == len(set(all_ids))
        assert len(all_ids) == 20  # 8 + 8 + 4


# ---------------------------------------------------------------------------
# alight_passengers
# ---------------------------------------------------------------------------


class TestAlightPassengers:
    def test_duration_equals_arrival_minus_board(self) -> None:
        """I8: duration_s == arrival_time_s - board_time_s（全乗客）。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 5}}
        stop_meta = make_stop_meta()
        rt.trip_board_time = 100
        acc.board_passengers(bus, rt, queues, stop_meta, sim_time=100)

        passenger_rows: list[dict[str, Any]] = []
        bus_rows: list[dict[str, Any]] = []
        acc.alight_passengers(bus, rt, sim_time=730, passenger_rows=passenger_rows, bus_rows=bus_rows)

        assert len(passenger_rows) == 5
        for p in passenger_rows:
            assert p["arrived"] is True
            assert p["duration_s"] == p["arrival_time_s"] - p["board_time_s"]
            assert p["duration_s"] == 730 - 100

    def test_deadhead_trip_still_advances_trip_seq_and_logs_bus_row(self) -> None:
        """deadhead（乗車0）でもtrip_seqが進み、bus_log行が出る。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 0}}
        stop_meta = make_stop_meta()
        acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        passenger_rows: list[dict[str, Any]] = []
        bus_rows: list[dict[str, Any]] = []
        assert rt.trip_seq == 0
        acc.alight_passengers(bus, rt, sim_time=600, passenger_rows=passenger_rows, bus_rows=bus_rows)

        assert rt.trip_seq == 1
        assert len(bus_rows) == 1
        assert bus_rows[0]["deadhead"] is True
        assert bus_rows[0]["boarded_count"] == 0
        assert bus_rows[0]["alight_count"] == 0
        assert passenger_rows == []

    def test_onboard_reset_after_alight(self) -> None:
        """降車後はonboardが空になる（次のtripに引き継がない）。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 3}}
        stop_meta = make_stop_meta()
        acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)
        assert len(rt.onboard) == 3

        acc.alight_passengers(bus, rt, sim_time=500, passenger_rows=[], bus_rows=[])
        assert rt.onboard == []

    def test_terminated_flag_propagates_to_bus_row(self) -> None:
        """打切り送届（JB-2）: terminated=Trueがbus_rowsに反映される。"""
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 3}}
        stop_meta = make_stop_meta()
        acc.board_passengers(bus, rt, queues, stop_meta, sim_time=0)

        bus_rows: list[dict[str, Any]] = []
        acc.alight_passengers(
            bus, rt, sim_time=500, passenger_rows=[], bus_rows=bus_rows, terminated=True
        )
        assert bus_rows[0]["terminated"] is True


# ---------------------------------------------------------------------------
# 乗降検証スモーク（ブループリント §5「Sonnetが実行する乗降検証スモークテスト設計」）
# ---------------------------------------------------------------------------


class TestBoardingSmoke:
    """最小構成：バス1台(standard, capacity=8)、1停、1避難所、queue初期={type3:20}。
    20人 → 8,8,4 の3往復で運び切り、4往復目以降はdeadhead。
    """

    def _run_trips(self, n_trips: int, board_interval_s: int = 1014):
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 20}}
        stop_meta = make_stop_meta()

        passenger_rows: list[dict[str, Any]] = []
        bus_rows: list[dict[str, Any]] = []
        sim_time = 0
        for _ in range(n_trips):
            rt.trip_board_time = sim_time
            acc.board_passengers(bus, rt, queues, stop_meta, sim_time=sim_time)
            sim_time += board_interval_s
            acc.alight_passengers(bus, rt, sim_time, passenger_rows, bus_rows)
            sim_time += board_interval_s
        return queues, passenger_rows, bus_rows

    def test_three_trips_clear_20_person_queue(self) -> None:
        queues, passenger_rows, bus_rows = self._run_trips(3)

        assert [row["boarded_count"] for row in bus_rows] == [8, 8, 4]
        assert acc.queue_total(queues) == 0
        assert len(passenger_rows) == 20
        assert all(p["arrived"] for p in passenger_rows)
        assert all(p["person_type"] == 3 for p in passenger_rows)
        assert len({p["passenger_id"] for p in passenger_rows}) == 20

    def test_fourth_trip_onward_is_deadhead(self) -> None:
        queues, passenger_rows, bus_rows = self._run_trips(5)

        assert [row["deadhead"] for row in bus_rows] == [False, False, False, True, True]
        # I1: Σboarded(=alight, 全員終了時到着) + Σ残queue = Σ初期queue(20)
        assert sum(row["boarded_count"] for row in bus_rows) + acc.queue_total(queues) == 20

    def test_invariant_i1_boarded_equals_alight_plus_residual(self) -> None:
        """I1: Σboarded = Σalight + Σonboard(終了時) + Σ送届(打切り)。
        本スモークでは打切り無し・終了時onboardは0（全便alight済み）なので
        Σboarded == Σalight が成立する。
        """
        _queues, passenger_rows, bus_rows = self._run_trips(3)
        total_boarded = sum(row["boarded_count"] for row in bus_rows)
        total_alight = sum(row["alight_count"] for row in bus_rows)
        assert total_boarded == total_alight == len(passenger_rows) == 20


# ---------------------------------------------------------------------------
# 境界ケース：sim終了直前の乗車（arrival付与前に打切り＝arrived==False）
# ---------------------------------------------------------------------------


class TestEndOfSimulationBoundary:
    def test_boarded_but_not_alighted_before_sim_end_is_not_arrived(self) -> None:
        """終了直前に乗車したがalight_passengersが呼ばれない場合、
        onboardのpassenger行はarrived==Falseのまま（passenger_rowsに追加されない）
        ＝逃げ遅れ計上される設計であることを確認する。
        """
        bus = make_bus_unit(vtype="bus_standard", capacity=8)
        rt = acc.BusRuntime()
        queues = {"bs_1": {"type4": 0, "type3_mob": 0, "type3": 5}}
        stop_meta = make_stop_meta()

        boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=21000)
        # sim終了(21600s)までにshelter到着せず、alight_passengersが呼ばれない想定
        assert all(p["arrived"] is False for p in boarded)
        assert all(p["arrival_time_s"] == "" for p in boarded)
        assert rt.onboard == boarded


# ---------------------------------------------------------------------------
# settle_stranded_to_rescue（I6・二層報告材料）
# ---------------------------------------------------------------------------


class TestSettleStrandedToRescue:
    def test_bus_transport_total_counts_only_arrived(self) -> None:
        queues = {"bs_1": {"type4": 1, "type3_mob": 2, "type3": 3}}
        passenger_rows = [
            {"arrived": True},
            {"arrived": True},
            {"arrived": False},
        ]
        result = acc.settle_stranded_to_rescue(queues, passenger_rows, non_car_households_total=100.0)

        assert result["bus_transport_total"] == 2
        assert result["residual_queue_total"] == 6
        assert result["residual_queue_by_stop"] == {"bs_1": {"type4": 1, "type3_mob": 2, "type3": 3}}

    def test_residual_queue_by_stop_is_a_copy_not_a_reference(self) -> None:
        """residual_queue_by_stopが元queuesの参照ではなくコピーであること
        （呼び出し後にqueuesを変更してもレポートに影響しない）。
        """
        queues = {"bs_1": {"type4": 1, "type3_mob": 0, "type3": 0}}
        result = acc.settle_stranded_to_rescue(queues, [], non_car_households_total=0.0)
        queues["bs_1"]["type4"] = 999
        assert result["residual_queue_by_stop"]["bs_1"]["type4"] == 1

    def test_rescue_after_bus_formula(self) -> None:
        """rescue_after_bus_vehicles_raw = non_car_households*R - bus_transport_total/k。"""
        queues: dict[str, dict[str, int]] = {}
        passenger_rows = [{"arrived": True} for _ in range(10)]
        result = acc.settle_stranded_to_rescue(
            queues, passenger_rows, non_car_households_total=50.0
        )
        k = acc.config.RESCUE_PER_VEHICLE_K
        r = acc.config.RESCUE_RATE_R
        expected = round(50.0 * r - 10 / k, 3)
        assert result["rescue_after_bus_vehicles_raw"] == expected

    def test_empty_queues_zero_residual(self) -> None:
        result = acc.settle_stranded_to_rescue({}, [], non_car_households_total=0.0)
        assert result["residual_queue_total"] == 0
        assert result["bus_transport_total"] == 0


# ---------------------------------------------------------------------------
# queue_total
# ---------------------------------------------------------------------------


class TestQueueTotal:
    def test_sums_all_categories_all_stops(self) -> None:
        queues = {
            "bs_1": {"type4": 1, "type3_mob": 2, "type3": 3},
            "bs_2": {"type4": 0, "type3_mob": 0, "type3": 10},
        }
        assert acc.queue_total(queues) == 16

    def test_zero_for_empty_dict(self) -> None:
        assert acc.queue_total({}) == 0


# ---------------------------------------------------------------------------
# load_bus_units / stop_meta_from_plan
# ---------------------------------------------------------------------------


class TestLoadBusUnitsAndStopMeta:
    def _plan_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "bus_id": "bus_wf_1",
                "bus_vtype": "bus_welfare",
                "origin_id": "origin_1",
                "KEY_CODE": "08211001",
                "pickup_edge": "e1",
                "pickup_stop_id": "bs_1",
                "shelter_id": "shelter_1",
                "shelter_edge": "e_shelter",
            },
            {
                "bus_id": "bus_std_1",
                "bus_vtype": "bus_standard",
                "origin_id": "origin_2",
                "KEY_CODE": "08211002",
                "pickup_edge": "e2",
                "pickup_stop_id": "bs_2",
                "shelter_id": "shelter_1",
                "shelter_edge": "e_shelter",
            },
        ]

    def test_load_bus_units_capacity_and_welfare_flag(self, tmp_path: Path) -> None:
        bus_plan = make_bus_plan_csv(tmp_path, self._plan_rows())
        units = acc.load_bus_units(bus_plan)

        assert len(units) == 2
        welfare = next(u for u in units if u.bus_id == "bus_wf_1")
        standard = next(u for u in units if u.bus_id == "bus_std_1")
        assert welfare.is_welfare is True
        assert welfare.capacity == acc.config.BUS_CAPACITY_WELFARE
        assert standard.is_welfare is False
        assert standard.capacity == acc.config.BUS_CAPACITY_STD

    def test_stop_meta_from_plan_maps_stop_to_origin_and_key_code(self, tmp_path: Path) -> None:
        bus_plan = make_bus_plan_csv(tmp_path, self._plan_rows())
        meta = acc.stop_meta_from_plan(bus_plan)

        assert meta["bs_1"] == {
            "origin_id": "origin_1",
            "KEY_CODE": "08211001",
            "shelter_id": "shelter_1",
        }
        assert meta["bs_2"]["origin_id"] == "origin_2"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
