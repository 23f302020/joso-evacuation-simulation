# Phase 2 実装タスク管理

> 作成日：2026/05/14  
> 目的：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）の実装作業を、実行可能な粒度まで分割して管理する。  
> 関連：`Phase2_詳細タスク管理.md`、`Phase2_判断事項一覧.md`、`03_研究設計文書/phase2/Phase2_実装前仕様.md`  
> 進捗記録先：`01_経過報告/経過報告20260520.md`

---

## 1. 実装対象

Phase 2では、まず常総市実データ版を対象に、シナリオA（自家用車のみ）の交通流ベースラインを作る。

Phase 3で扱うバス・デマンド交通は、この実装タスク管理には含めない。

---

## 2. 凡例

| マーク | 意味 |
|---|---|
| ✅ | 完了 |
| 🔄 | 作業中 |
| ❌ | 未着手 |
| ⏸ | 依存タスク待ち |
| 🔴 | 停止条件・要確認 |

---

## 3. 実装マイルストーン

| マイルストーン | 内容 | 状態 | 主な成果物 |
|---|---|---:|---|
| P2-IMPL-0 | 実装環境・作業ディレクトリ準備 | ✅ | SUMO 1.26.0、`output/sumo/` |
| P2-IMPL-1 | SUMO道路ネットワーク変換 | ❌ | `joso.osm.xml`, `joso.net.xml` |
| P2-IMPL-2 | Phase 1 edge ID と SUMO edge ID の対応 | ❌ | `edge_id_mapping.csv` |
| P2-IMPL-3 | 派生データ生成 | ❌ | `shelters_safety.csv`, `agent_origins_10pct.csv`, `time_mapping_sumo.csv` |
| P2-IMPL-4 | SUMO出発地・避難所スナップ | ⏸ | `agent_origins_sumo.csv`, `shelters_sumo.csv` |
| P2-IMPL-5 | 小規模シナリオA route/config生成 | ⏸ | `scenario_a_small.rou.xml`, `scenario_a_small.sumocfg` |
| P2-IMPL-6 | TraCI動的道路閉鎖 | ⏸ | `run_scenario_a_traci.py`, `closure_log.csv` |
| P2-IMPL-7 | 1/10試行・全量試行 | ⏸ | `scenario_a_10pct.*`, `scenario_a.*` |
| P2-IMPL-8 | 評価CSV・比較表生成 | ⏸ | `evacuation_summary.csv`, `phase1_phase2_comparison.csv` |
| P2-IMPL-9 | 成果物トップページ更新 | ⏸ | Phase 1/2/3別 `index.html` |

---

## 4. P2-IMPL-0：環境・作業ディレクトリ

| ID | タスク | 状態 | 成果物・確認 |
|---|---|---:|---|
| P2-IMPL-0-1 | SUMO 1.26.0を導入する | ✅ | 公式MSIをユーザー領域へ管理展開 |
| P2-IMPL-0-2 | `SUMO_HOME` を設定する | ✅ | `C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo` |
| P2-IMPL-0-3 | `sumo`, `sumo-gui`, `netconvert`, `netedit` を確認する | ✅ | 各 `--version` で 1.26.0 |
| P2-IMPL-0-4 | `traci` / `sumolib` importを確認する | ✅ | `SUMO_HOME/tools` 経由で成功 |
| P2-IMPL-0-5 | SUMO用出力ディレクトリを作成する | ✅ | `network`, `derived`, `scenarios`, `results` |

---

## 5. P2-IMPL-1：SUMO道路ネットワーク変換

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-1-1 | `joso_road_network.graphml` のノード・エッジ属性を確認する | ❌ | P2-IMPL-0 | 属性確認メモ | `u`, `v`, `key`, `osmid`, `geometry`, `length` の有無 |
| P2-IMPL-1-2 | GraphMLからOSM XMLへ変換する方針を実装に落とす | ❌ | 1-1 | 変換スクリプト案 | ID保持方法が明記されている |
| P2-IMPL-1-3 | `joso.osm.xml` を生成する | ❌ | 1-2 | `output/sumo/network/joso.osm.xml` | XMLとして読める |
| P2-IMPL-1-4 | `netconvert` で `joso.net.xml` を生成する | ❌ | 1-3 | `output/sumo/network/joso.net.xml` | `netconvert` がエラー終了しない |
| P2-IMPL-1-5 | `sumo-gui` または `netedit` でネットワークを確認する | ❌ | 1-4 | 確認メモ | 道路が空でない、常総市周辺に表示される |

