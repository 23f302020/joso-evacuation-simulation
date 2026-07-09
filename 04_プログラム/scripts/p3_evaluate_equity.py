"""Phase 3 E系: distribution-based equity metrics for evacuation results.

避難完了時間の分布ベース公平性指標（worst-off 分位）を、シナリオ非依存で算出する。
入力は Phase 2/3 の `*_vehicle_log.csv`（列: duration, arrival, arrived, stranded_main 等）。
SUMO 実行を必要とせず pandas のみで動作するため、R4（シナリオA再実行）・B系
（シナリオB）の出力どちらにもそのまま適用できる。A/B 比較は相対差で提示する
（本研究方針: 逃げ遅れ絶対数は主張せず A/B 相対差で論じる）。

判断結果 2026-07-07（`交通シミュレーション調査/_判断結果_2026-07-07.md`）に基づき、
公平性指標は worst-off 分位のみを採用する（ジニ・アトキンソン・アクセシビリティ
格差は不採用）。指標のうち worst-off 系を論文で主張するかは RQ 改訂の承認(A1)を
前提とする。承認前でも本スクリプトの算出自体は実行・検証してよい。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import config

SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_RESULTS_DIR = OUTPUT_DIR / "sumo" / "results"
SUMO_EVAL_DIR = OUTPUT_DIR / "sumo" / "evaluation"

# worst-off（最も不利な層）を定義する分位。既定は最も遅い 10%。
DEFAULT_WORST_OFF_FRACTION = 0.10
# 分布として報告するパーセンタイル点。
REPORTED_PERCENTILES = (0.50, 0.75, 0.90, 0.95, 0.99)

# シナリオA（自家用車）の既定の入力。R4 後もパスは同じなので再実行結果に追随する。
DEFAULT_SCENARIO_A = {
    "small": SUMO_RESULTS_DIR / "scenario_a_small_vehicle_log.csv",
    "10pct": SUMO_RESULTS_DIR / "scenario_a_10pct_vehicle_log.csv",
    "full": SUMO_RESULTS_DIR / "scenario_a_vehicle_log.csv",
}


def region_dir(city_code: str) -> Path:
    return OUTPUT_DIR / "sumo" / "regions" / city_code


def _read_bool_series(series: pd.Series) -> pd.Series:
    """CSV 上の真偽表現（True/1/yes 等）を bool へ正規化する。"""
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def compute_equity_metrics(
    vehicle_log_path: Path,
    worst_off_fraction: float = DEFAULT_WORST_OFF_FRACTION,
) -> dict[str, Any]:
    """1 シナリオ分の vehicle_log から分布ベースの公平性指標を計算する。

    worst-off 分位は「到着車両のうち最も遅い worst_off_fraction の避難完了時間の平均」
    として定義する。到着できなかった車両（stranded / not arrived）は完了時間が
    打ち切り（右打ち切り）であり分位計算からは除外し、代わりに絶対的な最悪層として
    stranded_count / stranded_rate で別掲する。
    """
    if not 0.0 < worst_off_fraction < 1.0:
        raise ValueError(
            f"worst_off_fraction は (0,1) の範囲で指定してください: {worst_off_fraction}"
        )

    df = pd.read_csv(vehicle_log_path)
    total_count = int(len(df))

    arrived_mask = (
        _read_bool_series(df["arrived"]) if "arrived" in df.columns else pd.Series(dtype=bool)
    )
    arrived_count = int(arrived_mask.sum())
    stranded_count = total_count - arrived_count

    durations = (
        pd.to_numeric(df.loc[arrived_mask, "duration"], errors="coerce").dropna()
        if arrived_count > 0
        else pd.Series(dtype=float)
    )
    arrivals = (
        pd.to_numeric(df.loc[arrived_mask, "arrival"], errors="coerce").dropna()
        if arrived_count > 0
        else pd.Series(dtype=float)
    )

    metrics: dict[str, Any] = {
        "source": vehicle_log_path.name,
        "total_count": total_count,
        "arrived_count": arrived_count,
        "stranded_count": stranded_count,
        "stranded_rate": round(stranded_count / total_count, 6) if total_count else "",
        "worst_off_fraction": worst_off_fraction,
    }

    if durations.empty:
        # 到着車両が無い場合は分布指標を空で返す（集計側で欠損として扱える）。
        metrics.update(
            {
                "mean_duration_sec": "",
                "worst_off_mean_duration_sec": "",
                "completion_time_sec": "",
                **{f"p{int(p * 100)}_duration_sec": "" for p in REPORTED_PERCENTILES},
            }
        )
        return metrics

    sorted_durations = durations.sort_values()
    # worst-off = 最も遅い側の分位。少なくとも 1 台は含める。
    worst_off_n = max(1, int(round(len(sorted_durations) * worst_off_fraction)))
    worst_off_slice = sorted_durations.iloc[-worst_off_n:]

    metrics["mean_duration_sec"] = round(float(durations.mean()), 3)
    metrics["worst_off_mean_duration_sec"] = round(float(worst_off_slice.mean()), 3)
    metrics["worst_off_count"] = worst_off_n
    # 全車両到着時のみ避難完了時刻（最後の到着）を確定値として入れる。
    metrics["completion_time_sec"] = (
        int(arrivals.max()) if stranded_count == 0 and not arrivals.empty else ""
    )
    for p in REPORTED_PERCENTILES:
        metrics[f"p{int(p * 100)}_duration_sec"] = round(
            float(durations.quantile(p)), 3
        )
    return metrics


def build_scenario_table(
    scenarios: dict[str, Path],
    worst_off_fraction: float = DEFAULT_WORST_OFF_FRACTION,
) -> pd.DataFrame:
    """複数シナリオの公平性指標を 1 つの DataFrame に集約する。"""
    rows: list[dict[str, Any]] = []
    for label, path in scenarios.items():
        if not path.exists():
            print(f"[WARN] skip (not found): {path}")
            continue
        row = {"scenario": label, **compute_equity_metrics(path, worst_off_fraction)}
        rows.append(row)
    return pd.DataFrame(rows)


def compare_ab(
    df: pd.DataFrame,
    baseline: str,
    treatment: str,
) -> pd.DataFrame:
    """A/B の相対差（treatment 対 baseline）を算出する。

    絶対数ではなく相対差（減少率）で提示する本研究方針に沿う。
    正の improvement_pct は「treatment で改善（値が減少）」を意味する。
    """
    compare_cols = [
        "stranded_count",
        "stranded_rate",
        "mean_duration_sec",
        "worst_off_mean_duration_sec",
        "completion_time_sec",
    ]
    indexed = df.set_index("scenario")
    if baseline not in indexed.index or treatment not in indexed.index:
        raise KeyError(
            f"baseline/treatment が集計に存在しません: {baseline}, {treatment}"
        )

    rows: list[dict[str, Any]] = []
    for col in compare_cols:
        base_val = pd.to_numeric(indexed.at[baseline, col], errors="coerce")
        treat_val = pd.to_numeric(indexed.at[treatment, col], errors="coerce")
        if pd.isna(base_val) or pd.isna(treat_val):
            improvement = ""
            abs_diff = ""
        else:
            abs_diff = round(float(treat_val - base_val), 3)
            improvement = (
                round(float((base_val - treat_val) / base_val) * 100, 2)
                if base_val != 0
                else ""
            )
        rows.append(
            {
                "metric": col,
                f"{baseline}": indexed.at[baseline, col],
                f"{treatment}": indexed.at[treatment, col],
                "abs_diff(treatment-baseline)": abs_diff,
                "improvement_pct(reduction)": improvement,
            }
        )
    return pd.DataFrame(rows)


def run_scenario_a(worst_off_fraction: float) -> None:
    """既定のシナリオA（small/10pct/full）に対して指標を出力する。"""
    SUMO_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    df = build_scenario_table(DEFAULT_SCENARIO_A, worst_off_fraction)
    out = SUMO_EVAL_DIR / "equity_scenario_a.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"[INFO] saved: {out}")
    print(df.to_string(index=False))


def run_region_phase3_summary(city_code: str) -> None:
    base = region_dir(city_code)
    derived = base / "derived"
    results = base / "results"
    evaluation = base / "evaluation"
    evaluation.mkdir(parents=True, exist_ok=True)

    a_summary = json.loads(
        (results / "scenario_a_traci_summary.json").read_text(encoding="utf-8")
    )
    b_traci_summary = json.loads(
        (results / "scenario_b_traci_summary.json").read_text(encoding="utf-8")
    )
    b_summary = json.loads(
        (results / "scenario_b_bus_summary.json").read_text(encoding="utf-8")
    )
    a_assign = pd.read_csv(derived / "scenario_a_vehicle_assignments.csv")
    b_assign = pd.read_csv(derived / "scenario_b_vehicle_assignments.csv")
    agent_summary = pd.read_csv(derived / "agent_type_summary.csv").iloc[0].to_dict()
    reduction = pd.read_csv(derived / "scenario_b_rescue_reduction.csv")

    bus_transport = int(b_summary["bus_arrived_passengers"])
    bus_boarded = int(b_summary["bus_boarded_passengers"])
    bus_not_arrived = int(b_summary["bus_not_arrived_passengers"])
    initial_bus_demand = int(b_summary["initial_bus_candidate_total"])
    residual_queue = int(b_summary["two_layer_report"]["residual_queue_total"])
    k_base = float(getattr(config, "RESCUE_PER_VEHICLE_K", 2.3))
    rescue_removed_base_raw = bus_transport / k_base
    rescue_removed_base_int = int(reduction["rescue_removed_count"].sum())
    rescue_removed_k1 = bus_transport
    a_vehicle_count = int(a_summary["vehicle_count"])
    b_vehicle_count = int(b_traci_summary["vehicle_count"])
    a_rescue_count = int((a_assign["vehicle_kind"] == "rescue_car").sum())
    b_rescue_count = int((b_assign["vehicle_kind"] == "rescue_car").sum())
    type34_total = int(agent_summary["bus_candidate_population"])

    rows = [
        {
            "metric": "vehicle_count",
            "scenario_a": a_vehicle_count,
            "scenario_b": b_vehicle_count,
            "difference_b_minus_a": b_vehicle_count - a_vehicle_count,
            "note": "route vehicle count for both scenarios; same quantity comparison",
        },
        {
            "metric": "arrived_vehicle_count",
            "scenario_a": int(a_summary["arrived_count"]),
            "scenario_b": int(b_traci_summary["arrived_count"]),
            "difference_b_minus_a": int(b_traci_summary["arrived_count"]) - int(a_summary["arrived_count"]),
            "note": "arrived vehicles for both scenarios",
        },
        {
            "metric": "not_arrived_vehicle_count",
            "scenario_a": int(a_summary["not_arrived_count"]),
            "scenario_b": int(b_traci_summary["not_arrived_count"]),
            "difference_b_minus_a": int(b_traci_summary["not_arrived_count"]) - int(a_summary["not_arrived_count"]),
            "note": "not-arrived vehicles for both scenarios",
        },
        {
            "metric": "rescue_vehicle_count",
            "scenario_a": a_rescue_count,
            "scenario_b": b_rescue_count,
            "difference_b_minus_a": b_rescue_count - a_rescue_count,
            "note": f"k={k_base} base accounting",
        },
        {
            "metric": "bus_transport_people",
            "scenario_a": "",
            "scenario_b": bus_transport,
            "difference_b_minus_a": "",
            "note": "arrived bus passengers only; despawn/not-arrived excluded",
        },
        {
            "metric": "bus_boarded_people",
            "scenario_a": "",
            "scenario_b": bus_boarded,
            "difference_b_minus_a": "",
            "note": "includes not-arrived bus passengers",
        },
        {
            "metric": "bus_not_arrived_people",
            "scenario_a": "",
            "scenario_b": bus_not_arrived,
            "difference_b_minus_a": "",
            "note": "despawn/time-end passengers are not counted as transported",
        },
        {
            "metric": "bus_initial_candidate_demand",
            "scenario_a": "",
            "scenario_b": initial_bus_demand,
            "difference_b_minus_a": "",
            "note": "demand in selected five bus stop meshes",
        },
        {
            "metric": "bus_residual_queue",
            "scenario_a": "",
            "scenario_b": residual_queue,
            "difference_b_minus_a": "",
            "note": "selected-stop demand not boarded/arrived by bus",
        },
        {
            "metric": "selected_stop_demand_satisfaction_rate",
            "scenario_a": "",
            "scenario_b": round(bus_transport / initial_bus_demand, 6)
            if initial_bus_demand
            else "",
            "difference_b_minus_a": "",
            "note": "bus_transport_people / selected-stop candidate demand",
        },
        {
            "metric": "all_type34_demand_satisfaction_rate",
            "scenario_a": "",
            "scenario_b": round(bus_transport / type34_total, 6) if type34_total else "",
            "difference_b_minus_a": "",
            "note": "bus_transport_people / all Type3+Type4 demand in full target",
        },
        {
            "metric": "rescue_reduction_raw_k2_3",
            "scenario_a": "",
            "scenario_b": round(rescue_removed_base_raw, 3),
            "difference_b_minus_a": "",
            "note": "raw value retained",
        },
        {
            "metric": "rescue_reduction_integer_k2_3",
            "scenario_a": "",
            "scenario_b": rescue_removed_base_int,
            "difference_b_minus_a": "",
            "note": "integer trips removed from scenario_b.rou.xml",
        },
        {
            "metric": "rescue_reduction_k1_sensitivity",
            "scenario_a": "",
            "scenario_b": rescue_removed_k1,
            "difference_b_minus_a": "",
            "note": "k=1.0 sensitivity; not used for base route generation",
        },
        {
            "metric": "terminated_trips",
            "scenario_a": "",
            "scenario_b": int(b_summary["terminated_trips"]),
            "difference_b_minus_a": "",
            "note": json.dumps(b_summary.get("termination_by_reason", {}), ensure_ascii=False),
        },
        {
            "metric": "scenario_a_long_stopped_count",
            "scenario_a": int(a_summary.get("long_stopped_count", 0)),
            "scenario_b": int(b_traci_summary.get("long_stopped_count", 0)),
            "difference_b_minus_a": int(b_traci_summary.get("long_stopped_count", 0)) - int(a_summary.get("long_stopped_count", 0)),
            "note": "600s+ stopped vehicles",
        },
        {
            "metric": "run_id",
            "scenario_a": a_summary.get("run_id", ""),
            "scenario_b": b_traci_summary.get("run_id", ""),
            "difference_b_minus_a": "",
            "note": "B run_id must match bus summary manifest",
        },
    ]
    out = evaluation / "phase3_ab_comparison.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
    print(f"[INFO] saved: {out}")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_a = sub.add_parser("scenario-a", help="既定のシナリオA(small/10pct/full)を集計")
    p_a.add_argument(
        "--worst-off-fraction",
        type=float,
        default=DEFAULT_WORST_OFF_FRACTION,
        help="worst-off とみなす最遅分位（既定 0.10）",
    )

    p_one = sub.add_parser("one", help="任意の vehicle_log を 1 つ集計")
    p_one.add_argument("label", help="シナリオラベル")
    p_one.add_argument("vehicle_log", type=Path, help="vehicle_log.csv のパス")
    p_one.add_argument(
        "--worst-off-fraction", type=float, default=DEFAULT_WORST_OFF_FRACTION
    )

    p_ab = sub.add_parser("compare", help="2 つの vehicle_log を A/B 相対比較")
    p_ab.add_argument("baseline_label")
    p_ab.add_argument("baseline_log", type=Path)
    p_ab.add_argument("treatment_label")
    p_ab.add_argument("treatment_log", type=Path)
    p_ab.add_argument(
        "--worst-off-fraction", type=float, default=DEFAULT_WORST_OFF_FRACTION
    )
    p_ab.add_argument("--out", type=Path, default=None, help="比較CSVの出力先")

    p_region = sub.add_parser("region-phase3", help="地域別Phase3 A/B従指標CSVを生成")
    p_region.add_argument("--city-code", required=True)

    args = parser.parse_args()

    if args.command == "scenario-a":
        run_scenario_a(args.worst_off_fraction)
    elif args.command == "one":
        metrics = compute_equity_metrics(args.vehicle_log, args.worst_off_fraction)
        for key, value in metrics.items():
            print(f"{key}: {value}")
    elif args.command == "compare":
        scenarios = {
            args.baseline_label: args.baseline_log,
            args.treatment_label: args.treatment_log,
        }
        df = build_scenario_table(scenarios, args.worst_off_fraction)
        comparison = compare_ab(df, args.baseline_label, args.treatment_label)
        print(comparison.to_string(index=False))
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            comparison.to_csv(args.out, index=False, encoding="utf-8")
            print(f"[INFO] saved: {args.out}")
    elif args.command == "region-phase3":
        run_region_phase3_summary(args.city_code)


if __name__ == "__main__":
    main()
