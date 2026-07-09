# Phase 3 B系 乗降検証スモーク（p2_traci_bus.py smoke-bus）

> **2026-07-09追記：** 本メモのBLOCKED結論は、WSL/Windows SUMO接続問題が残っていた時点の履歴である。その後、PowerShell実行・パス変換・SUMO binary解決を修正し、乗降検証は完走済み。最新結果は `04_プログラム/テスト結果/phase3/B系_常総full再実行_20260709.md` を正とする。最新のバス単独検証では5台・候補247人・乗車215人・到着215人・未到着0人・`conservation_ok=true`、full交通同時実行では乗車91人・到着67人・未到着24人・`conservation_ok=true`。full交通のdespawn 3便は到着扱いしない。

**対象：** `04_プログラム/scripts/p2_traci_bus.py`（B-c本体・`run_traci_scenario_b`）
**目的：** `_Bc実装ブループリント_fable5.md` §5の「乗降検証スモーク」を実行し、不変条件I1〜I8（Σboarded=Σalight+…／queue非負／二重計上なし／JB-4／等）を実測値で検証する。
**実行担当：** Sonnet（コード変更なし。バグは修正せず報告のみ）
**結論：** **総合＝BLOCKED（未完走）。乗降会計ロジックの実測検証はできなかった。** 原因は2件とも環境／プロセス間通信の問題であり、`p2_traci_bus.py` の乗降会計ロジック（`board_passengers`/`alight_passengers`等 in `p3_bus_accounting.py`）自体の不具合ではない。

---

## 実行手順と結果

### (1) バス計画・バス停の生成 — PASS
```
SUMO_HOME="$SUMO_WIN" PYTHONPATH="$SUMO_WIN/tools" python3 scripts/p3_bus_scenario.py smoke --buses 1
```
- 正常終了。`output/sumo/derived/bus_plan.csv` に1行生成：
  ```
  priority_rank=1, bus_id=bus_std_1, bus_vtype=bus_standard, origin_id=origin_0023,
  pickup_stop_id=bs_origin_0023, shelter_id=shelter_019, shelter_stop_id=bs_shelter_shelter_019,
  bus_candidate_population=25, type4_no_car_elderly_pop=11
  ```
- 期待値の前提（設計書の「25人＝type3≈13＋mob1＋type4 11」）と整合する人数（25・type4=11）を確認。

### (2) 乗降検証スモーク（`p2_traci_bus.py smoke-bus --buses 1`）— **BLOCKED（2種の環境エラーで未完走）**

#### エラー1：`sumolib.checkBinary("sumo")` がWSL(Linux)環境で拡張子解決に失敗
コマンド`env SUMO_HOME="$SUMO_WIN" PYTHONPATH="$SUMO_WIN/tools" python3 scripts/p2_traci_bus.py smoke-bus --buses 1` をそのまま実行すると：
```
File "scripts/p2_traci_bus.py", line 329, in run_traci_scenario_b
    traci.start([sumo_binary, "-c", str(sumocfg), "--no-step-log", "true"])
  ...
FileNotFoundError: [Errno 2] No such file or directory: 'sumo'
```
- **原因（確認済み）：** SUMO同梱`sumolib.checkBinary()`（`$SUMO_WIN/tools/sumolib/__init__.py:60-61`）は `os.name == "nt"` の時だけ `.exe` を付与する。WSL上のPython（`os.name=="posix"`）では常に拡張子なし `"sumo"` を返すため、`$SUMO_HOME/bin/sumo.exe` しか存在しない環境では解決できない。
- **発生関数：** `p2_traci_bus.py:328` `sumo_binary = sumolib.checkBinary("sumo")`（`run_traci_scenario_b`内）。**同一パターンが既存 `p2_traci_closure.py:433` にも存在**（未検証・今回はp2_traci_bus.pyのみ対象）。
- **回避（テスト実行のみ・コード非変更）：** 環境変数 `SUMO_BINARY="$SUMO_WIN/bin/sumo.exe"` を明示指定すると`checkBinary`内の`envName`分岐で解決される。これで先へ進めた。