停止条件：

- `joso.net.xml` が生成できない場合は、route生成へ進まない。
- 変換時に元IDを追跡できない場合は、edge ID対応表の方針を修正する。

---

## 6. P2-IMPL-2：edge ID対応

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-2-1 | SUMO edge一覧を抽出する | ❌ | P2-IMPL-1 | `sumo_edges.csv` | edge数・ID形式を確認 |
| P2-IMPL-2-2 | Phase 1閉鎖edge一覧を抽出する | ❌ | Phase 1出力 | `phase1_closed_edges.csv` | t0〜t7の閉鎖edgeを重複なしで整理 |
| P2-IMPL-2-3 | `edge_id_mapping.csv` を生成する | ❌ | 2-1,2-2 | `output/sumo/derived/edge_id_mapping.csv` | `mapping_status` を付与 |
| P2-IMPL-2-4 | 未対応・曖昧対応edgeを検査する | ❌ | 2-3 | 検査ログ | 閉鎖対象edgeの未対応が0件 |
| P2-IMPL-2-5 | 必要なら手動確認結果を追記する | ⏸ | 2-4 | 更新済み対応表 | `manual_checked` を記録 |

停止条件：

- 閉鎖対象edgeに `unmatched` が残る場合、TraCI閉鎖実装へ進まない。

---

## 7. P2-IMPL-3：派生データ生成

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-3-1 | `time_mapping_sumo.csv` を生成する | ❌ | 実装前仕様 | `output/sumo/derived/time_mapping_sumo.csv` | t0=789、t7=21600 |
| P2-IMPL-3-2 | 避難所浸水リスクを判定する | ❌ | A31a, shelters | `shelters_safety.csv` | 安全目的地が1件以上 |
| P2-IMPL-3-3 | 人口メッシュから車両台数を算出する | ❌ | origin_points | `agent_origins_10pct.csv` | 人口ありメッシュの小規模台数が1 |
| P2-IMPL-3-4 | 派生データの列・件数を仕様書と照合する | ❌ | 3-1〜3-3 | 検査ログ | 欠損・型不一致がない |

---

## 8. P2-IMPL-4：SUMO edgeへのスナップ

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-4-1 | 出発地メッシュをSUMO edgeへスナップする | ⏸ | P2-IMPL-1,3 | `agent_origins_sumo.csv` | `unmatched` が0件 |
| P2-IMPL-4-2 | 安全避難所をSUMO edgeへスナップする | ⏸ | P2-IMPL-1,3 | `shelters_sumo.csv` | 採用避難所の `unmatched` が0件 |
| P2-IMPL-4-3 | スナップ距離の外れ値を確認する | ⏸ | 4-1,4-2 | 外れ値メモ | 遠すぎる点を手動確認 |

---

## 9. P2-IMPL-5：小規模シナリオA route/config生成

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-5-1 | 小規模テスト用の車両ID規則を決める | ⏸ | P2-IMPL-4 | 実装メモ | メッシュIDと対応可能 |
| P2-IMPL-5-2 | `scenario_a_small.rou.xml` を生成する | ⏸ | 5-1 | route XML | XML妥当性、車両数確認 |
| P2-IMPL-5-3 | `scenario_a_small.sumocfg` を生成する | ⏸ | 5-2 | sumocfg | SUMOで読み込み可能 |
| P2-IMPL-5-4 | 小規模シナリオを閉鎖なしで実行する | ⏸ | 5-3 | 実行ログ | 車両が発生・走行・到着する |

---

