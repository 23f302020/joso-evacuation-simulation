# テスト結果 Phase 2

作成日：2026/05/14  
対象：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）実装一式

---

## 1. 結論

Phase 2 実装の再実行テストは **合格** とする。

- Python構文チェック：合格
- SUMO / TraCI 環境検出：合格
- SUMOネットワーク変換：合格
- Phase 1 edge ID と SUMO edge ID 対応：合格
- 派生データ生成：合格
- 出発地・避難所のSUMO edgeスナップ：合格
- 小規模、1/10、全量のroute/config生成：合格
- 小規模SUMO閉鎖なし実行：合格
- 小規模、1/10、全量のTraCI動的閉鎖実行：合格
- 評価CSV生成：合格
- Phase 1 / Phase 2 / Phase 3別トップページ生成：合格

ブロッキングエラーは残っていない。

---

## 2. 修正したエラー・改善点

### 2.1 SUMO_HOME未設定時のimport失敗

初回テストで、`p2_sumo_snap.py --help` が次のエラーで失敗した。

```text
ModuleNotFoundError: No module named 'sumolib'
```

原因は、SUMO導入済みであっても現在のPowerShellプロセスに `SUMO_HOME` が引き継がれていない場合、`SUMO_HOME/tools` が `sys.path` に追加されず、`sumolib` をimportできないためである。

対応として、`04_プログラム/scripts/p2_sumo_env.py` を追加した。  
`SUMO_HOME` が未設定の場合でも、今回導入したSUMO 1.26.0の既定パスを自動検出し、`tools` と `bin` を現在プロセスへ追加する。

修正対象：

- `04_プログラム/scripts/p2_sumo_env.py` を追加
- `04_プログラム/scripts/p2_sumo_network.py`
- `04_プログラム/scripts/p2_sumo_snap.py`
- `04_プログラム/scripts/p2_sumo_scenario.py`
- `04_プログラム/scripts/p2_traci_closure.py`

修正後、`p2_sumo_snap.py --help`、`p2_sumo_scenario.py --help`、`p2_traci_closure.py --help` はすべて成功した。

---

## 3. テスト環境

| 項目 | 値 |
|---|---|
| OS | Windows |
| Python | `04_プログラム/venv/Scripts/python.exe` |
| SUMO | Eclipse SUMO sumo 1.26.0 |
| SUMO_HOME | `C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo` |
| `sumolib` | `SUMO_HOME/tools/sumolib` |
| `traci` | `SUMO_HOME/tools/traci` |

---

## 4. 実行テスト一覧

| ID | テスト | 結果 | 実行時間 | 確認内容 |
|---|---|---:|---:|---|
| T01 | `python -m py_compile` | ✅ | - | Phase 2スクリプト8件の構文チェック成功 |
| T02 | SUMO自動検出・`sumolib` / `traci` import | ✅ | - | `p2_sumo_env.py` 経由でSUMO 1.26.0を検出 |
| T03 | `p2_sumo_network.py inspect` | ✅ | 3.27秒 | GraphML属性確認を再実行 |
| T04 | `p2_sumo_network.py netconvert` | ✅ | 10.95秒 | `joso.net.xml` を再生成 |
| T05 | `p2_sumo_mapping.py all` | ✅ | 3.22秒 | edge対応表と検証JSONを再生成 |
| T06 | `p2_derived_data.py all` | ✅ | 1.19秒 | 時間軸・避難所安全性・車両台数を再生成 |
| T07 | `p2_sumo_snap.py all` | ✅ | 17.69秒 | 出発地・避難所のSUMO edgeスナップを再生成 |
| T08 | `p2_sumo_scenario.py small` | ✅ | 4.49秒 | 小規模route/configを再生成 |
| T09 | `p2_sumo_scenario.py 10pct` | ✅ | 4.44秒 | 1/10 route/configを再生成 |
| T10 | `p2_sumo_scenario.py full` | ✅ | 4.75秒 | 全量route/configを再生成 |
| T11 | `p2_sumo_scenario.py run-small` | ✅ | 56.15秒 | 小規模閉鎖なしSUMO実行成功 |
| T12 | `p2_traci_closure.py closure-json` | ✅ | 1.79秒 | SUMO edge閉鎖タイムラインを再生成 |
| T13 | `p2_traci_closure.py run-small` | ✅ | 87.03秒 | 小規模TraCI動的閉鎖実行成功 |
| T16 | `p2_traci_closure.py run-10pct` | ✅ | 79.14秒 | 1/10 TraCI動的閉鎖実行成功 |
| T17 | `p2_traci_closure.py run-full` | ✅ | 196.26秒 | 全量TraCI動的閉鎖実行成功 |
| T18 | `p2_evaluate_results.py all` | ✅ | 1.38秒 | 評価CSVと卒論用表テンプレートを再生成 |
| T19 | `gen_index.py` | ✅ | 0.16秒 | Phase 1/2/3別トップページを再生成 |
| T20 | Edge headless screenshot | ✅ | - | `output/index.html` の画面描画を確認 |

