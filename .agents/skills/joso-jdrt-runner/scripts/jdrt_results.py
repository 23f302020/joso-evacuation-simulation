"""Export the fully validated and recorded JDRT v2 core as one offline HTML file."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote

import jdrt_cell as cell


OUTPUT_REL = Path("06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html")


def collect(root: Path) -> dict:
    parameters = cell._json(root / cell.PARAMETERS_REL)
    cells = cell._cells(parameters)
    expected = int(parameters["experiment"]["expected_core_run_count"])
    current = cell.status(root)
    if (len(cells) != expected or current["completed_valid"] != expected
            or current["recorded"] != expected or current["running"]
            or current["completed_unrecorded"]):
        raise ValueError(f"All {expected} core cells must be completed and recorded before export: {current}")
    manifests = cell._matching_manifests(root, cell._sha256(root / cell.PARAMETERS_REL))
    completed = cell._completed_by_cell(manifests)
    if set(completed) != set(cells):
        raise ValueError("Completed cells differ from the registered core")
    latest_id = completed[cells[-1]]["run_id"]
    for relative in [cell.FULL_RECORD_REL, cell.TASKS_REL, cell.CONTEXT_REL, cell.DECISIONS_REL, cell.PROGRESS_REL]:
        if latest_id not in cell._read_preserved(root / relative):
            raise ValueError(f"Final cell is not synchronized: {relative}")
    results = []
    sources = {}
    for scenario, seed in cells:
        manifest = completed[(scenario, seed)]
        result = cell.validate_run(root, manifest["run_id"])
        if result["validation"] != "PASS":
            raise ValueError(f"Independent validation failed: {result}")
        results.append(result)
        relative = cell.RUNS_REL / manifest["run_id"] / "manifest.json"
        sources[relative.as_posix()] = cell._sha256(root / relative)
    for relative in [cell.PARAMETERS_REL, cell.INPUT_REGISTRY_REL, cell.LEDGER_REL, cell.FULL_RECORD_REL]:
        sources[relative.as_posix()] = cell._sha256(root / relative)
    sources[Path(__file__).resolve().relative_to(root).as_posix()] = cell._sha256(Path(__file__))
    accepted = {item["run_id"] for item in results}
    excluded = [{"run_id": item["run_id"], "status": item["status"]}
                for item in manifests if item["run_id"] not in accepted]
    return {"parameters": parameters, "results": results, "sources_sha256": sources, "excluded": excluded}


def table(headers: list[str], rows: list[list[str]], caption: str) -> str:
    heading = "".join(f'<th scope="col">{escape(label)}</th>' for label in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
    return f'<div class="scroll"><table><caption>{escape(caption)}</caption><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>'


def render(root: Path, data: dict, output: Path) -> str:
    parameters = data["parameters"]
    population = parameters["population"]
    type4 = int(population["type4"])
    eligible = int(population["drt_eligible"])
    requests = int(population["request_grouping"]["expected_request_count"])
    outcome_rows, technical_rows = [], []
    for index, result in enumerate(data["results"], 1):
        run_id = result["run_id"]
        source = root / cell.RUNS_REL / run_id / "manifest.json"
        href = quote(os.path.relpath(source, output.parent).replace("\\", "/"), safe="/.")
        identifier = f'<a href="{href}"><code>{escape(run_id)}</code></a>'
        label = [escape(result["scenario"]), str(result["seed"])]
        p95 = "NA（成功者なし）" if result["arrival_p95_sec"] is None else str(result["arrival_p95_sec"])
        outcome_rows.append([str(index), *label,
            f'{result["type4_evacuated"]} / {type4}<br>{result["type4_evacuated"] / type4 * 100:.3f}%',
            str(result["type3_evacuated"]),
            f'{result["evacuated"]} / {eligible}<br>{result["evacuated"] / eligible * 100:.3f}%',
            str(result["stranded"]),
            f'{result["request_completed"]} / {requests}', str(result["request_stranded"]),
            p95, f'{result["total_vkt_km"]:.6f}', f'{result["empty_vkt_km"]:.6f}'])
        technical_rows.append([str(index), identifier, *label,
            str(result["warnings"]), str(result["errors"]), str(result["handled_errors"]),
            str(result["unhandled_errors"]), str(result["teleport"]), str(result["collision"]),
            str(result["controller_steps"]), str(result["observations"]),
            escape(f'{result["parameter_sha"]} / {result["input_sha"]} / {result["output_sha"]}'),
            escape(result["validation"])])
    outcomes = table(["#", "方式", "seed", "Type4完了 / 母数・率", "Type3完了（人）",
        "DRT対象完了 / 母数・率", "立ち往生（人）", "完了要求 / 全要求", "未完了要求",
        "到着P95（秒）", "総VKT（km）", "空車VKT（km）"], outcome_rows, "登録済み全セルの避難結果")
    technical = table(["#", "run ID・manifest", "方式", "seed", "Warning", "Error", "捕捉済みError",
        "未処理Error", "teleport", "衝突teleport", "controller回数", "観測回数",
        "SHA 設定 / 入力 / 出力", "独立検証"], technical_rows, "全セルの技術検証と一次成果物")
    excluded = table(["run ID", "状態"],
        [[escape(item["run_id"]), escape(item["status"])] for item in data["excluded"]],
        "同じv2設定の採用外run（結果集計に含めない）")
    stamp = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    evidence = escape(json.dumps({"generated_at_jst": stamp, "parameter_version": parameters["parameter_version"],
        "sources_sha256": data["sources_sha256"], "validated_results": data["results"]}, ensure_ascii=False, indent=2))
    count = len(data["results"])
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>常総市JDRT v2 全セル結果一覧</title>
<style>
body{{font:15px/1.7 system-ui,sans-serif;color:#172b3a;background:#f4f7fa;margin:0;padding:24px}}
main{{max-width:1600px;margin:auto}}h1{{font-size:28px}}h2{{margin-top:32px}}
.note{{border-left:4px solid #247487;background:#fff;padding:14px 20px}}
.scroll{{overflow:auto;background:white;border:1px solid #d9e1e8;margin:18px 0}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
caption{{text-align:left;font-weight:700;padding:12px}}th,td{{padding:9px 12px;border-bottom:1px solid #e1e7ec;text-align:right;white-space:nowrap}}
th{{background:#e6eff4}}td:nth-child(2){{text-align:left}}tbody tr:nth-child(even){{background:#f8fafc}}
code{{font-size:12px}}a{{color:#135b82}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;padding:16px}}
@media print{{body{{background:white;padding:0}}.scroll{{overflow:visible}}table{{font-size:8px}}th,td{{padding:3px;white-space:normal}}}}
</style></head><body><main>
<h1>常総市JDRT v2 全セル結果一覧</h1>
<p>登録済み {count} / {parameters["experiment"]["expected_core_run_count"]} セル：完了・独立検証PASS・記録済み。生成日時：{stamp}</p>
<div class="note">対象は常総市08211のJDRT v2中核実験です。v1、凍結済みPhase 1〜3、Scenario C、正式採用保留のREAL-R0を混在させません。
DRT対象は{eligible:,}人（Type4 {type4:,}人）。人口全体{population["total"]:,}人の完了率ではありません。
到着P95は成功者だけの値で、完了率と併せて読みます。Warningと捕捉済みErrorは隠さず表示します。
一覧は実測値の記述であり、現実の政策効果や他地域への一般化を意味しません。</div>
<h2>避難結果</h2>{outcomes}
<h2>技術検証</h2>{technical}
<p>人物・要求会計、VKT、event件数とSHA、入力・出力SHA、controller・観測回数、teleport・衝突・未処理Errorを一次成果物から再検証しました。
run IDのリンクから元のmanifestを参照できます。このHTML単独でも一覧と検証証跡を閲覧できます。</p>
<h2>採用外runの履歴</h2>{excluded}
<details><summary>生成根拠・SHA-256・独立検証の詳細</summary><pre>{evidence}</pre></details>
</main></body></html>'''


def generate(root: Path) -> dict:
    data = collect(root)
    output = root / OUTPUT_REL
    document = render(root, data, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cell._atomic_write(output, document)
    return {"status": "GENERATED", "path": str(output), "cell_count": len(data["results"]),
            "sha256": cell._sha256(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root")
    args = parser.parse_args()
    root = cell._find_project_root(args.project_root)
    started = time.monotonic()
    try:
        result = generate(root)
        cell._log_operation(root, "results", None, started, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        failure = {"status": "NOT_GENERATED", "error_type": type(error).__name__, "error": str(error)}
        cell._log_operation(root, "results", None, started, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