## 10. P2-IMPL-6：TraCI動的道路閉鎖

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-6-1 | `closure_timeline_sumo.json` を生成する | ⏸ | P2-IMPL-2,3 | `closure_timeline_sumo.json` | `unmapped_phase1_edge_ids` が空 |
| P2-IMPL-6-2 | TraCI実行スクリプトを作成する | ⏸ | 6-1,5 | `run_scenario_a_traci.py` | SUMOが起動・終了する |
| P2-IMPL-6-3 | 指定時刻でedge閉鎖を実行する | ⏸ | 6-2 | `closure_log.csv` | t0〜t7の閉鎖件数が記録される |
| P2-IMPL-6-4 | 閉鎖後の再経路探索を実装する | ⏸ | 6-3 | ログ | reroute成功・失敗を記録 |
| P2-IMPL-6-5 | 到達不能・600秒停止を記録する | ⏸ | 6-4 | `vehicle_log.csv` | 主指標に必要な状態を出力 |

---

## 11. P2-IMPL-7：1/10試行・全量試行

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-7-1 | 1/10試行 route/config を生成する | ⏸ | P2-IMPL-6 | `scenario_a_10pct.*` | 車両数が仕様どおり |
| P2-IMPL-7-2 | 1/10試行を実行する | ⏸ | 7-1 | 実行ログ | 完走または停止理由を記録 |
| P2-IMPL-7-3 | 全量試行 route/config を生成する | ⏸ | 7-2 | `scenario_a.*` | 車両数が仕様どおり |
| P2-IMPL-7-4 | 全量試行を実行する | ⏸ | 7-3 | 実行ログ | 処理時間・メモリ負荷を記録 |

---

## 12. P2-IMPL-8：評価CSV・比較表

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-8-1 | `evacuation_summary.csv` を生成する | ⏸ | P2-IMPL-6 | summary CSV | 到着・未到着・逃げ遅れ台数 |
| P2-IMPL-8-2 | `congestion_log.csv` を生成する | ⏸ | P2-IMPL-6 | congestion CSV | 時刻別平均速度・停止台数 |
| P2-IMPL-8-3 | `phase1_phase2_comparison.csv` を生成する | ⏸ | 8-1 | 比較CSV | 静的到達不可と動的逃げ遅れを分けて記録 |
| P2-IMPL-8-4 | 卒論用表テンプレートへ反映する | ⏸ | 8-1〜8-3 | 表案 | 数値・注記を確認 |

---

## 13. P2-IMPL-9：成果物トップページ更新

| ID | タスク | 状態 | 依存 | 成果物 | 検証 |
|---|---|---:|---|---|---|
| P2-IMPL-9-1 | Phase 2成果物リンク構成を決める | ⏸ | P2-IMPL-8 | リンク案 | Phase 1/2/3が分かれる |
| P2-IMPL-9-2 | `gen_index.py` を更新する | ⏸ | 9-1 | 更新スクリプト | index再生成可能 |
| P2-IMPL-9-3 | `output/index.html` を更新する | ⏸ | 9-2 | index HTML | Phase別に確認できる |
| P2-IMPL-9-4 | ブラウザで導線確認する | ⏸ | 9-3 | 確認メモ | リンク切れがない |

---

## 14. 実装順序

1. P2-IMPL-1：SUMO道路ネットワーク変換
2. P2-IMPL-2：edge ID対応
3. P2-IMPL-3：派生データ生成
4. P2-IMPL-4：出発地・避難所スナップ
5. P2-IMPL-5：小規模route/config生成
6. P2-IMPL-6：TraCI動的閉鎖
7. P2-IMPL-7：1/10試行・全量試行
8. P2-IMPL-8：評価CSV・比較表
9. P2-IMPL-9：成果物トップページ更新

---

## 15. 最重要リスク

| リスク | 影響 | 対応 |
|---|---|---|
| Phase 1 edge ID と SUMO edge ID が対応しない | 誤った道路閉鎖になる | `edge_id_mapping.csv` を必須成果物にする |
| 出発地・避難所のスナップ失敗 | route生成不能 | `snap_status` を検査する |
| 安全避難所が0件になる | 避難目的地が成立しない | `shelters_safety.csv` 生成時に停止 |
| 車両数が多すぎて実行が重い | 全量試行が完走しない | 小規模→1/10→全量の順に進める |
| Phase 1とPhase 2の指標誤読 | 卒論の比較が不正確になる | 比較表に静的/動的の注記を付ける |
