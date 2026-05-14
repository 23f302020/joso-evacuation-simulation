# Phase 2 SUMO導入・変換手順

作成日：2026/05/14  
対象：Windows環境 / SUMO 1.26.0 / 常総市実データ版

---

## 1. 採用方針

Phase 2では、SUMO公式配布のWindows 64-bit版を導入する。

| 項目 | 採用内容 |
|---|---|
| SUMO本体 | Eclipse SUMO 1.26.0 |
| 導入方法 | 公式Windows 64-bit MSIを優先 |
| MSIが使えない場合 | 公式Windows 64-bit ZIPを展開して利用 |
| Python連携 | `SUMO_HOME/tools` を `sys.path` に追加して `traci` / `sumolib` を利用 |
| 初期対象 | 常総市実データ版 |

判断理由：

- 公式MSIは `sumo`, `sumo-gui`, `netconvert`, `netedit` をまとめて導入できる。
- `pip install traci` ではSUMO本体とのバージョンずれが起きる可能性がある。
- `SUMO_HOME/tools` を参照する方法なら、SUMO本体とPython APIの対応を保てる。

---

## 2. 2026/05/14 導入結果

公式Windows 64-bit MSIの通常サイレントインストールは `1603` で失敗したため、同じMSIをユーザー領域へ管理展開した。

| 項目 | 結果 |
|---|---|
| 通常MSIインストール | 失敗（exit code `1603`） |
| 採用した導入方法 | 公式MSIの管理展開 |
| 実際の `SUMO_HOME` | `C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo` |
| PATH追加 | `%SUMO_HOME%\bin` をユーザーPATHへ追加 |
| Python API | `%SUMO_HOME%\tools` から `traci` / `sumolib` import確認済み |
| ZIPフォールバック | 今回の試行ではZIPダウンロードがタイムアウトで不完全だったため不採用 |

確認済みコマンド：

```text
Eclipse SUMO sumo 1.26.0
Eclipse SUMO GUI 1.26.0
Eclipse SUMO netconvert 1.26.0
Eclipse SUMO netedit 1.26.0
traci ok
sumolib ok
```

補足：既存のPowerShellやCodexプロセスでは、ユーザーPATHの変更が即時反映されない場合がある。その場合は、新しいターミナルを開くか、実行時に `SUMO_HOME` と `%SUMO_HOME%\bin` を明示する。

---

## 3. 導入後に必要な環境変数

| 変数 | 値 |
|---|---|
| `SUMO_HOME` | SUMOのインストール先 |
| `PATH` | `%SUMO_HOME%\bin` を追加 |

今回の実インストール先：

```text
C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo
```

公式MSIの通常インストールが使える環境での想定インストール先：

```text
C:\Program Files (x86)\Eclipse\Sumo
```

MSIの導入先が異なる場合は、実際の `sumo.exe` の親フォルダに合わせる。

---

## 4. 導入確認コマンド

PowerShellで次を確認する。

```powershell
sumo --version
sumo-gui --version
netconvert --version
netedit --version
```

Python仮想環境からは次を確認する。

```powershell
.\04_プログラム\venv\Scripts\python.exe -c "import os, sys; sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools')); import traci, sumolib; print('traci/sumolib ok')"
```

---

## 5. Phase 2用ディレクトリ

| ディレクトリ | 内容 |
|---|---|
| `04_プログラム/output/sumo/network/` | `joso.osm.xml`, `joso.net.xml` |
| `04_プログラム/output/sumo/derived/` | 派生CSV / JSON |
| `04_プログラム/output/sumo/scenarios/` | SUMO route / config XML |
| `04_プログラム/output/sumo/results/` | 実行結果CSV |

---

## 6. 変換手順の全体像

| 手順 | 入力 | 出力 | 目的 |
|---|---|---|---|
| 1 | `joso_road_network.graphml` | `joso.osm.xml`, `phase1_edge_osm_way_mapping.csv` | OSMnxエッジをOSM wayとして出力し、Phase 1 edge ID → way ID の対応を記録 |
| 2 | `joso.osm.xml` | `joso.net.xml` | `netconvert` でSUMOネットワークへ変換 |
| 3 | `phase1_edge_osm_way_mapping.csv`, `joso.net.xml` | `edge_id_mapping.csv` | way ID経由でPhase 1 edge IDとSUMO edge IDを対応 |
| 4 | `road_closure_timeline.json`, `edge_id_mapping.csv` | `closure_timeline_sumo.json` | TraCI閉鎖用ファイルへ変換 |
| 5 | `origin_points.csv`, `joso.net.xml` | `agent_origins_sumo.csv` | 出発地をSUMO edgeへスナップ |
| 6 | `shelters_safety.csv`, `joso.net.xml` | `shelters_sumo.csv` | 安全避難所をSUMO edgeへスナップ |
| 7 | `agent_origins_sumo.csv`, `shelters_sumo.csv` | `scenario_a_small.rou.xml` | 小規模テスト用ルート作成 |

---

## 7. `netconvert` 初期候補

初回は、変換成功とedge ID対応の確認を優先する。

```powershell
netconvert --osm-files 04_プログラム\output\sumo\network\joso.osm.xml --output-file 04_プログラム\output\sumo\network\joso.net.xml --geometry.remove --roundabouts.guess --ramps.guess
```

補足：

- 変換後にedge分割や内部edgeが発生するため、Phase 1 edge IDとの対応表作成を必ず行う。
- `--geometry.remove` などのオプションは初期候補であり、形状確認後に調整する。

---

## 8. 導入後に最初に確認すること

| 確認 | 通過条件 |
|---|---|
| `sumo --version` | 1.26.0 が表示される |
| `netconvert --version` | 1.26.0 が表示される |
| Python import | `traci/sumolib ok` が表示される |
| GUI起動 | `sumo-gui` が起動できる |
| 変換準備 | `04_プログラム/output/sumo/` 以下の作業ディレクトリが作れる |

---

## 9. 実装へ入る前の停止条件

次のいずれかに該当する場合、TraCI動的閉鎖の実装へ進まず、先に設計または変換手順を修正する。

| 停止条件 | 理由 |
|---|---|
| SUMOコマンドがPATHから呼べない | 実行環境が固定できていない |
| `traci` / `sumolib` を読み込めない | 動的制御スクリプトを実行できない |
| `edge_id_mapping.csv` に未対応閉鎖edgeが残る | 間違った道路を閉鎖する危険がある |
| 安全避難所が0件になる | Phase 2の目的地が成立しない |
| 出発地または避難所のSUMO edgeスナップに失敗する | ルート生成が成立しない |
