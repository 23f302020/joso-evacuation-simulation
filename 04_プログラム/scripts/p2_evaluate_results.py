"""Phase 2: aggregate SUMO evacuation results for thesis tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"
SUMO_RESULTS_DIR = SUMO_DIR / "results"
SUMO_EVAL_DIR = SUMO_DIR / "evaluation"
RESEARCH_RESULTS_PHASE2_DIR = PROGRAM_DIR.parent / "06_研究結果" / "phase2"

PHASE1_UNREACHABLE_CSV = OUTPUT_DIR / "routes" / "unreachable_agents.csv"

EVACUATION_SUMMARY_CSV = SUMO_EVAL_DIR / "evacuation_summary.csv"
CONGESTION_LOG_CSV = SUMO_EVAL_DIR / "congestion_log.csv"
MAJOR_ROUTE_CONGESTION_SUMMARY_CSV = SUMO_EVAL_DIR / "major_route_congestion_summary.csv"
PHASE1_PHASE2_COMPARISON_CSV = SUMO_EVAL_DIR / "phase1_phase2_comparison.csv"
TABLE_TEMPLATE_MD = RESEARCH_RESULTS_PHASE2_DIR / "Phase2_評価表テンプレート.md"

SCENARIOS = {
    "small": {
        "label": "small",
        "summary": SUMO_RESULTS_DIR / "scenario_a_small_traci_summary.json",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_small_vehicle_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_small_congestion_log.csv",
        "major_route_congestion_summary": SUMO_RESULTS_DIR
        / "scenario_a_small_major_route_congestion_summary.csv",
    },
    "10pct": {
        "label": "10pct",
        "summary": SUMO_RESULTS_DIR / "scenario_a_10pct_traci_summary.json",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_10pct_vehicle_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_10pct_congestion_log.csv",
        "major_route_congestion_summary": SUMO_RESULTS_DIR
        / "scenario_a_10pct_major_route_congestion_summary.csv",
    },
    "full": {
        "label": "full",
        "summary": SUMO_RESULTS_DIR / "scenario_a_traci_summary.json",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_vehicle_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_congestion_log.csv",
        "major_route_congestion_summary": SUMO_RESULTS_DIR
        / "scenario_a_major_route_congestion_summary.csv",
    },
}


def ensure_dirs() -> None:
    SUMO_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_RESULTS_PHASE2_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def md_value(value: Any) -> Any:
    if pd.isna(value):
        return ""
    return value


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_evacuation_summary() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario_name, scenario in SCENARIOS.items():
        summary = read_json(scenario["summary"])
        vehicle_count = int(summary["vehicle_count"])
        arrived_count = int(summary["arrived_count"])
        stranded_main_count = int(summary["stranded_main_count"])
        rows.append(
            {
                "scenario_name": scenario_name,
                "scale_label": scenario["label"],
                "vehicle_count": vehicle_count,
                "departed_count": int(summary.get("departed_count", arrived_count)),
                "arrived_count": arrived_count,
                "not_arrived_count": int(summary["not_arrived_count"]),
                "arrival_rate": ratio(arrived_count, vehicle_count),
                "reroute_failed_count": int(summary["reroute_failed_count"]),
                "long_stopped_count": int(summary["long_stopped_count"]),
                "departure_blocked_by_closure_count": int(
                    summary.get("departure_blocked_by_closure_count", 0)
                ),
                "stranded_main_count": stranded_main_count,
                "stranded_rate": ratio(stranded_main_count, vehicle_count),
                "closure_event_count": int(summary["closure_event_count"]),
                "final_cumulative_closed_sumo_edge_count": int(
                    summary["final_cumulative_closed_sumo_edge_count"]
                ),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(EVACUATION_SUMMARY_CSV, index=False, encoding="utf-8")
    return df


def generate_congestion_log() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for scenario_name, scenario in SCENARIOS.items():
        df = pd.read_csv(scenario["congestion_log"])
        df.insert(0, "scale_label", scenario["label"])
        df.insert(0, "scenario_name", scenario_name)
        frames.append(df)
    output = pd.concat(frames, ignore_index=True)
    output.to_csv(CONGESTION_LOG_CSV, index=False, encoding="utf-8")
    return output


def generate_major_route_congestion_summary() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for scenario_name, scenario in SCENARIOS.items():
        path = scenario["major_route_congestion_summary"]
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if "scenario" not in df.columns:
            df.insert(0, "scenario", scenario_name)
        frames.append(df)
    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    output.to_csv(MAJOR_ROUTE_CONGESTION_SUMMARY_CSV, index=False, encoding="utf-8")
    return output


def generate_phase1_phase2_comparison(evacuation_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    phase1 = pd.read_csv(PHASE1_UNREACHABLE_CSV, dtype={"KEY_CODE": str})
    for timestamp, group in phase1.groupby("timestamp", sort=True):
        rows.append(
            {
                "analysis_type": "phase1_static_route_search",
                "scenario_name": "phase1_static",
                "time_or_scale": timestamp,
                "unit": "mesh_population",
                "vehicle_count": "",
                "departed_count": "",
                "arrived_count": "",
                "not_arrived_vehicle_count": "",
                "stranded_main_vehicle_count": "",
                "unreachable_mesh_count": int(group["KEY_CODE"].nunique()),
                "unreachable_population": int(group["total_pop"].sum()),
                "unreachable_elderly_population": int(group["elderly_pop"].sum()),
                "note": "Phase 1 static shortest path result; not directly a vehicle count.",
            }
        )

    for _, row in evacuation_summary.iterrows():
        rows.append(
            {
                "analysis_type": "phase2_dynamic_sumo",
                "scenario_name": row["scenario_name"],
                "time_or_scale": row["scale_label"],
                "unit": "vehicle",
                "vehicle_count": int(row["vehicle_count"]),
                "departed_count": int(row["departed_count"]),
                "arrived_count": int(row["arrived_count"]),
                "not_arrived_vehicle_count": int(row["not_arrived_count"]),
                "stranded_main_vehicle_count": int(row["stranded_main_count"]),
                "unreachable_mesh_count": "",
                "unreachable_population": "",
                "unreachable_elderly_population": "",
                "note": "Phase 2 dynamic SUMO result; stranded_main includes reroute failure, 600s stop, and departure blocked by closure.",
            }
        )

    fieldnames = [
        "analysis_type",
        "scenario_name",
        "time_or_scale",
        "unit",
        "vehicle_count",
        "departed_count",
        "arrived_count",
        "not_arrived_vehicle_count",
        "stranded_main_vehicle_count",
        "unreachable_mesh_count",
        "unreachable_population",
        "unreachable_elderly_population",
        "note",
    ]
    write_csv(PHASE1_PHASE2_COMPARISON_CSV, fieldnames, rows)
    return pd.DataFrame(rows)


def write_table_template(
    evacuation_summary: pd.DataFrame,
    comparison: pd.DataFrame,
    major_route_summary: pd.DataFrame,
) -> None:
    phase1_rows = comparison[comparison["analysis_type"] == "phase1_static_route_search"]
    full = evacuation_summary[evacuation_summary["scenario_name"] == "full"].iloc[0]
    lines = [
        "# Phase 2 評価表テンプレート",
        "",
        "## 表1 Phase 2 シナリオAの避難完了結果",
        "",
        "| ケース | 車両数 | 出発台数 | 到着台数 | 未到着台数 | 逃げ遅れ主指標 | 到着率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in evacuation_summary.iterrows():
        lines.append(
            "| {scenario_name} | {vehicle_count} | {departed_count} | {arrived_count} | "
            "{not_arrived_count} | {stranded_main_count} | {arrival_rate:.3f} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## 表2 Phase 1静的到達不可とPhase 2動的逃げ遅れの比較",
            "",
            "| 区分 | 単位 | 主な値 | 注記 |",
            "|---|---|---:|---|",
            f"| Phase 1静的経路探索 | メッシュ/人口 | "
            f"{int(phase1_rows['unreachable_mesh_count'].max())}メッシュ・"
            f"{int(phase1_rows['unreachable_population'].max())}人 | "
            "閉鎖道路を除外した最短経路探索で到達不可となった対象 |",
            f"| Phase 2動的SUMO（全量） | 車両 | "
            f"{int(full['stranded_main_count'])}台 | "
            "動的閉鎖下でreroute失敗、600秒以上停止、または出発edge閉鎖により発車不能となった対象 |",
            "",
            "## 表3 主要避難路別の渋滞指標",
            "",
            "| ケース | 路線 | 最大車両数 | 最大停止車両数 | 最低平均速度(m/s) | 最大占有率(%) | 最大閉鎖edge数 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    if not major_route_summary.empty:
        for _, row in major_route_summary.iterrows():
            row_data = {key: md_value(value) for key, value in row.to_dict().items()}
            lines.append(
                "| {scenario} | {route_name} | {max_vehicle_count} | {max_halting_vehicle_count} | "
                "{min_mean_speed_mps} | {max_mean_occupancy_pct} | {max_closed_edge_count} |".format(
                    **row_data
                )
            )
    lines.extend(
        [
            "",
            "## 注記",
            "",
            "- Phase 1はメッシュ・人口単位、Phase 2は車両単位であり、同じ数値として単純比較しない。",
            "- Phase 2全量試行では、未到着14台はいずれも閉鎖済み出発edgeから発車できなかった車両として記録した。",
            "- 表3の主要避難路はGraphMLの路線番号・道路名から抽出したSUMO edge群であり、国道294号、国道・県道354号、県道357号、常総IC接続部（水海道有料道路）を対象とする。",
            "- SUMOのteleport警告は渋滞・車線遷移問題の解消処理であり、本集計では到着/未到着と逃げ遅れ主指標を優先して評価する。",
        ]
    )
    TABLE_TEMPLATE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_all() -> None:
    ensure_dirs()
    evacuation_summary = generate_evacuation_summary()
    generate_congestion_log()
    major_route_summary = generate_major_route_congestion_summary()
    comparison = generate_phase1_phase2_comparison(evacuation_summary)
    write_table_template(evacuation_summary, comparison, major_route_summary)
    print(f"[INFO] saved: {EVACUATION_SUMMARY_CSV}")
    print(f"[INFO] saved: {CONGESTION_LOG_CSV}")
    print(f"[INFO] saved: {MAJOR_ROUTE_CONGESTION_SUMMARY_CSV}")
    print(f"[INFO] saved: {PHASE1_PHASE2_COMPARISON_CSV}")
    print(f"[INFO] saved: {TABLE_TEMPLATE_MD}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["all"], help="task to run")
    args = parser.parse_args()
    if args.command == "all":
        run_all()


if __name__ == "__main__":
    main()