#### エラー2：`str(sumocfg)`（WSL POSIXパス）を Windows版 sumo.exe の引数にそのまま渡している
`SUMO_BINARY`指定後の再実行：
```
Error: Could not access configuration '/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム/output/sumo/scenarios/scenario_b_busonly.sumocfg'.
Quitting (on error).
...
traci.exceptions.FatalTraCIError: Could not connect in 1 tries
```
- **原因（直接検証済み）：** `p2_traci_bus.py:329` の `traci.start([sumo_binary, "-c", str(sumocfg), ...])` は `sumocfg`（`pathlib.Path`、WSL上でPOSIXパス）を`str()`化してそのままコマンドライン引数に渡す。Windows版`sumo.exe`はこのPOSIXパス文字列（`/mnt/c/...`）をWindowsパスとして解釈できず、設定ファイルを読めずに即終了する。
  - **再現・切り分け実験：** 同じ`sumo.exe`を同じPOSIXパスで直接シェルから起動 → 同一エラーメッセージを再現。`wslpath -w`でWindows形式（`C:\Users\...`）に変換した同じパスで起動 → **エラーなく正常終了（exit 0、9秒で完走）**。パス形式の問題であることを確定。
- **発生関数：** `run_traci_scenario_b`（`p2_traci_bus.py:303-329`）。

#### エラー2の切り分け用ラッパ（コード非変更・テストハーネスのみ）
上記2件はコードを一切変更せずに完走させることが目的で解決不能だったため、**`p2_traci_bus.py`は無変更のまま**、`traci.start`（ライブラリ関数）だけをテスト実行スクリプト側でパス変換ラップし、実際の乗降ロジックまで到達できるか検証した（このラッパはスクラッチパッドに置いた別ファイルであり、対象コードへの変更は一切ない）。

#### エラー3：WSL→Windows sumo.exe のTraCIソケット接続が拒否される（**最終ブロッカー・未解決**）
パス変換ラッパ適用後：
```
Could not connect to TraCI server at localhost:36013 [Errno 111] Connection refused
（1秒間隔で61回リトライ）
traci.exceptions.FatalTraCIError: Could not connect in 61 tries
```
- **切り分け結果：**
  - `tasklist.exe` で当該 `sumo.exe`（PID確認済み）が実際に起動・生存していることを確認。
  - `netstat.exe -ano` で該当PIDが `0.0.0.0:36013` を **LISTENING** していることを確認（＝SUMO側はTraCIサーバとして正常に待受け中）。
  - WSL側から同じポートへ生ソケットで直接接続を試行（`python3 socket.connect(('127.0.0.1', 36013))`）→ **`[Errno 111] Connection refused`**（traci以外の経路でも再現＝アプリ層の問題ではなくOS/ネットワーク層の問題）。
  - `netsh advfirewall firewall show rule name=all` で確認したところ、`sumo.exe` の受信許可ルールは**「パブリック」プロファイルにのみ存在**（TCP/UDPとも）。Private/Domainプロファイル向けの許可ルールは見当たらなかった。
  - `Get-NetConnectionProfile`（PowerShell）ではWi-Fiアダプタのみ`Public`と表示され、WSL仮想アダプタ（vEthernet (WSL)）は個別のプロファイルとして列挙されなかった（＝WSLのNAT/ローカルホスト転送機構がどのファイアウォールプロファイル判定を受けているか、今回の調査だけでは断定できない）。
  - 以上より、**Windows Defender ファイアウォールが `sumo.exe` への当該プロファイル経由の受信接続をブロックしている可能性が高い**と推定（確定ではない。管理者権限でのファイアウォール診断・設定変更は本タスクの権限外のため実施せず）。
- **重要：** この接続拒否により、TraCIループが1ステップも実行されない。`inject_buses`／`step_bus`／`board_passengers`／`alight_passengers`等、乗降会計ロジックのコードは一切実行されないまま失敗する。

### (3)(4) 出力確認・JB-2閉鎖ケース — 未実施
- 上記(2)が完走しなかったため、`scenario_b_passenger_log.csv`・`scenario_b_bus_log.csv`・`scenario_b_bus_summary.json` は**いずれも生成されていない**（`ls`で不存在を確認済み）。
- `--closure` 付きの再実行（JB-2検証）も同一の理由で未実施。

---

## 不変条件（I1〜I8）の検証結果

**すべて「検証不能（NOT TESTED）」。** TraCI接続がブロックされ乗降会計コードが1行も実行されていないため、I1〜I8のいずれについても実測値が存在しない。

| # | 不変条件 | 結果 |
|---|---|---|
| I1〜I8 | （ブループリント§5参照） | 検証不能（環境ブロッカーによりTraCIループ未到達） |

