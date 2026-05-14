# Phase 2 出力CSV仕様案

> 作成日：2026/05/14  
> 目的：Phase 2で出力するCSVの候補と列構成を、実装前に整理する。  
> 位置づけ：判断不要の下準備文書。最終的な指標定義は `Phase2_判断事項一覧.md` で確認する。

---

## 1. 出力方針

Phase 2では、まずCSVで出力する。

小規模テスト・1/10試行ではCSVで十分確認できる。  
全量実行でログ量が大きくなる場合は、SQLiteやGeoPackageへの移行を検討する。

---

## 2. `evacuation_summary.csv`

避難完了・未完了をシナリオ単位で集計する。

| 列 | 内容 |
|---|---|
| `scenario_id` | シナリオID。例：`small`, `scenario_a_10pct`, `scenario_a_full` |
| `run_id` | 実行ID |
| `vehicle_count` | 投入車両数 |
| `departed_count` | 出発済み車両数 |
| `arrived_count` | 避難所へ到着した車両数 |
| `not_arrived_count` | 終了時点で未到着の車両数 |
| `stranded_count` | 逃げ遅れ判定された車両数 |
| `mean_travel_time_sec` | 到着車両の平均移動時間 |
| `median_travel_time_sec` | 到着車両の中央値移動時間 |
| `mean_speed_mps` | 全体平均速度 |
| `simulation_end_sec` | シミュレーション終了秒 |
| `notes` | 補足 |

---

## 3. `vehicle_log.csv`

車両単位の最終状態を出力する。

| 列 | 内容 |
|---|---|
| `run_id` | 実行ID |
| `vehicle_id` | SUMO車両ID |
| `origin_key` | 出発地メッシュID |
| `origin_lon` | 出発地経度 |
| `origin_lat` | 出発地緯度 |
| `destination_name` | 目的地避難所名 |
| `depart_sec` | 出発秒 |
| `arrival_sec` | 到着秒。未到着なら空欄 |
| `travel_time_sec` | 移動時間 |
| `status` | `arrived`, `not_arrived`, `stranded`, `rerouted` など |
| `stranded_reason` | 逃げ遅れ理由。例：`no_route`, `stopped_long`, `in_flood_area` |
| `final_edge_id` | 最終的にいたSUMO edge ID |
| `final_lon` | 最終位置経度 |
| `final_lat` | 最終位置緯度 |

---

## 4. `closure_log.csv`

TraCIで道路閉鎖を反映したログを出力する。

| 列 | 内容 |
|---|---|
| `run_id` | 実行ID |
| `sim_time_sec` | SUMO上の時刻秒 |
| `phase_time_id` | t0〜t7 |
| `source_timestamp` | Phase 1の元時刻 |
| `phase1_edge_id` | Phase 1の閉鎖エッジID |
| `sumo_edge_id` | SUMOのedge ID |
| `action` | `closed`, `already_closed`, `missing_mapping` など |
| `affected_vehicle_count` | その時点で影響を受けた車両数 |

---

## 5. `congestion_log.csv`

時刻別・エッジ別の速度や停止状況を出力する。

| 列 | 内容 |
|---|---|
| `run_id` | 実行ID |
| `sim_time_sec` | SUMO上の時刻秒 |
| `sumo_edge_id` | SUMO edge ID |
| `mean_speed_mps` | 平均速度 |
| `vehicle_count` | 当該エッジ上の車両数 |
| `halting_vehicle_count` | 停止車両数 |
| `occupancy` | 占有率。取得可能な場合 |
| `is_closed` | 閉鎖済みか |

---

## 6. `phase1_phase2_comparison.csv`

Phase 1の静的結果とPhase 2の動的結果を比較する。

| 列 | 内容 |
|---|---|
| `time_id` | t0〜t7、または比較対象の時点 |
| `phase1_unreachable_mesh_count` | Phase 1到達不可メッシュ数 |
| `phase1_unreachable_population` | Phase 1到達不可人口 |
| `phase1_closed_edge_count` | Phase 1閉鎖エッジ数 |
| `phase2_vehicle_count` | Phase 2投入車両数 |
| `phase2_arrived_count` | Phase 2到着車両数 |
| `phase2_stranded_count` | Phase 2逃げ遅れ車両数 |
| `phase2_mean_travel_time_sec` | Phase 2平均移動時間 |
| `interpretation` | 比較上のメモ |

---

## 7. 今後追加する可能性がある出力

| ファイル | 内容 |
|---|---|
| `edge_id_mapping.csv` | Phase 1 edge ID と SUMO edge ID の対応 |
| `time_mapping_sumo.csv` | t0〜t7とSUMO秒の対応 |
| `shelters_safety.csv` | 避難所の浸水リスク判定 |
| `agent_origins_sumo.csv` | 出発地をSUMO edgeへスナップした結果 |
| `shelters_sumo.csv` | 避難所をSUMO edgeへスナップした結果 |

---

## 8. 未決事項

| 項目 | 判断が必要な内容 |
|---|---|
| 逃げ遅れ定義 | `stranded_count` に何を含めるか |
| 時間軸 | 実時間か6時間圧縮か |
| 保存形式 | CSVのみか、SQLite併用か |
| 車両単位 | 1メッシュ1台、人口換算、世帯換算のどれか |