---

## 5. 主要検証値

### 5.1 SUMOネットワーク

| 項目 | 値 |
|---|---:|
| 通常edge数 | 49,356 |
| internal edge数 | 86,841 |
| junction数 | 34,124 |
| connection数 | 178,721 |

### 5.2 edge対応

| 項目 | 値 |
|---|---:|
| Phase 1閉鎖edge数 | 764 |
| matched | 764 |
| unmatched | 0 |
| 対応SUMO edge segment数 | 3,158 |
| TraCI閉鎖へ進行可能 | true |

### 5.3 派生データ

| 項目 | 値 |
|---|---:|
| 時間軸行数 | 8 |
| t0 SUMO秒 | 789 |
| t7 SUMO秒 | 21,600 |
| 避難所数 | 19 |
| 安全目的地数 | 19 |
| 出発地メッシュ数 | 40 |
| 小規模車両数 | 40 |
| 1/10車両数 | 120 |
| 全量車両数 | 1,001 |

### 5.4 スナップ検査

| 項目 | 値 |
|---|---:|
| 出発地matched | 40 / 40 |
| 出発地最大スナップ距離 | 468.839m |
| 安全避難所matched | 19 / 19 |
| 安全避難所最大スナップ距離 | 103.35m |
| route生成へ進行可能 | true |

### 5.5 TraCI実行結果

| ケース | 車両数 | 出発台数 | 到着台数 | 未到着 | 出発edge閉鎖 | 逃げ遅れ主指標 | 閉鎖イベント | 最終累積閉鎖SUMO edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small | 40 | 40 | 40 | 0 | 0 | 0 | 8 | 3,158 |
| 1/10 | 120 | 120 | 120 | 0 | 0 | 0 | 8 | 3,158 |
| full | 1,001 | 987 | 987 | 14 | 14 | 14 | 8 | 3,158 |

### 5.6 評価CSV

| ファイル | 行数 |
|---|---:|
| `output/sumo/evaluation/evacuation_summary.csv` | 3 |
| `output/sumo/evaluation/congestion_log.csv` | 1,080 |
| `output/sumo/evaluation/phase1_phase2_comparison.csv` | 11 |
| `output/sumo/derived/scenario_a_small_vehicle_assignments.csv` | 40 |
| `output/sumo/derived/scenario_a_10pct_vehicle_assignments.csv` | 120 |
| `output/sumo/derived/scenario_a_vehicle_assignments.csv` | 1,001 |

---

## 6. 注意点・今後の改善候補

### 6.1 SUMO teleport警告

全量TraCI実行中に、SUMOのteleport警告が複数出力された。  
これは渋滞・車線遷移・閉鎖後の経路制約によりSUMOが車両を移動させる内部処理であり、今回の実行ではプロセス停止には至っていない。

