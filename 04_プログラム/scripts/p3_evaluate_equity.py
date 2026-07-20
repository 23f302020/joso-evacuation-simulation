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

REPLICATE_SCOPE = {
    "unit_scope": "vehicle",
    "population_conditioning": "arrived_vehicles_only",
    "scenario_b_bus_passengers": "excluded",
    "analysis_role": "descriptive_diagnostic_only",
    "directional_claim": "prohibited",
}

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


def build_replicate_descriptive_table(
    replicate_metrics_path: Path,
    worst_off_fraction: float = DEFAULT_WORST_OFF_FRACTION,
) -> pd.DataFrame:
    """既存runの車両ログを、方向判定を含まない記述統計へ集約する。"""
    replicates = pd.read_csv(replicate_metrics_path)
    required = {"scenario", "run", "seed", "run_id", "artifact_dir"}
    missing = required.difference(replicates.columns)
    if missing:
        raise ValueError(f"replicate CSVの必須列がありません: {sorted(missing)}")

    rows: list[dict[str, Any]] = []
    for record in replicates.to_dict(orient="records"):
        scenario = str(record["scenario"]).strip().upper()
        artifact_dir = Path(str(record["artifact_dir"]))
        vehicle_log = artifact_dir / f"scenario_{scenario.lower()}_vehicle_log.csv"
        if not vehicle_log.exists():
            raise FileNotFoundError(f"archived vehicle logがありません: {vehicle_log}")

        metrics = compute_equity_metrics(vehicle_log, worst_off_fraction)
        rows.append(
            {
                "scenario": scenario,
                "run": record["run"],
                "seed": record["seed"],
                "run_id": record["run_id"],
                "source_vehicle_log": str(vehicle_log.resolve()),
                **REPLICATE_SCOPE,
                "total_vehicle_count": metrics["total_count"],
                "arrived_vehicle_count": metrics["arrived_count"],
                "arrival_rate": round(
                    metrics["arrived_count"] / metrics["total_count"], 6
                )
                if metrics["total_count"]
                else "",
                "worst_off_fraction": metrics["worst_off_fraction"],
                "worst_off_count": metrics.get("worst_off_count", ""),
                "mean_duration_sec": metrics["mean_duration_sec"],
                "p50_duration_sec": metrics["p50_duration_sec"],
                "p75_duration_sec": metrics["p75_duration_sec"],
                "p90_duration_sec": metrics["p90_duration_sec"],
                "p95_duration_sec": metrics["p95_duration_sec"],
                "p99_duration_sec": metrics["p99_duration_sec"],
                "worst_off_mean_duration_sec": metrics[
                    "worst_off_mean_duration_sec"
                ],
            }
        )
    return pd.DataFrame(rows)


def run_replicate_descriptive(
    city_code: str,
    worst_off_fraction: float,
    replicate_metrics_path: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    """地域別の既存replicateからworst-off記述統計CSVを1枚生成する。"""
    evaluation = region_dir(city_code) / "evaluation"
    source = replicate_metrics_path or evaluation / "phase3r_e1_replicate_metrics.csv"
    out = out_path or evaluation / "phase3_worst_off_descriptive.csv"
    table = build_replicate_descriptive_table(source, worst_off_fraction)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False, encoding="utf-8")
    print(f"[INFO] saved: {out}")
    print(table.to_string(index=False))
    return out


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

    band = json.loads((evaluation / "phase3r_e1_band_summary.json").read_text(encoding="utf-8"))
    rows = build_phase3_band_comparison_rows(band)
    out = evaluation / "phase3_ab_comparison.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
    print(f"[INFO] saved: {out}")
    print(pd.DataFrame(rows).to_string(index=False))


def build_phase3_band_comparison_rows(band: dict[str, Any]) -> list[dict[str, Any]]:
    def row(metric: str, unit: str, **values: Any) -> dict[str, Any]:
        return {
            "metric": metric,
            "unit": unit,
            "scenario_a_point": "",
            "scenario_a_min": "",
            "scenario_a_max": "",
            "scenario_b_point": "",
            "scenario_b_min": "",
            "scenario_b_max": "",
            "difference_b_minus_a_point": "",
            "difference_b_minus_a_min": "",
            "difference_b_minus_a_max": "",
            "positive_combinations": "",
            "negative_combinations": "",
            "zero_combinations": "",
            "note": "",
            **values,
        }

    raw_signs = band["raw_sign_counts"]
    conservative_signs = band["conservative_sign_counts"]
    return [
        row(
            "route_vehicle_count",
            "vehicles",
            scenario_a_point=9569,
            scenario_a_min=9569,
            scenario_a_max=9569,
            scenario_b_point=9515,
            scenario_b_min=9515,
            scenario_b_max=9515,
            difference_b_minus_a_point=-54,
            difference_b_minus_a_min=-54,
            difference_b_minus_a_max=-54,
            note="AC8 same-quantity comparison; rescue reduction fixed externally at 54",
        ),
        row(
            "type34_completion_rate_raw",
            "percent",
            scenario_a_point=band["a_completion_rate_median"] * 100,
            scenario_a_min=band["a_completion_rate_min"] * 100,
            scenario_a_max=band["a_completion_rate_max"] * 100,
            scenario_b_point=band["b_raw_completion_rate_median"] * 100,
            scenario_b_min=band["b_raw_completion_rate_min"] * 100,
            scenario_b_max=band["b_raw_completion_rate_max"] * 100,
            difference_b_minus_a_point=band["raw_point_delta_percentage_points"],
            difference_b_minus_a_min=band["raw_delta_min_percentage_points"],
            difference_b_minus_a_max=band["raw_delta_max_percentage_points"],
            positive_combinations=raw_signs["positive"],
            negative_combinations=raw_signs["negative"],
            zero_combinations=raw_signs["zero"],
            note="difference columns are percentage points; 15-combination signs are non-consistent",
        ),
        row(
            "type34_completion_rate_conservative",
            "percent",
            scenario_a_point=band["a_completion_rate_median"] * 100,
            scenario_a_min=band["a_completion_rate_min"] * 100,
            scenario_a_max=band["a_completion_rate_max"] * 100,
            scenario_b_point=band["b_conservative_completion_rate_median"] * 100,
            scenario_b_min=band["b_conservative_completion_rate_min"] * 100,
            scenario_b_max=band["b_conservative_completion_rate_max"] * 100,
            difference_b_minus_a_point=band["conservative_point_delta_percentage_points"],
            difference_b_minus_a_min=band["conservative_delta_min_percentage_points"],
            difference_b_minus_a_max=band["conservative_delta_max_percentage_points"],
            positive_combinations=conservative_signs["positive"],
            negative_combinations=conservative_signs["negative"],
            zero_combinations=conservative_signs["zero"],
            note="bus arrivals capped at 124.2 people; difference columns are percentage points",
        ),
    ]


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

    p_replicates = sub.add_parser(
        "replicates-descriptive",
        help="既存replicateのworst-off記述統計CSVを生成（SUMO実行なし）",
    )
    p_replicates.add_argument("--city-code", required=True)
    p_replicates.add_argument(
        "--worst-off-fraction", type=float, default=DEFAULT_WORST_OFF_FRACTION
    )
    p_replicates.add_argument("--replicate-metrics", type=Path, default=None)
    p_replicates.add_argument("--out", type=Path, default=None)

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
    elif args.command == "replicates-descriptive":
        run_replicate_descriptive(
            args.city_code,
            args.worst_off_fraction,
            args.replicate_metrics,
            args.out,
        )


if __name__ == "__main__":
    main()
