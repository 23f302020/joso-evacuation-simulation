#!/usr/bin/env python3
"""既存の正本・診断CSVだけから卒論用静的図表と記述表を生成する。

追加SUMO runや新しい正式判定は行わない。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
P2_EVAL = ROOT / "04_プログラム/output/sumo/evaluation"
P3_EVAL = ROOT / "04_プログラム/output/sumo/regions/08211/evaluation"
P3_DERIVED = ROOT / "04_プログラム/output/sumo/regions/08211/derived"
P2_FIG = ROOT / "06_研究結果/phase2/figures"
P3_FIG = ROOT / "06_研究結果/phase3/figures"
HTML_FIG = ROOT / "04_プログラム/output/assets/research_figures"
BUS_TABLE = ROOT / "06_研究結果/phase3/Phase3_バス運行サービス詳細表.md"
N03 = (
    ROOT
    / "04_プログラム/data/admin_boundary/N03-150101_08_GML"
    / "N03-20150101_08_GML/N03-15_08_150101.shp"
)


def setup_plotting() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Yu Gothic", "Meiryo", "Noto Sans CJK JP", "DejaVu Sans"],
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
            "figure.dpi": 140,
        }
    )
    P2_FIG.mkdir(parents=True, exist_ok=True)
    P3_FIG.mkdir(parents=True, exist_ok=True)


GENERATED_IMAGES: list[Path] = []


def save_svg(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, format="svg", bbox_inches="tight", metadata={"Date": "2026-07-21"})
    png_path = path.with_suffix(".png")
    fig.savefig(png_path, format="png", dpi=180, bbox_inches="tight")
    HTML_FIG.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, HTML_FIG / path.name)
    shutil.copy2(png_path, HTML_FIG / png_path.name)
    GENERATED_IMAGES.extend([path, png_path])
    plt.close(fig)


def plot_phase2_congestion() -> Path:
    df = pd.read_csv(P2_EVAL / "congestion_log.csv")
    order = ["small", "10pct", "full"]
    labels = {"small": "small（40台）", "10pct": "10pct（120台）", "full": "full（1,001台）"}
    fig, axes = plt.subplots(3, 2, figsize=(11.4, 8.4), sharex=True)

    for row, scenario in enumerate(order):
        part = df[df["scenario_name"] == scenario].copy()
        hours = part["sim_time_sec"] / 3600

        ax = axes[row, 0]
        ax.plot(hours, part["active_vehicle_count"], color="#31688e", lw=1.6, label="シミュレーション内")
        ax.plot(hours, part["stopped_vehicle_count"], color="#b35806", lw=1.5, label="停止")
        ax.set_ylabel(f"{labels[scenario]}\n車両数（台）")
        ax.grid(alpha=0.25, lw=0.6)
        if row == 0:
            ax.legend(loc="upper right", frameon=False, ncol=2)

        ax = axes[row, 1]
        speed_kmh = (part["mean_speed_mps"] * 3.6).where(part["active_vehicle_count"] > 0)
        speed_plot_kwargs = {"marker": "o", "markersize": 3.2} if scenario in {"small", "10pct"} else {}
        ax.plot(hours, speed_kmh, color="#2a9d8f", lw=1.6, **speed_plot_kwargs)
        ax.set_ylabel("平均速度（km/h）")
        ax.grid(alpha=0.25, lw=0.6)
        ax.set_ylim(bottom=0)
        if scenario in {"small", "10pct"}:
            ax.text(
                0.98,
                0.93,
                "有効値10点（開始10分）",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                color="#4d4d4d",
            )

    axes[0, 0].set_title("シミュレーション内・停止車両数")
    axes[0, 1].set_title("ネットワーク平均速度")
    axes[-1, 0].set_xlabel("シミュレーション時間（時）")
    axes[-1, 1].set_xlabel("シミュレーション時間（時）")
    fig.suptitle("Phase 2 常総市：試行規模別の交通状態（60秒間隔）", fontsize=15, y=1.01)
    fig.text(
        0.5,
        -0.01,
        "注：Phase 2旧成果は単一run・SUMO既定teleport=300秒。実装基盤と時間変化の記述に用い、一般的な逃げ遅れ確定値にはしない。",
        ha="center",
        fontsize=9,
        color="#4d4d4d",
    )
    fig.tight_layout()
    path = P2_FIG / "fig_phase2_congestion_timeseries.svg"
    save_svg(fig, path)
    return path


def plot_pairwise_differences() -> Path:
    df = pd.read_csv(P3_EVAL / "phase3r_e1_15_combination_signs.csv")
    x = np.arange(len(df))
    labels = [f"{b.replace('#', '')}−{a.replace('#', '')}" for b, a in zip(df["b_run"], df["a_run"])]
    fig, ax = plt.subplots(figsize=(12.2, 5.7))
    ax.axhline(0, color="#202020", lw=1.2)
    ax.scatter(x - 0.08, df["raw_delta_percentage_points"], s=42, marker="o", color="#31688e", label="raw")
    ax.scatter(
        x + 0.08,
        df["conservative_delta_percentage_points"],
        s=42,
        marker="x",
        linewidths=1.7,
        color="#b35806",
        label="保守",
    )
    ax.set_xticks(x, labels, rotation=55, ha="right")
    ax.set_ylabel("B−A Type3/4完了率差（ポイント）")
    ax.set_xlabel("B run − A run")
    ax.set_title("図4-7-1　Type3/4完了率の全15組合せ差")
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    ax.legend(frameon=False)
    ax.text(
        0.01,
        0.97,
        "負2組・正13組：ゼロをまたぐため方向差を確定しない",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
    )
    fig.text(
        0.5,
        -0.02,
        "注：15組はA3run・B5runの8runを再利用した非独立な組合せであり、15個の独立標本として扱わない。",
        ha="center",
        fontsize=9,
        color="#4d4d4d",
    )
    fig.tight_layout()
    path = P3_FIG / "fig4-7-1_pairwise_completion_rate_differences.svg"
    save_svg(fig, path)
    return path


def plot_replicate_rates() -> Path:
    df = pd.read_csv(P3_EVAL / "phase3r_e1_replicate_metrics.csv")
    fig, ax = plt.subplots(figsize=(8.8, 6.2))
    offsets = {"A": np.linspace(-0.13, 0.13, 3), "B": np.linspace(-0.17, 0.17, 5)}
    colors = {"A": "#2a9d8f", "B": "#31688e"}

    for scenario, x0 in (("A", 0), ("B", 1)):
        part = df[df["scenario"] == scenario].reset_index(drop=True)
        xs = x0 + offsets[scenario]
        raw = part["raw_completion_rate"] * 100
        conservative = part["conservative_completion_rate"] * 100
        ax.scatter(xs, raw, s=58, marker="o", color=colors[scenario], label=f"Scenario {scenario} raw")
        if scenario == "B":
            ax.scatter(xs, conservative, s=55, marker="x", linewidths=1.7, color="#b35806", label="Scenario B 保守")
        for x, y, run, seed in zip(xs, raw, part["run"], part["seed"]):
            ax.annotate(f"{run}\nseed {seed}", (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)
        ax.hlines(raw.median(), x0 - 0.24, x0 + 0.24, colors=colors[scenario], lw=2.0)

    ax.set_xlim(-0.45, 1.45)
    ax.set_ylim(72, 101.5)
    ax.set_xticks([0, 1], ["Scenario A\n自家用車＋救出走行", "Scenario B\n固定経路避難シャトル"])
    ax.set_ylabel("Type3/4避難完了率（%）")
    ax.set_title("図5-4-1　run別完了率と初期条件感応性")
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), frameon=False, loc="lower right")
    fig.text(
        0.5,
        -0.02,
        "横線はraw中央値。A#2を事後除外しない。本図は強い初期条件感応性を示すが、統計的二峰性の実証ではない。",
        ha="center",
        fontsize=9,
        color="#4d4d4d",
    )
    fig.tight_layout()
    path = P3_FIG / "fig5-4-1_replicate_completion_rates.svg"
    save_svg(fig, path)
    return path


def plot_origin_diagnostic() -> Path:
    diag = pd.read_csv(P3_EVAL / "scenario_a_diag_allocation_reweighting_by_origin.csv")
    origins = pd.read_csv(P3_DERIVED / "agent_origins_10pct.csv")[["origin_id", "lon", "lat"]]
    df = diag.merge(origins, on="origin_id", how="left", validate="one_to_one")
    if df[["lon", "lat"]].isna().any().any():
        raise ValueError("出発地診断と座標の結合に欠損があります")

    total = df["type3_total"] + df["type4_total"]
    arrived = df["type3_arrived"] + df["type4_arrived"]
    df["completion_rate"] = np.where(total > 0, arrived / total, np.nan)
    df["type34_total"] = total

    boundary = gpd.read_file(N03)
    boundary = boundary[boundary["N03_007"].astype(str) == "08211"].to_crs(4326)
    if boundary.empty:
        raise ValueError("N03から常総市境界を取得できません")

    fig, ax = plt.subplots(figsize=(8.2, 9.2))
    boundary.plot(ax=ax, facecolor="#f2f2f2", edgecolor="#4d4d4d", linewidth=0.9)
    def allocation_marker_size(people: pd.Series | float) -> pd.Series | float:
        return 16 + 3.2 * np.sqrt(np.maximum(people, 1))

    sizes = allocation_marker_size(df["type34_total"])
    points = ax.scatter(
        df["lon"],
        df["lat"],
        c=df["completion_rate"] * 100,
        s=sizes,
        cmap="viridis",
        vmin=0,
        vmax=100,
        edgecolor="#ffffff",
        linewidth=0.25,
        alpha=0.9,
    )
    cbar = fig.colorbar(points, ax=ax, shrink=0.72, pad=0.02)
    cbar.set_label("Type3/4完了率（%）")
    size_levels = [1, 5, 10, 25]
    size_handles = [
        ax.scatter(
            [],
            [],
            s=allocation_marker_size(people),
            facecolor="#bdbdbd",
            edgecolor="#ffffff",
            linewidth=0.25,
            label=f"{people}人",
        )
        for people in size_levels
    ]
    ax.legend(
        handles=size_handles,
        title="Type3/4割当数",
        loc="lower left",
        frameon=True,
        fontsize=8,
        title_fontsize=8.5,
        borderpad=0.6,
        labelspacing=0.7,
    )
    ax.set_title("図4-9-1　A基準runの出発地別Type3/4完了率（診断）")
    ax.set_xlabel("経度")
    ax.set_ylabel("緯度")
    ax.set_aspect("equal", adjustable="datalim")
    fig.text(
        0.5,
        0.015,
        "点の大きさはType3/4割当数。A基準runの配分診断であり、Phase 3全runの空間的一般結果・人口属性の因果効果・正式A/B判定には用いない。",
        ha="center",
        fontsize=8.5,
        color="#4d4d4d",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    path = P3_FIG / "fig4-9-1_origin_completion_diagnostic.svg"
    save_svg(fig, path)
    return path


def percentile_nearest(values: pd.Series, percentile: float) -> float:
    ordered = np.sort(values.astype(float).to_numpy())
    if len(ordered) == 0:
        return float("nan")
    index = int(np.floor(percentile * (len(ordered) - 1)))
    return float(ordered[index])


def fmt_minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def write_bus_service_table() -> Path:
    metrics = pd.read_csv(P3_EVAL / "phase3r_e1_replicate_metrics.csv")
    metrics = metrics[metrics["scenario"] == "B"]
    run_rows: list[dict[str, object]] = []
    passenger_frames: list[pd.DataFrame] = []

    for row in metrics.itertuples(index=False):
        artifact = Path(row.artifact_dir)
        passengers = pd.read_csv(artifact / "scenario_b_passenger_log.csv")
        passengers["run"] = row.run
        passengers["arrived_bool"] = passengers["arrived"].astype(str).str.lower().eq("true")
        passenger_frames.append(passengers)
        arrived = passengers[passengers["arrived_bool"]]
        run_rows.append(
            {
                "run": row.run,
                "seed": row.seed,
                "boarded": len(passengers),
                "arrived": len(arrived),
                "not_arrived": len(passengers) - len(arrived),
                "median_s": percentile_nearest(arrived["duration_s"], 0.5),
                "p90_s": percentile_nearest(arrived["duration_s"], 0.9),
                "origins": passengers["origin_id"].nunique(),
                "shelters": arrived["shelter_id"].nunique(),
            }
        )

    all_passengers = pd.concat(passenger_frames, ignore_index=True)
    origin_rows = []
    for origin_id, group in all_passengers.groupby("origin_id", sort=True):
        arrived = group[group["arrived_bool"]]
        origin_rows.append(
            {
                "origin_id": origin_id,
                "boarded": len(group),
                "arrived": len(arrived),
                "not_arrived": len(group) - len(arrived),
                "arrival_rate": 100 * len(arrived) / len(group),
                "median_s": percentile_nearest(arrived["duration_s"], 0.5),
                "runs": group["run"].nunique(),
            }
        )

    lines = [
        "# Phase 3 バス運行サービス詳細表",
        "",
        "> 生成日：2026-07-21  ",
        "> 対象：正本B側5runの`scenario_b_passenger_log.csv`  ",
        "> 位置づけ：輸送実績の記述表。Type3/4完了率の正式A/B判定には使用しない。",
        "",
        "## 1. run別輸送実績",
        "",
        "| run | seed | 乗車記録人数 | 避難所到着 | 乗車後未到着 | 到着者の車内時間中央値（分） | 90%点（分） | 利用出発地数 | 到着避難所数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in run_rows:
        lines.append(
            f"| {row['run']} | {row['seed']} | {row['boarded']} | {row['arrived']} | {row['not_arrived']} | "
            f"{fmt_minutes(float(row['median_s']))} | {fmt_minutes(float(row['p90_s']))} | {row['origins']} | {row['shelters']} |"
        )

    lines.extend(
        [
            "",
            "> 注：seed 42ではScenario AのA#2が低完了状態（75.87%）である一方、固定経路避難シャトルを含むfull-busのB#2は低完了状態ではない（Type3/4完了率raw 96.68%）。同じseedでもScenario構成により状態が非対称であり、A#2の低位をB#2へ一般化しない。",
        ]
    )

    lines.extend(
        [
            "",
            "## 2. 出発地別輸送実績（5run合計）",
            "",
            "| 出発地 | 乗車記録人数 | 避難所到着 | 乗車後未到着 | 到着率 | 到着者の車内時間中央値（分） | 出現run数 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in origin_rows:
        lines.append(
            f"| {row['origin_id']} | {row['boarded']} | {row['arrived']} | {row['not_arrived']} | "
            f"{row['arrival_rate']:.1f}% | {fmt_minutes(float(row['median_s']))} | {row['runs']} |"
        )

    lines.extend(
        [
            "",
            "## 3. 解釈上の制約",
            "",
            "1. 乗客ログはバスへ乗車した人を記録し、停留所に残った候補者全員を含まない。",
            "2. `duration_s`は乗車から到着または終了までであり、予約から乗車までの待ち時間ではない。",
            "3. 現行ログに予約時刻・待機開始時刻がないため、待ち時間は算出しない。`board_time_s`を待ち時間と読み替えない。",
            "4. 未到着者を除いた車内時間分布には条件付き選択があるため、到着人数・未到着人数と対で示す。",
            "5. 本表は現行の固定経路避難シャトルを記述し、動的DRTのサービス品質を示すものではない。",
            "",
            "## 4. 真実源",
            "",
            "- `04_プログラム/output/sumo/regions/08211/evaluation/phase3r_e1_replicate_metrics.csv`",
            "- 同CSVの`artifact_dir`配下にあるB側5runの`scenario_b_passenger_log.csv`",
            "",
        ]
    )
    BUS_TABLE.write_text("\n".join(lines), encoding="utf-8")
    return BUS_TABLE


def main() -> None:
    setup_plotting()
    outputs = [
        plot_phase2_congestion(),
        plot_pairwise_differences(),
        plot_replicate_rates(),
        plot_origin_diagnostic(),
        write_bus_service_table(),
    ]
    manifest = {
        "generated": [str(path.relative_to(ROOT)) for path in [*GENERATED_IMAGES, BUS_TABLE]],
        "source_policy": "existing canonical and diagnostic outputs only; no additional SUMO run",
    }
    manifest_path = P3_EVAL / "research_depth_figures_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in outputs:
        print(path.relative_to(ROOT))
    for path in GENERATED_IMAGES:
        if path.suffix == ".png":
            print(path.relative_to(ROOT))
    print(manifest_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