## 期待値との照合（20人→8/8/4想定 等）

- 未実施。会計コア（`p3_bus_accounting.py`）自体は既に別テスト（`B系_会計コア単体テスト.md`、pytest 28件PASS）でTraCI非依存の単体検証済みであり、そちらで「1台20人→8/8/4で3往復・不変条件成立」が確認されている。**ただし本スモークが検証すべき対象はTraCIループとの結合（`step_bus`の状態機械・停車検知・`inject_buses`等）であり、それは今回検証できていない。**

---

## 総合判定

| 項目 | 判定 |
|---|---|
| 完走（TraCI例外なくsim終了・3ファイル出力） | **FAIL（未完走）** |
| 人数保存（conservation_ok） | 検証不能 |
| 往復・乗車（boarded_count等） | 検証不能 |
| 完了時刻（duration_s） | 検証不能 |
| 早期terminate（判断6-3） | 検証不能 |
| JB-2（--closure） | 検証不能 |

## 重大な不具合の報告（コード修正はしていません）

1. **`p2_traci_bus.py:328` `sumolib.checkBinary("sumo")` がWSL実行時に`.exe`拡張子を解決できない。**
   - `checkBinary`はSUMO同梱ライブラリの挙動（`os.name=="nt"`判定）であり、`p2_traci_bus.py`側の直接バグではないが、WSL実行を前提とする本タスクの手順書どおりに実行すると`FileNotFoundError`で即落ちる。`SUMO_BINARY`環境変数を明示指定すれば回避可能（コード変更不要）。
2. **`p2_traci_bus.py:329` `traci.start([sumo_binary, "-c", str(sumocfg), ...])` がWSLのPOSIXパスをそのままWindows版`sumo.exe`に渡しており、設定ファイルを読み込めない。**
   - `p3_bus_scenario.py`・`p2_traci_closure.py`など既存コードも同一パターン（`str(scenario["sumocfg"])`を直接渡す）を使っている可能性が高く、WSL上でTraCI経由の実行を行う限り同じ問題が起き得る（未確認：`p2_traci_closure.py`自体は今回実行していない）。
   - 対処案（実装判断はOpus/ユーザー）：WSL実行時のみ`subprocess.run(["wslpath","-w",str(sumocfg)])`等でWindows形式に変換してから`sumo_binary`引数に渡す。
3. **【最重要・未解決】WSL→Windows `sumo.exe` へのTraCI TCPソケット接続が `Connection refused` で拒否される。**
   - `sumo.exe`は正常に起動し指定ポートで待受け中であることを`tasklist`/`netstat`で確認済み。にもかかわらずWSL側からの接続（`traci`経由・生ソケット直結の両方）が拒否される。
   - Windows Defender ファイアウォールの`sumo.exe`受信許可ルールが「パブリック」プロファイルのみに存在し、Private/Domain向けルールが見当たらないことを確認。WSL仮想アダプタがどのプロファイル判定を受けているかは今回の調査では断定できていない。
   - **これはコードの不具合ではなく、実行マシンのネットワーク／ファイアウォール設定に起因する環境ブロッカーと推定される。** 管理者権限での診断・ファイアウォール規則追加、またはWSL2ミラーモードネットワーキング（`.wslconfig`の`networkingMode=mirrored`、Windows 11 22H2以降）への切替えが必要な可能性がある。本タスクの権限・スコープ外のため設定変更は行っていない。

## 申し送り

- **乗降会計ロジック自体（`board_passengers`/`alight_passengers`/`step_bus`等）の正否は、今回のスモークでは一切検証できていない。** 会計コアの単体テスト（TraCI非依存・`B系_会計コア単体テスト.md`）はPASS済みだが、TraCIループとの結合部分（停車検知・`setRoute`動的往復・状態機械の遷移条件）は未検証のまま。
- 次回再試行する場合の前提整備（本タスクの権限外につき未実施）：
  1. WSL→Windows sumo.exeへのTraCI接続を通す（ファイアウォール規則追加 or WSL2ミラーモード）。
  2. `p2_traci_bus.py`側でWSL実行時のパス変換（`wslpath -w`相当）をどう扱うか方針を決める（コード変更が必要）。
  3. 上記2点の解消後に本スモークを再実行し、I1〜I8・期待値（20人→8/8/4等）を実測で照合する。
