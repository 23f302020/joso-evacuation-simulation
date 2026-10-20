"""Recalculate the fixed JDRT v2 core; never start or modify a simulation.

Run with the project venv Python and --project-root. Outputs are analysis-only.
The primary comparison and descriptive seed summaries follow PAP v1 sections
9-12, inherited by v2. Other contrast rows are labelled descriptive supplements.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
from html import escape
import json
import math
from pathlib import Path
import statistics
import sys


PREFIX = "JDRT-v2_中核比較"
OUT_REL = Path("06_研究結果/jdrt")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * .95) - 1] if ordered else None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def near(actual, expected, label):
    require((actual is None and expected is None) or
            (actual is not None and expected is not None and
             math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9)), label)


def stats(values):
    present = [value for value in values if value is not None]
    return {"n": len(present), "missing": len(values) - len(present),
            "median": statistics.median(present) if present else None,
            "min": min(present) if present else None,
            "max": max(present) if present else None,
            "positive": sum(value > 0 for value in present),
            "zero": sum(value == 0 for value in present),
            "negative": sum(value < 0 for value in present)}


def frozen_members(agent_rows, rescue_rows, parameters):
    """Reconstruct membership from PAP §4, then check it against run CSVs."""
    rescue = {row["origin_id"]: row for row in rescue_rows}
    result = {}
    capacity = parameters["population"]["request_grouping"]["capacity_reference"]
    for row in agent_rows:
        origin = row["origin_id"]
        definitions = [("type4", int(row["type4_no_car_elderly_pop"])),
                       ("type3_mobility_limited", int(row["type3_mobility_limited_candidate_pop"])),
                       ("type3", int(row["type3_no_car_non_elderly_pop"]) -
                        int(row["type3_mobility_limited_candidate_pop"]))]
        people = [[f"{origin}_{category}_{index:04d}" for index in range(1, count + 1)]
                  for category, count in definitions]
        total = sum(map(len, people))
        if not total:
            continue
        n = min(total, max(1, int(rescue[origin]["rescue_vehicle_count"]), math.ceil(total / capacity)))
        groups = [[] for _ in range(n)]
        for category in people:
            for identifier in category:
                groups[min(range(n), key=lambda index: (len(groups[index]), index))].append(identifier)
        for index, group in enumerate(groups, 1):
            result[f"request_{origin}_{index:04d}"] = group
    return result


def generate(root):
    helper_dir = root / ".agents/skills/joso-jdrt-runner/scripts"
    sys.path.insert(0, str(helper_dir))
    import jdrt_cell as cell
    import jdrt_results

    # Snapshot before validation, including files outside the metric subset.
    candidates = cell._matching_manifests(root, sha(root / cell.PARAMETERS_REL))
    accepted = cell._completed_by_cell(candidates)
    immutable = {path.relative_to(root).as_posix(): sha(path)
                 for item in accepted.values()
                 for path in (root / cell.RUNS_REL / item["run_id"]).iterdir() if path.is_file()}
    # collect() revalidates every registered cell and checks formal recording.
    data = jdrt_results.collect(root)
    parameters = data["parameters"]
    registry = json.loads((root / cell.INPUT_REGISTRY_REL).read_text(encoding="utf-8"))
    sources = {item["role"]: root / item["path"] for item in registry["files"]}
    agents = read_csv(sources["population_and_types"])
    origin_mesh = {row["origin_id"]: row["KEY_CODE"] for row in agents}
    membership = frozen_members(agents, read_csv(sources["rescue_substitution_and_fixed_shelter"]), parameters)
    require(len({person for group in membership.values() for person in group}) ==
            sum(map(len, membership.values())), "duplicate reconstructed person membership")
    evidence = dict(data["sources_sha256"])
    for relative in ["03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_v1.md",
                     "03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_v2.md",
                     "03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_v2.md"]:
        evidence[relative] = sha(root / relative)
    for source in [Path(__file__), helper_dir / "jdrt_cell.py", *sources.values()]:
        evidence[source.relative_to(root).as_posix()] = sha(source)
    evidence.update(immutable)
    rows, reasons, meshes, vehicles_out, time_rows = [], [], [], [], []
    people_by_cell = {}
    static_reference = None
    request_reference = None
    for validated in data["results"]:
        run_id = validated["run_id"]
        run_dir = root / cell.RUNS_REL / run_id
        people = {row["person_id"]: row for row in read_csv(run_dir / "person_results.csv")}
        requests_list = read_csv(run_dir / "request_results.csv")
        requests = {row["request_id"]: row for row in requests_list}
        require(len(people) == parameters["population"]["drt_eligible"], "duplicate/missing person ID")
        require(len(requests) == len(requests_list) == len(membership), "request ID/membership mismatch")
        static = {key: tuple(row[field] for field in
                  ["origin_id", "person_type", "vulnerability_score", "request_time_sec"])
                  for key, row in people.items()}
        request_static = {key: tuple(row[field] for field in
                          ["origin_edge", "shelter_id", "shelter_edge", "party_size", "vulnerability", "request_time_sec"])
                          for key, row in requests.items()}
        if static_reference is None:
            static_reference, request_reference = static, request_static
        require(static == static_reference, "paired person ID/static attributes differ")
        require(request_static == request_reference, "paired request static attributes differ")
        events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        stranded_events = [event for event in events if event["event_type"] == "REQUEST_STRANDED"]
        reason_map = {event["entity_id"]: event["details"]["reason"] for event in stranded_events}
        require(len(reason_map) == len(stranded_events), "duplicate stranded request event")
        require(set(reason_map) == {key for key, row in requests.items() if row["status"] == "STRANDED"}, "stranded reasons incomplete")
        person_request = {}
        reason_groups = defaultdict(list)
        for identifier, request in requests.items():
            members = [people[key] for key in membership[identifier]]
            require(len(members) == int(request["party_size"]), "request size mismatch")
            near(sum(float(row["vulnerability_score"]) for row in members) / len(members),
                 float(request["vulnerability"]), "request vulnerability mismatch")
            expected_status = "EVACUATED" if request["status"] == "COMPLETED" else "STRANDED"
            require(all(row["status"] == expected_status for row in members), "member terminal status mismatch")
            for field in ["pickup_time_sec", "arrival_time_sec"]:
                times = [float(row[field]) for row in members if row[field]]
                near(min(times) if times else None, float(request[field]) if request[field] else None, "member/request time mismatch")
            for member in members:
                person_request[member["person_id"]] = identifier
            if identifier in reason_map:
                reason_groups[reason_map[identifier]].append(identifier)
        for reason, identifiers in sorted(reason_groups.items()):
            members = [people[key] for identifier in identifiers for key in membership[identifier]]
            reasons.append({"run_id": run_id, "scenario": validated["scenario"], "seed": validated["seed"],
                            "reason": reason, "requests": len(identifiers), "people": len(members),
                            "type4_people": sum(row["person_type"] == "4" for row in members)})
        near(sum(row["people"] for row in reasons if row["run_id"] == run_id), validated["stranded"], "stranded reason population mismatch")
        for row in people.values():
            identifier = row["person_id"]
            row["request_id"] = person_request[identifier]
            row["stranded_reason"] = reason_map.get(person_request[identifier], "")
            row["mesh_code"] = origin_mesh[row["origin_id"]]
            require((row["status"] == "EVACUATED") == bool(row["arrival_time_sec"]), "arrival missingness mismatch")
            if row["arrival_time_sec"]:
                require(float(row["request_time_sec"]) <= float(row["pickup_time_sec"]) <= float(row["arrival_time_sec"]) <= parameters["simulation_end_sec"], "person time ordering")
        arrival = [float(row["arrival_time_sec"]) for row in people.values() if row["status"] == "EVACUATED"]
        near(p95(arrival), validated["arrival_p95_sec"], "independent arrival P95 mismatch")
        row = {**validated}
        del row["issues"]
        for kind, key, denom in [("type4", "type4_evacuated", parameters["population"]["type4"]),
                                 ("type3", "type3_evacuated", parameters["population"]["type3"]),
                                 ("all_drt", "evacuated", parameters["population"]["drt_eligible"])]:
            row[f"{kind}_denominator"] = denom
            row[f"{kind}_rate_pct"] = row[key] / denom * 100
        pickups = [float(item["pickup_time_sec"]) - float(item["request_time_sec"])
                   for item in requests.values() if item["pickup_time_sec"]]
        boarding = {event["entity_id"]: float(event["sim_time_sec"])
                    for event in events if event["event_type"] == "BOARDING_STARTED"}
        boarding_waits = [time - float(requests[key]["request_time_sec"]) for key, time in boarding.items()]
        row.update(request_pickup_completed=len(pickups), request_no_pickup=len(requests) - len(pickups),
                   request_pickup_rate_pct=len(pickups) / len(requests) * 100,
                   wait_pickup_completed_median_sec=statistics.median(pickups) if pickups else None,
                   wait_pickup_completed_p95_sec=p95(pickups),
                   request_boarding_started=len(boarding_waits),
                   wait_boarding_started_median_sec=statistics.median(boarding_waits) if boarding_waits else None,
                   wait_boarding_started_p95_sec=p95(boarding_waits))
        for request_id, request in requests.items():
            time_rows.append({"run_id": run_id, "scenario": row["scenario"], "seed": row["seed"],
                              **request, "stranded_reason": reason_map.get(request_id, ""),
                              "boarding_started_sec": boarding.get(request_id),
                              "wait_to_boarding_started_sec": boarding[request_id] - float(request["request_time_sec"]) if request_id in boarding else None,
                              "wait_to_pickup_completed_sec": float(request["pickup_time_sec"]) - float(request["request_time_sec"]) if request["pickup_time_sec"] else None})
        fleet = read_csv(run_dir / "drt_vehicle_metrics.csv")
        assigned = Counter(request["assigned_vehicle_id"] for request in requests.values() if request["status"] == "COMPLETED")
        for vehicle in fleet:
            identifier = vehicle["vehicle_id"]
            delivered = sum(int(request["party_size"]) for request in requests.values()
                            if request["status"] == "COMPLETED" and request["assigned_vehicle_id"] == identifier)
            vehicles_out.append({"run_id": run_id, "scenario": row["scenario"], "seed": row["seed"], **vehicle,
                                 "completed_requests": assigned[identifier], "evacuated_people": delivered})
        near(sum(v["evacuated_people"] for v in vehicles_out if v["run_id"] == run_id), row["evacuated"], "vehicle transport person accounting")
        congestion = read_csv(run_dir / "congestion.csv")
        row["network_sample_count"] = len(congestion)
        row["network_mean_of_snapshot_mean_speed_mps"] = statistics.mean(float(v["mean_speed_mps"]) for v in congestion)
        row["network_mean_snapshot_halting_vehicles"] = statistics.mean(int(v["halting_vehicle_count"]) for v in congestion)
        row["network_max_snapshot_halting_vehicles"] = max(int(v["halting_vehicle_count"]) for v in congestion)
        for mesh in sorted(set(origin_mesh.values())):
            residents = [person for person in people.values() if person["mesh_code"] == mesh]
            meshes.append({"run_id": run_id, "scenario": row["scenario"], "seed": row["seed"], "mesh_code": mesh,
                           "eligible_people": len(residents), "evacuated_people": sum(p["status"] == "EVACUATED" for p in residents),
                           "type4_people": sum(p["person_type"] == "4" for p in residents),
                           "type4_evacuated": sum(p["person_type"] == "4" and p["status"] == "EVACUATED" for p in residents)})
        rows.append(row)
        people_by_cell[(row["scenario"], row["seed"])] = people
    by_cell = {(row["scenario"], row["seed"]): row for row in rows}
    baseline = parameters["dispatchers"]["primary_baseline"]
    proposal = parameters["dispatchers"]["primary_proposal"]
    contrasts = [(proposal, baseline, "primary_PAP"),
                 (baseline, "JDRT-B2", "descriptive_support"),
                 ("JDRT-P1", baseline, "descriptive_support"),
                 (proposal, "JDRT-P1", "descriptive_support")]
    paired, individual = [], []
    outcomes = ["type4_evacuated", "type3_evacuated", "evacuated", "type4_rate_pct", "type3_rate_pct", "all_drt_rate_pct",
                "stranded", "arrival_p95_sec", "request_completed", "request_pickup_rate_pct",
                "wait_pickup_completed_median_sec", "wait_pickup_completed_p95_sec", "wait_boarding_started_median_sec",
                "total_vkt_km", "empty_vkt_km", "network_mean_of_snapshot_mean_speed_mps", "network_mean_snapshot_halting_vehicles"]
    for left, right, role in contrasts:
        for seed in parameters["experiment"]["paired_seeds"]:
            a, b = by_cell[left, seed], by_cell[right, seed]
            difference = {"comparison": f"{left} - {right}", "role": role, "seed": seed,
                          "left_run_id": a["run_id"], "right_run_id": b["run_id"]}
            for outcome in outcomes:
                difference[outcome] = a[outcome] - b[outcome] if a[outcome] is not None and b[outcome] is not None else None
            # Rate difference independently recalculated from exact integer counts.
            for rate, count, denominator in [("type4_rate_pct", "type4_evacuated", parameters["population"]["type4"]),
                                              ("type3_rate_pct", "type3_evacuated", parameters["population"]["type3"]),
                                              ("all_drt_rate_pct", "evacuated", parameters["population"]["drt_eligible"])]:
                near(difference[rate], float(Fraction(a[count] - b[count], denominator) * 100), "paired exact-rate difference")
            if role == "primary_PAP":
                transitions = Counter()
                for identifier, person in people_by_cell[left, seed].items():
                    previous = people_by_cell[right, seed][identifier]
                    transitions[(previous["status"], person["status"], person["person_type"])] += 1
                    individual.append({"seed": seed, "person_id": identifier, "origin_id": person["origin_id"], "mesh_code": person["mesh_code"],
                                       "person_type": person["person_type"], "vulnerability_score": person["vulnerability_score"],
                                       "baseline_status": previous["status"], "proposal_status": person["status"],
                                       "baseline_arrival_sec": previous["arrival_time_sec"], "proposal_arrival_sec": person["arrival_time_sec"],
                                       "baseline_stranded_reason": previous["stranded_reason"], "proposal_stranded_reason": person["stranded_reason"]})
                gained4 = transitions["STRANDED", "EVACUATED", "4"]
                lost4 = transitions["EVACUATED", "STRANDED", "4"]
                require(gained4 - lost4 == difference["type4_evacuated"], "Type4 gain/loss identity")
                difference["type4_gained_people"], difference["type4_lost_people"] = gained4, lost4
            paired.append(difference)
    summaries = []
    for group_field, groups in [("scenario", rows), ("comparison", paired)]:
        for label in dict.fromkeys(row[group_field] for row in groups):
            group = [row for row in groups if row[group_field] == label]
            for outcome in outcomes:
                summaries.append({"group_type": group_field, "group": label, "metric": outcome,
                                  "unit": "percentage_points" if group_field == "comparison" and outcome.endswith("_pct") else
                                          "percent" if outcome.endswith("_pct") else "see_dictionary",
                                  **stats([row[outcome] for row in group])})
    output = root / OUT_REL
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for suffix, contents in [("cells", rows), ("paired", paired), ("summary", summaries), ("stranded_reasons", reasons),
                             ("requests", time_rows), ("vehicles", vehicles_out), ("mesh", meshes), ("individual_primary", individual)]:
        path = output / f"{PREFIX}_{suffix}.csv"
        fields = list(dict.fromkeys(key for row in contents for key in row))
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(contents)
        require(len(read_csv(path)) == len(contents), "CSV read-back row count")
        artifacts[path.name] = {"rows": len(contents), "sha256": sha(path)}
    # Independent read-back uses integer differences and explicitly sorted seed values.
    saved_cells = {(row["scenario"], int(row["seed"])): row for row in read_csv(output / f"{PREFIX}_cells.csv")}
    for row in read_csv(output / f"{PREFIX}_paired.csv"):
        left, right = row["comparison"].split(" - ")
        a, b = saved_cells[left, int(row["seed"])], saved_cells[right, int(row["seed"])]
        for outcome in outcomes:
            actual = float(row[outcome]) if row[outcome] else None
            expected = float(a[outcome]) - float(b[outcome]) if a[outcome] and b[outcome] else None
            near(actual, expected, "CSV read-back paired difference")
    for item in summaries:
        group = rows if item["group_type"] == "scenario" else paired
        values = sorted(row[item["metric"]] for row in group if row[item["group_type"]] == item["group"] and row[item["metric"]] is not None)
        n = len(values)
        if n:
            near(item["median"], (values[(n-1)//2] + values[n//2]) / 2, "independent order-statistic median")
            require(item["min"] == values[0] and item["max"] == values[-1], "summary range")
    require(all(sha(root / relative) == digest for relative, digest in immutable.items()), "accepted run modified during analysis")
    report = build_report(parameters, rows, paired, summaries, artifacts)
    report_path = output / f"{PREFIX}_報告.md"
    report_path.write_text(report, encoding="utf-8")
    artifacts[report_path.name] = {"sha256": sha(report_path)}
    html_path = output / "JDRT-v2_中核比較.html"
    html_path.write_text(build_html(parameters, rows, paired, summaries), encoding="utf-8")
    artifacts[html_path.name] = {"sha256": sha(html_path)}
    manifest = {"generated_at_jst": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
                "parameter_version": parameters["parameter_version"], "protocol": "v2", "city_code": parameters["city_code"],
                "verification": "PASS", "accepted_cells": len(rows), "primary_contrast": f"{proposal} - {baseline}",
                "source_sha256": evidence, "artifacts": artifacts, "independent_checks": [
                    "all accepted cells independently validated by skill", "paired ID and static attributes identical",
                    "PAP reconstructed request membership matched CSV and terminal states", "all stranded events accounted by request and person",
                    "person CSV arrival P95 matched metrics", "vehicle transported people matched person totals",
                    "paired rates matched exact fractions", "CSV read-back differences and order-statistic summaries",
                    "all accepted run file SHA unchanged before/after"]}
    (output / f"{PREFIX}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"verification": "PASS", "cells": len(rows), "artifacts": artifacts,
            "primary_type4": [row for row in summaries if row["group_type"] == "comparison" and row["group"] == f"{proposal} - {baseline}" and row["metric"] == "type4_rate_pct"]}


def build_report(parameters, rows, paired, summaries, artifacts):
    primary = [row for row in paired if row["role"] == "primary_PAP"]
    lines = ["# 常総市JDRT v2 中核比較・取得データ検証", "", "対象：登録済み全中核セル。PAP v2が継承するv1第9〜12節の事前登録済み分析。",
             "v1、REAL-R0、Phase 3、Scenario Cは集計へ含めない。既存Phase 3のヌル結論は変更しない。", "",
             "## 主比較（P2-L15 − B3）", "", "率差の単位はパーセントポイント。全体はDRT対象者であり、人口全体ではない。", "",
             "| seed | Type4追加完了人数 | Type4率差 %pt | DRT対象追加完了人数 | DRT対象率差 %pt | Type4獲得 / 喪失 | 総VKT差 km | 空車VKT差 km |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in primary:
        lines.append(f'| {row["seed"]} | {row["type4_evacuated"]} | {row["type4_rate_pct"]:.6f} | {row["evacuated"]} | {row["all_drt_rate_pct"]:.6f} | {row["type4_gained_people"]} / {row["type4_lost_people"]} | {row["total_vkt_km"]:.6f} | {row["empty_vkt_km"]:.6f} |')
    lines += ["", "| 指標 | 対応差中央値 | 最小 | 最大 | 正 / 0 / 負 |", "|---|---:|---:|---:|---:|"]
    for item in summaries:
        if item["group_type"] == "comparison" and item["group"] == primary[0]["comparison"]:
            fmt = lambda value: "NA" if value is None else f"{value:.6f}"
            lines.append(f'| {item["metric"]} | {fmt(item["median"])} | {fmt(item["min"])} | {fmt(item["max"])} | {item["positive"]} / {item["zero"]} / {item["negative"]} |')
    lines += ["", "## 定義・単位・欠損・解釈", "",
              f'- Type4母数は{parameters["population"]["type4"]}人、Type3は{parameters["population"]["type3"]}人、DRT対象全体は{parameters["population"]["drt_eligible"]}人。人数・率を併記。',
              '- 完了はシミュレーション終了時刻までに安全な避難所で降車を完了した人。arrival_p95_secは成功者のみの最近順位法ceil(0.95n)の秒値。P95は完了率と対にし、両方式の成功者構成は同じとは限らない。',
              '- wait_pickup_completed_*は要求発生から乗車完了まで。pickup_time_secは乗車開始時刻ではない。wait_boarding_started_*はeventsのBOARDING_STARTEDまでの待ち。単位は秒、要求を1件1票として要約。',
              '- 未乗車・未乗車開始の待ち時間はnullであり0秒や21600秒を代入しない。終端理由付き失敗は、全てを一律の右打切りとは解釈しない。成功/観測された部分集合の中央値・P95と対象件数、非観測件数を併記し、母集団全体の平均待ち時間や生存時間推定は行わない。',
              '- 個人ID、origin、Type、脆弱性、要求発生時刻と要求静的属性が全セルで一致することを確認。主比較個人CSVは同一seed・同一IDの獲得/喪失を示す。別seedの人物を独立標本として合算しない。',
              '- stranded理由はREQUEST_STRANDEDのdetails.reason原文を保存。人数は凍結入力/PAPの決定的グループ割当を再構築し、要求人数・脆弱性・人物終状態・時刻を照合した上で集計した。理由は終端処理の分類であり、因果効果の分解とはしない。',
              '- 総/空車VKTはDRT車両のkm。vehiclesのtotal_m/empty_m/occupied_mは元出力のm。occupied_m+empty_mがtotal_mと必ず一致するとの仮定は置かない。1台あたり輸送人数は降車完了人数。',
              '- network速度は60秒ごとのネットワーク平均速度スナップショットの算術平均、haltingは各時点台数の平均/最大。全車両の時間加重平均速度や渋滞継続時間を意味しない。',
              '- meshは凍結agent_typesのorigin_id→KEY_CODEで対応。meshコードは文字列。ゼロ母数meshも人数0として保持。地域別表は探索的記述で、事前登録された地域別検定や現実人口の属性効果ではない。',
              '- B3−B2、P1−B3、P2−P1は登録方式間の補助的記述比較。具体的な補助差はPAPで固定されていないため、主比較と同格の検証仮説として扱わない。p値による成功判定は行わない。',
              '- 予測誤差は道路閉鎖時刻だけ。利用率100%、一斉要求、容量無制約、5台・poolingなしの共通条件に限定し、現実政策効果・実利用率・他地域へ一般化しない。',
              "", "## 取得範囲と不足", "",
              '- 取得済み：Type別人数と率、対応seed差と符号、理由別未完了、成功者P95、要求待ち/乗車成功、DRT VKT、1台別輸送、ネットワーク速度/halting、個人対応、mesh対応、技術ゲートとSHA。取得の成功と仮説支持は区別する。',
              '- Feasibility Gateの候補別拒否数・拒否理由は既存eventsに記録されていない。最終未完了理由から代用・逆算できない。',
              '- 実際の閉鎖後進入はedge軌跡を全車両分保存していないため直接検証できない。閉鎖適用ログやteleport 0から「閉鎖後進入0」と結論しない。',
              '- 新しい記録項目や感度runは研究方法の追加判断・事前登録後の別作業。既存run、実行器、設定は変更しない。',
              "", "## 再計算・監査", "",
              '実行：`04_プログラム/venv/Scripts/python.exe 04_プログラム/scripts/jdrt_v2_analysis.py --project-root .`',
              'manifestには取得日時（JST）、採用runと出典SHA、出力SHA、独立検証項目を保存。対象時点は各runの0〜21600秒であり、取得日現在の実社会データではない。全採用runの全ファイルSHAを分析前後で照合した。', "",
              "| 成果物 | 行数 |", "|---|---:|"]
    for name, info in artifacts.items():
        lines.append(f'| [{name}]({name}) | {info.get("rows", "—")} |')
    lines += ["", "CSVの列名が指標辞書を兼ねる。率は_pct、時刻/待ちは_sec、距離は_kmまたは_m、人数/件数は整数。差CSVでは_pct列の単位を%ptとする。空欄は未観測/未定義、0は観測値の0。", ""]
    return "\n".join(lines)


def build_html(parameters, rows, paired, summaries):
    primary = [row for row in paired if row["role"] == "primary_PAP"]
    heading = primary[0]["comparison"]
    def table(headers, contents):
        return ('<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{escape(str(h))}</th>' for h in headers) +
                '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in contents) + '</tbody></table></div>')
    def fmt(value):
        return "NA" if value is None else f"{value:.6f}"
    primary_table = table(["seed", "Type4追加人数", "Type4差 %pt", "DRT対象追加人数", "DRT対象差 %pt", "Type4獲得/喪失", "総VKT差 km", "空車VKT差 km"],
                          [[r["seed"], r["type4_evacuated"], fmt(r["type4_rate_pct"]), r["evacuated"], fmt(r["all_drt_rate_pct"]),
                            f'{r["type4_gained_people"]}/{r["type4_lost_people"]}', fmt(r["total_vkt_km"]), fmt(r["empty_vkt_km"])] for r in primary])
    summary_table = table(["主比較指標", "中央値", "最小", "最大", "正/0/負"],
                          [[r["metric"], fmt(r["median"]), fmt(r["min"]), fmt(r["max"]), f'{r["positive"]}/{r["zero"]}/{r["negative"]}']
                           for r in summaries if r["group_type"] == "comparison" and r["group"] == heading])
    cells_table = table(["方式", "seed", "Type4完了/母数", "Type4率 %", "DRT対象完了/母数", "DRT対象率 %", "成功者P95 秒", "乗車完了要求数", "要求→乗車完了 中央値 秒", "未乗車要求数"],
                       [[r["scenario"], r["seed"], f'{r["type4_evacuated"]}/{r["type4_denominator"]}', fmt(r["type4_rate_pct"]),
                         f'{r["evacuated"]}/{r["all_drt_denominator"]}', fmt(r["all_drt_rate_pct"]), r["arrival_p95_sec"], r["request_pickup_completed"],
                         r["wait_pickup_completed_median_sec"], r["request_no_pickup"]] for r in rows])
    extent = max(abs(r["type4_rate_pct"]) for r in primary) or 1
    ticks = []
    for index, r in enumerate(primary):
        y = 45 + index * 48
        width = abs(r["type4_rate_pct"]) / extent * 250
        x = 380 if r["type4_rate_pct"] >= 0 else 380 - width
        ticks.append(f'<text x="10" y="{y+16}">seed {r["seed"]}</text><rect x="{x}" y="{y}" width="{width}" height="24" fill="#247a82"/><text x="660" y="{y+16}">{r["type4_rate_pct"]:+.4f}</text>')
    chart = ('<svg role="img" aria-label="主比較のseed別Type4完了率差。単位はパーセントポイント" viewBox="0 0 800 310">'
             '<title>Type4完了率差 P2-L15 − B3</title><text x="350" y="22">0 %pt</text><line x1="380" y1="30" x2="380" y2="290" stroke="#617380"/>' + ''.join(ticks) + '</svg>')
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>常総市JDRT v2 中核比較</title>
<style>body{{margin:0;background:#f3f6f9;color:#183243;font:15px/1.8 system-ui,sans-serif}}main{{max-width:1400px;margin:auto;padding:28px}}h1{{font-size:28px}}h2{{margin-top:32px}}.note{{background:white;border-left:4px solid #247a82;padding:16px 22px}}.scroll{{overflow:auto;background:white;border:1px solid #d8e1e8;margin:18px 0}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{padding:9px 12px;white-space:nowrap;text-align:right;border-bottom:1px solid #e1e8ed}}th{{background:#e6eef3}}td:first-child{{text-align:left}}a{{color:#146583}}svg{{display:block;background:white;max-width:850px;width:100%;margin:18px 0}}svg text{{font-size:16px;fill:#183243}}</style></head><body><main>
<h1>常総市JDRT v2 中核比較</h1><p>全{len(rows)}採用セル・対応5seed。PAP v1第9〜12節をv2へ継承した主比較。</p>
<p><a href="JDRT-v2_全セル結果一覧.html">全セル技術検証一覧</a> / <a href="{PREFIX}_報告.md">定義・欠損・限界を含む報告書</a> / <a href="{PREFIX}_manifest.json">出典と出力SHA</a></p>
<div class="note">主比較は{escape(heading)}。Type4母数{parameters["population"]["type4"]}人、DRT対象全体{parameters["population"]["drt_eligible"]}人。人口全体の完了率とは区別します。v1・REAL-R0・Phase 3・Scenario Cは含みません。5seedの記述比較であり、現実の政策効果や他地域へ一般化しません。</div>
<h2>同一seedの主比較</h2>{chart}{primary_table}
<h2>対応差の中央値・最小・最大・符号</h2>{summary_table}
<h2>完了率・成功者時間・観測要求の待ち</h2>
<p>P95は安全な避難所で降車完了した成功者のみの時刻（秒、最近順位法）。待ちは要求発生から乗車完了までの要求別中央値で、乗車作業300秒を含みます。未乗車はnullで0秒や終了時刻に置換しません。両方式の成功者・乗車者の構成は異なり得ます。</p>{cells_table}
<h2>取得データと不足</h2><p>人物・要求ID/静的属性の同一性、人物/要求/車両会計、全理由付き未完了、成功者P95、対応差、出力CSV、分析前後の全採用run SHAを再計算・照合しました。取得成功と仮説支持は区別します。</p>
<p>Feasibility Gateの候補別拒否数/理由と、全車両の閉鎖後進入は既存ログから直接復元できません。未完了理由やteleport 0による代用はしません。mesh/個人表と登録方式間の補助差は探索的・記述的資料です。新しい計測や感度runは別途事前登録する対象です。</p>
<p>各CSVの定義、全成果物と再現コマンドは<a href="{PREFIX}_報告.md">報告書</a>に記録しています。既存Phase 3のヌル結論は変更しません。</p></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(generate(args.project_root.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