卒論上は、到着/未到着、出発edge閉鎖、逃げ遅れ主指標を主要評価値とし、teleport警告は交通流モデル上の制約として注記する。

### 6.2 全量ケースの未到着14台

全量ケースの未到着14台は、すべて `departure_blocked_by_closure=true` として記録されている。  
これは閉鎖済みの出発edgeから発車できなかった車両であり、動的閉鎖の影響として妥当な記録である。

### 6.3 残る改善候補

- Phase 2本文ドラフトで、Phase 1の静的到達不可とPhase 2の動的逃げ遅れの単位差を明記する。
- SUMO teleport警告の意味と、評価値への扱いを論文注記に入れる。
- 将来の感度分析として、出発時刻の30分分散、車両台数換算係数、避難所選択ルールの変更を追加できる。

---

## 7. 最終判定

Phase 2実装は、現時点のシナリオA（自家用車のみ）について再実行可能であり、主要出力も仕様と一致した。  
テスト中に見つかった `SUMO_HOME` 未設定時のimport失敗は修正済みである。

したがって、Phase 2実装テストは **完了** とする。

---

## 8. P2-IMPL-VIZ テスト（FCD可視化実装）

追加日：2026/05/14  
対象：`p2_sumo_scenario.py` FCD出力設定追加・`p2_fcd_to_json.py` 新規作成・`gen_index.py` 更新

### 8.1 テスト一覧

| ID | テスト | 結果 | 確認内容 |
|---|---|---:|---|
| T21 | `p2_sumo_scenario.py` FCD出力設定確認 | ✅ | `generate_scenario()` が `fcd-output`, `fcd-output.period`, `fcd-output.geo` 要素を sumocfg に出力することを確認（構文チェック + コードレビュー） |
| T22 | `p2_fcd_to_json.py` 構文チェック | ✅ | `python -m py_compile` 合格 |
| T23 | `p2_fcd_to_json.py sample` 実行 | ✅ | `vehicles_small.js`（23 KB）、`closures.js`（0 KB）、`viz_meta.js`（0 KB）、`sumo_viz.html`（6.9 KB）が `output/sumo/viz/` に生成されることを確認 |
| T24 | `gen_index.py` 実行 | ✅ | `phase1-pages.js` の `phase2` 配列に `SUMO走行アニメーション / sumo/viz/sumo_viz.html` が追加されることを確認 |

### 8.2 生成ファイル

| ファイル | サイズ | 内容 |
|---|---:|---|
| `output/sumo/viz/vehicles_small.js` | 23 KB | 10台のサンプル車両位置時系列（`window.VIZ_VEHICLES_SMALL`） |
| `output/sumo/viz/closures.js` | <1 KB | サンプル閉鎖エッジ2イベント（`window.VIZ_CLOSURES`） |
| `output/sumo/viz/viz_meta.js` | <1 KB | シナリオ名・地図中心・シミュレーション秒数（`window.VIZ_META`） |
| `output/sumo/viz/sumo_viz.html` | 6.9 KB | Leaflet.js地図 + 車両アニメーション + タイムラインスライダー |

### 8.3 備考

- T23 は `sample` コマンドで実行するため SUMO インストール不要（sumolib は import されるが実使用しない）。
- `vehicles_10pct.js` の生成（VIZ-8）は FCD 付き TraCI 実行後に `p2_fcd_to_json.py vehicles-10pct` で実施する。
- FCD 付き sumocfg の実際の動作確認（VIZ-2: FCD XML 生成）は TraCI 再実行時に合わせて実施する。

### 8.4 追加判定

P2-IMPL-VIZ のうち VIZ-1、VIZ-3〜VIZ-7 の実装とサンプル動作確認は **合格** とする。  
VIZ-2（FCD付きTraCI再実行）および VIZ-8（10pct拡張）は FCD XMLが存在する段階で実施する。
