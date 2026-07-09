"""Phase 3前処理: Phase 2入力からエージェント4タイプ分類を作成する。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

import config


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DERIVED_DIR = OUTPUT_DIR / "sumo" / "derived"
RESEARCH_RESULTS_PHASE2_DIR = PROGRAM_DIR.parent / "06_研究結果" / "phase2"

ORIGIN_POINTS_CSV = OUTPUT_DIR / "agents" / "origin_points.csv"
AGENT_ORIGINS_SUMO_CSV = SUMO_DERIVED_DIR / "agent_origins_sumo.csv"

AGENT_TYPES_CSV = SUMO_DERIVED_DIR / "agent_types.csv"
BUS_DEMAND_CANDIDATES_CSV = SUMO_DERIVED_DIR / "bus_demand_candidates.csv"
AGENT_TYPE_SUMMARY_CSV = SUMO_DERIVED_DIR / "agent_type_summary.csv"
AGENT_TYPE_SUMMARY_MD = RESEARCH_RESULTS_PHASE2_DIR / "Phase3前_エージェント4タイプ前処理結果.md"

NON_CAR_RATE = getattr(config, "NON_CAR_RATE", 0.15)
TYPE3_MOBILITY_LIMITED_RATE = 500 / 4700
BASE_BUS_CAPACITY_PEOPLE = (
    (getattr(config, "BUS_COUNT_BASE", 5) - 1)
    * getattr(config, "BUS_CAPACITY_STD", 8)
    * 9
    + getattr(config, "BUS_CAPACITY_WELFARE", 4)
    * 9
)


def ensure_dirs() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_RESULTS_PHASE2_DIR.mkdir(parents=True, exist_ok=True)


def allocate_agent_types(row: pd.Series) -> dict[str, Any]:
    total_pop = int(row["total_pop"])
    elderly_pop = int(row["elderly_pop"])
    non_elderly_pop = max(0, total_pop - elderly_pop)

    type4_no_car_elderly = round(elderly_pop * NON_CAR_RATE)
    type2_car_elderly = elderly_pop - type4_no_car_elderly
    type3_no_car_non_elderly = round(non_elderly_pop * NON_CAR_RATE)
    type1_car_non_elderly = non_elderly_pop - type3_no_car_non_elderly
    type3_mobility_limited = round(type3_no_car_non_elderly * TYPE3_MOBILITY_LIMITED_RATE)
    bus_priority_population = type4_no_car_elderly + type3_mobility_limited

    return {
        "total_pop": total_pop,
        "elderly_pop": elderly_pop,
        "non_elderly_pop": non_elderly_pop,
        "type1_car_non_elderly_pop": type1_car_non_elderly,
        "type2_car_elderly_pop": type2_car_elderly,
        "type3_no_car_non_elderly_pop": type3_no_car_non_elderly,
        "type4_no_car_elderly_pop": type4_no_car_elderly,
        "type3_mobility_limited_candidate_pop": type3_mobility_limited,
        "bus_candidate_population": type3_no_car_non_elderly + type4_no_car_elderly,
        "bus_priority_population": bus_priority_population,
    }


def build_agent_types_for_paths(
    origins_path: Path,
    origins_sumo_path: Path,
    out_dir: Path,
    summary_md_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    origins = pd.read_csv(origins_path, dtype={"KEY_CODE": str})
    origins_sumo = pd.read_csv(origins_sumo_path, dtype={"KEY_CODE": str})
    merged = origins_sumo.merge(
        origins[["KEY_CODE", "total_pop", "elderly_pop"]],
        on="KEY_CODE",
        how="left",
        validate="one_to_one",
    )
    if merged[["total_pop", "elderly_pop"]].isna().any().any():
        missing = merged[merged["total_pop"].isna()]["KEY_CODE"].tolist()
        raise ValueError(f"Missing population fields for KEY_CODE: {missing[:5]}")

    type_rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        allocation = allocate_agent_types(row)
        type_rows.append(
            {
                "origin_id": row["origin_id"],
                "KEY_CODE": row["KEY_CODE"],
                "lon": row["lon"],
                "lat": row["lat"],
                "sumo_edge_id": row["sumo_edge_id"],
                "snap_distance_m": row["snap_distance_m"],
                "vehicle_count_small": int(row["vehicle_count_small"]),
                "vehicle_count_10pct": int(row["vehicle_count_10pct"]),
                "vehicle_count_full": int(row["vehicle_count_full"]),
                "non_car_rate": NON_CAR_RATE,
                "type3_mobility_limited_rate": round(TYPE3_MOBILITY_LIMITED_RATE, 6),
                **allocation,
            }
        )

    agent_types = pd.DataFrame(type_rows)
    bus_candidates = agent_types[agent_types["bus_priority_population"] > 0].copy()
    bus_candidates = bus_candidates.sort_values(
        ["bus_priority_population", "type4_no_car_elderly_pop", "total_pop"],
        ascending=[False, False, False],
    )
    bus_candidates.insert(0, "priority_rank", range(1, len(bus_candidates) + 1))

    summary = pd.DataFrame(
        [
            {
                "origin_count": len(agent_types),
                "total_pop": int(agent_types["total_pop"].sum()),
                "elderly_pop": int(agent_types["elderly_pop"].sum()),
                "non_elderly_pop": int(agent_types["non_elderly_pop"].sum()),
                "type1_car_non_elderly_pop": int(
                    agent_types["type1_car_non_elderly_pop"].sum()
                ),
                "type2_car_elderly_pop": int(agent_types["type2_car_elderly_pop"].sum()),
                "type3_no_car_non_elderly_pop": int(
                    agent_types["type3_no_car_non_elderly_pop"].sum()
                ),
                "type4_no_car_elderly_pop": int(agent_types["type4_no_car_elderly_pop"].sum()),
                "type3_mobility_limited_candidate_pop": int(
                    agent_types["type3_mobility_limited_candidate_pop"].sum()
                ),
                "bus_candidate_population": int(agent_types["bus_candidate_population"].sum()),
                "bus_priority_population": int(agent_types["bus_priority_population"].sum()),
                "base_bus_capacity_people": BASE_BUS_CAPACITY_PEOPLE,
                "base_capacity_coverage_rate": round(
                    BASE_BUS_CAPACITY_PEOPLE
                    / max(1, int(agent_types["bus_priority_population"].sum())),
                    6,
                ),
            }
        ]
    )

    agent_types_csv = out_dir / "agent_types.csv"
    bus_candidates_csv = out_dir / "bus_demand_candidates.csv"
    summary_csv = out_dir / "agent_type_summary.csv"
    agent_types.to_csv(agent_types_csv, index=False, encoding="utf-8")
    bus_candidates.to_csv(bus_candidates_csv, index=False, encoding="utf-8")
    summary.to_csv(summary_csv, index=False, encoding="utf-8")
    if summary_md_path is not None:
        write_summary_md(
            summary.iloc[0],
            len(bus_candidates),
            agent_types_csv,
            bus_candidates_csv,
            summary_csv,
            summary_md_path,
        )
    return agent_types, bus_candidates, summary


def build_agent_types() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_dirs()
    return build_agent_types_for_paths(
        ORIGIN_POINTS_CSV,
        AGENT_ORIGINS_SUMO_CSV,
        SUMO_DERIVED_DIR,
        AGENT_TYPE_SUMMARY_MD,
    )


def write_summary_md(
    summary: pd.Series,
    bus_candidate_origin_count: int,
    agent_types_csv: Path,
    bus_candidates_csv: Path,
    summary_csv: Path,
    summary_md_path: Path,
) -> None:
    lines = [
        "# Phase 3前 エージェント4タイプ前処理結果",
        "",
        "> 作成日：2026/05/19  ",
        "> 目的：Phase 3のバス利用候補を作る前処理として、Phase 2の常総市出発地を4タイプへ分類する。",
        "",
        "## 1. 採用した第1近似",
        "",
        "| 項目 | 採用値 | 理由 |",
        "|---|---:|---|",
        f"| 非車保有率 | {NON_CAR_RATE:.0%} | `H2_人口エージェント属性定義.md` の第1近似に合わせる |",
        f"| Type3行動困難者率 | {TYPE3_MOBILITY_LIMITED_RATE:.3f} | H2のType3行動困難者500人 / Type3 4,700人から算出 |",
        f"| ベースバス輸送容量 | {BASE_BUS_CAPACITY_PEOPLE}人 | H2の5台・8人・複数往復仮定に合わせる |",
        "",
        "## 2. 集計結果",
        "",
        "| 指標 | 値 |",
        "|---|---:|",
        f"| 出発地数 | {int(summary['origin_count'])} |",
        f"| 総人口 | {int(summary['total_pop'])} |",
        f"| 高齢者人口 | {int(summary['elderly_pop'])} |",
        f"| Type1 車保有・非高齢者 | {int(summary['type1_car_non_elderly_pop'])} |",
        f"| Type2 車保有・高齢者 | {int(summary['type2_car_elderly_pop'])} |",
        f"| Type3 車非保有・非高齢者 | {int(summary['type3_no_car_non_elderly_pop'])} |",
        f"| Type4 車非保有・高齢者 | {int(summary['type4_no_car_elderly_pop'])} |",
        f"| Type3行動困難候補 | {int(summary['type3_mobility_limited_candidate_pop'])} |",
        f"| バス候補人口（Type3+Type4） | {int(summary['bus_candidate_population'])} |",
        f"| バス優先人口（Type4+Type3行動困難候補） | {int(summary['bus_priority_population'])} |",
        f"| バス優先候補を持つ出発地数 | {bus_candidate_origin_count} |",
        f"| ベース容量カバー率 | {summary['base_capacity_coverage_rate']:.3f} |",
        "",
        "## 3. 出力ファイル",
        "",
        "| ファイル | 内容 |",
        "|---|---|",
        f"| `{agent_types_csv}` | 出発地ごとの4タイプ人口とSUMO edge対応 |",
        f"| `{bus_candidates_csv}` | バス優先人口がある出発地を優先順位付きで抽出 |",
        f"| `{summary_csv}` | 4タイプ分類の集計値 |",
        "",
        "## 4. 注意点",
        "",
        "- この前処理はPhase 3本体のバス運行実装ではない。",
        "- 現時点では非車保有率15%を全メッシュへ一律適用する第1近似である。",
        "- Phase 3実装時には、この候補表からバス容量・往復回数に応じて実際の乗車対象を選ぶ。",
    ]
    summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["all"], help="task to run")
    parser.add_argument(
        "--city-code",
        help="地域別SUMO出力を対象にする場合の市区町村コード（例: 08211）",
    )
    args = parser.parse_args()
    if args.command == "all":
        if args.city_code:
            derived_dir = OUTPUT_DIR / "sumo" / "regions" / args.city_code / "derived"
            agent_types, bus_candidates, summary = build_agent_types_for_paths(
                derived_dir / "agent_origins_10pct.csv",
                derived_dir / "agent_origins_sumo.csv",
                derived_dir,
                None,
            )
            print(f"[INFO] saved: {derived_dir / 'agent_types.csv'} ({len(agent_types)} origins)")
            print(f"[INFO] saved: {derived_dir / 'bus_demand_candidates.csv'} ({len(bus_candidates)} origins)")
            print(f"[INFO] saved: {derived_dir / 'agent_type_summary.csv'}")
        else:
            agent_types, bus_candidates, summary = build_agent_types()
            print(f"[INFO] saved: {AGENT_TYPES_CSV} ({len(agent_types)} origins)")
            print(f"[INFO] saved: {BUS_DEMAND_CANDIDATES_CSV} ({len(bus_candidates)} origins)")
            print(f"[INFO] saved: {AGENT_TYPE_SUMMARY_CSV}")
            print(f"[INFO] saved: {AGENT_TYPE_SUMMARY_MD}")
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
