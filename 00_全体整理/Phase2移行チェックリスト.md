# Phase 2 移行チェックリスト

> 作成日：2026/05/12  
> 目的：Phase 1 完了後、SUMO/TraCI を使った Phase 2 へ移る前に確認する項目をまとめる。

---

## 1. Phase 1 完了条件

| 項目 | 状態 | 確認先 |
|---|---:|---|
| 茨城県内41市区町村の市別HTML生成 | ✅ | `04_プログラム/output/scenario_cities/` |
| 統合シミュレーションの41市区町村対応 | ✅ | `04_プログラム/output/unified/scenario_route_simulation.html` |
| 対象外3市町村の整理 | ✅ | `06_研究結果/phase1/Phase1_対象外市町村の除外原因分析.md` |
| 鬼怒川レイヤー表示 | ✅ | `04_プログラム/output/unified/assets/kinugawa_river.js` |
| 最終テスト記録 | ✅ | `04_プログラム/テスト結果_phase1/テスト結果_phase1_final_20260512.md` |
| 出力HTML/JS/CSSの旧表記除去 | ✅ | 最終テスト記録に記載 |

---

## 2. Phase 2 最初の対象範囲

Phase 2 は、まず **常総市実データ版** を対象とする。

理由は次の通り。

| 観点 | 判断 |
|---|---|
| データの揃い方 | 常総市は道路NW、閉鎖タイムライン、出発地、避難所が揃っている |
| 実災害との関係 | 2015年鬼怒川氾濫の中心事例である |
| SUMO化の負荷 | 茨城県41市区町村全体より小さく、初回検証に向く |
| Phase 3への接続 | 車避難のベースラインとして使える |

---

## 3. Phase 2 必須タスク

| 順序 | タスク | 出力・確認 |
|---:|---|---|
| 1 | SUMO本体のインストール確認 | `sumo`、`sumo-gui`、`netconvert`、`netedit` が実行可能 |
| 2 | `SUMO_HOME` とPATH設定 | PowerShellからSUMOコマンドを実行可能 |
| 3 | Pythonから `traci` / `sumolib` を利用できるか確認 | import確認 |
| 4 | 常総市道路NWをSUMO形式へ変換 | `joso.net.xml` |
| 5 | Phase 1の閉鎖エッジIDとSUMO edge IDの対応確認 | 対応表または変換ログ |
| 6 | 小規模車両エージェントで走行テスト | 最小 `.rou.xml`、`.sumocfg` |
| 7 | `road_closure_timeline.json` をSUMO時刻へ対応 | 時刻マッピング表 |
| 8 | TraCIで動的道路閉鎖を実装 | 閉鎖ログ |
| 9 | 逃げ遅れ・完走・平均速度を出力 | CSV |

---

## 4. Phase 2 で使う主なPhase 1成果物

| 用途 | ファイル |
|---|---|
| 常総市道路NW | `04_プログラム/output/network/joso_road_network.graphml` |
| 道路エッジ確認 | `04_プログラム/output/network/joso_edges.gpkg` |
| 道路閉鎖時系列 | `04_プログラム/output/closure/road_closure_timeline.json` |
| 出発地 | `04_プログラム/output/agents/origin_points.csv` |
| 避難所 | `04_プログラム/output/agents/shelters.csv` |
| 到達不可結果 | `04_プログラム/output/routes/unreachable_agents.csv` |

---

## 5. Phase 2 の最小成功条件

Phase 2 の最小成功条件は、次の3点とする。

| 条件 | 内容 |
|---|---|
| 1 | 常総市道路ネットワークをSUMOで読み込める |
| 2 | 車両エージェントが避難所方向へ走行する |
| 3 | TraCIにより時刻別道路閉鎖を反映し、逃げ遅れ・完走結果をCSV出力できる |

この3点が成立すれば、Phase 3 のデマンド交通・バス比較に進むための自家用車避難ベースラインになる。
