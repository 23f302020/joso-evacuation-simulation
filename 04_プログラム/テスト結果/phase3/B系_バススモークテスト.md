# Phase 3 B系 バススモークテスト

**対象：** `04_プログラム/scripts/p3_bus_scenario.py`（最小バスシナリオ生成）＋SUMO実行
**目的：** シナリオB本実装(B-b/B-c)の前に、最大の技術未検証点を最小構成で潰す。
**実行環境：** WSL から Windows SUMO 1.26.0 を利用（`sumo.exe` 実行可・`sumolib` import可を確認済み 2026-07-08）。
**仕様正本：** `交通シミュレーション調査/_シナリオB実装仕様_fable5.md`・`_判断結果_2026-07-07.md`

> 実行担当：Sonnet。各テストケースの「実測」「判定」を埋め、末尾に総合判定と申し送りを記載する。

---

## 実行手順（WSL）

```bash
cd "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム"
SUMO_WIN="/mnt/c/Users/Ko_rr/AppData/Local/Programs/sumo-1.26.0-msi-extract/PFiles/Eclipse/Sumo"

# (1) 生成（sumolib必要・SUMO_HOME経由。pandasはユーザーsiteに導入済）
SUMO_HOME="$SUMO_WIN" PYTHONPATH="$SUMO_WIN/tools" python3 scripts/p3_bus_scenario.py smoke --buses 1

# (2) SUMO実行（sumo.exe。相対パスが効かない場合は wslpath -w で変換）
cd output/sumo/scenarios
"$SUMO_WIN/bin/sumo.exe" -c scenario_b_smoke.sumocfg --log scenario_b_smoke_sumo.log
# 代替: "$SUMO_WIN/bin/sumo.exe" -c "$(wslpath -w scenario_b_smoke.sumocfg)"
```

---

## テストケース

### TC-B-1：生成が成功する（バス計画・停・ルート・cfg）
- **手順：** 上記(1)を実行。
- **期待：** エラーなく `output/sumo/derived/bus_plan.csv`・`output/sumo/scenarios/bus_stops.add.xml`・`scenario_b_smoke.rou.xml`・`scenario_b_smoke.sumocfg` が生成。`bus_plan.csv` に1行（buses=1）。
- **実測：**
  - 初回実行は `ModuleNotFoundError: No module named 'pyproj'`（`sumolib`の`net.convertLonLat2XY`が内部でpyprojを要求）で例外落ち。コードは変更せず、`python3 -m pip install --user --break-system-packages pyproj`（pandasと同様の導入手順）でモジュールを追加導入し再実行。
  - 再実行後、4ファイルとも生成を確認：
    - `output/sumo/derived/bus_plan.csv`（`wc -l` = 2行 = ヘッダ1行＋データ1行。期待通り1台分）
    - `output/sumo/scenarios/bus_stops.add.xml`（busStop 2件：`bs_origin_0023`・`bs_shelter_shelter_019`）
    - `output/sumo/scenarios/scenario_b_smoke.rou.xml`
    - `output/sumo/scenarios/scenario_b_smoke.sumocfg`
  - コンソール出力：
    ```
    [INFO] saved: .../output/sumo/derived/bus_plan.csv (1 bus stops)
    [INFO] saved: .../output/sumo/scenarios/bus_stops.add.xml (2 busStops)
    [INFO] saved: .../output/sumo/scenarios/scenario_b_smoke.rou.xml
    [INFO] saved: .../output/sumo/scenarios/scenario_b_smoke.sumocfg
    === スモークテスト生成サマリ ===
      バス台数: 1  （うち福祉: 0）
      [OK] 全バス停が bus vClass 通行可レーンに敷設できた。
    ```
- **判定：** PASS（※初回の環境不備＝pyproj未導入を環境整備で解消した上でのPASS。本体コード自体は無エラーで完走）

### TC-B-2：バス vClass 通行可否（要検証2）
- **手順：** (1)のコンソールサマリと生成物を確認。
- **期待：** 「[OK] 全バス停が bus vClass 通行可レーンに敷設できた」。かつ `write_smoke_routes` が bus最短路の警告を出さない。
- **実測：** コンソールに「[OK] 全バス停が bus vClass 通行可レーンに敷設できた。」が出力された（`[要検証(2)]`メッセージは出ていない）。bus最短路に関する警告メッセージなし。
- **判定：** PASS

### TC-B-3：SUMO実行がエラーなく完走する
- **手順：** 上記(2)を実行。
- **期待：** route error / vClass error なく終了。`scenario_b_smoke_sumo.log` に致命的エラーなし。
- **実測：** 終了コード=1（`echo $?` で確認）。`sumo.exe`はネット・追加ファイル読み込み後、ルート読み込み中に致命的エラーで即終了：
  ```
  Loading net-file from '../network/joso.net.xml' ... done (10998ms).
  Loading additional-files from 'bus_stops.add.xml' ... done (4ms).
  Loading route-files incrementally from 'scenario_b_smoke.rou.xml'
  Loading done.
  Error: Disconnected route '!bus_std_1' when repeating. Last edge '3459' is not connected to first edge '3459' for vehicle 'bus_std_1' with vClass bus.
  Quitting (on error).
  ```
  シミュレーション本体（ステップ実行）には到達せず、読み込み段階でのエラー。原因は `scenario_b_smoke.rou.xml` の `<route edges="... 3459" repeat="14" />` — SUMOの`repeat`属性は経路が閉ループ（最終エッジ=先頭エッジに連結）であることを要求するが、このルートはpickup(3459)→shelter(6779#4)の片道経路であり閉ループではないため、2周目の接続時点で「切断されたルート」エラーとなる。
- **判定：** FAIL

### TC-B-4：route repeat × busStop がループ動作する（要検証1・最重要）
- **手順：** `output/sumo/results/scenario_b_smoke_stopinfo.xml` の `<stopinfo>` 件数を数える。
- **期待：** 1台が pickup→shelter を1往復するたび +2件。6時間内に複数往復ぶん（**4件以上＝2往復以上**）並ぶ。
- **実測：** `grep -c "<stopinfo" output/sumo/results/scenario_b_smoke_stopinfo.xml` = **0件**。TC-B-3のルート読み込みエラーによりシミュレーションが1ステップも進まなかったため、`<stops>...</stops>`は空要素のまま出力終了（tripinfo.xmlも同様に空）。busStop別内訳・往復数は測定不能（0台通過）。
- **判定：** FAIL（2件どころか0件で停止。ただし停止理由はTraCI云々ではなく、そもそも`repeat`属性が片道ルートに使えないという読み込み時エラー）

---

## 総合判定
**総合＝FAIL。要検証2（bus vClass通行可否）はPASSで解消済み。要検証1（repeat×busStopループ）はFAIL＝不成立。**

- 要検証2の結論：全バス停がbus vClass通行可レーンに敷設できており、bus vClass自体の通行可否は問題なし（TC-B-2 PASS）。
- 要検証1の結論：`route repeat`方式は、pickup→shelterのような片道（非ループ）ルートには使えないことが判明。SUMOは`repeat`属性付きルートに「最終エッジが先頭エッジへ接続していること（閉ループ）」を要求するため、現状の`.rou.xml`生成ロジック（片道経路に`repeat="14"`を付与）は構造的にSUMOのルート読み込みで即エラーになる。TC-B-4はstopinfo 0件で、往復動作の検証以前の段階で失敗。

## Opusへの申し送り（次の実装分岐）
**該当：repeat不動作 → B-cを TraCI setRoute 動的方式で実装（または route repeat を使うなら shelter→pickup の復路エッジを明示的に繋いだ閉ループルートを構築する代替も検討可）**

- bus vClass不許可の分岐は非該当（TC-B-2 PASSのため、lane選択分岐やnetconvert再設定は不要）。
- 根本原因：`scripts/p3_bus_scenario.py`（未確認だが`write_smoke_routes`相当の関数と推定）が生成する`<route edges="... 片道 ..." repeat="N" />`は、SUMOの`repeat`仕様上「閉ループ」でなければ2周目で`Disconnected route`エラーになる。pickup→shelterの単純往復では最終エッジが先頭エッジに戻らないため、この方式のままでは本実装（B-b/B-c）でも同じエラーが再現する見込み。
- 選択肢（Opus判断用）：
  1. **TraCI動的setRoute方式**：シミュレーション実行中にバスがshelter到着後、`traci.vehicle.setRoute()`でpickup地点へ戻る経路・再度shelterへの経路を都度計算・設定する。往復回数を動的に制御可能。
  2. **往復route手動構築＋repeat撤廃**：pickup→shelter→pickup→shelter…の往路・復路エッジを連結した1本の長いrouteを`repeat`なしで生成する（往復回数を静的に決め打ち）。SUMOの`repeat`機構自体を使わない。
  3. `repeat`を使い続けるなら、経路の終点から始点へ戻る復路エッジ列を明示的に含めて「閉ループ」を構成する必要がある（現状は往路のみで終端しているため不成立）。
- **未検証（今回のスモークテストの範囲外）：** pyproj未導入は本環境固有の問題であり、他環境（Opus実装環境含む）でも同様に発生しうる。本実装に進む前に依存関係（`pyproj`）を`requirements`等に明記することを推奨（コード修正はOpus側で判断）。

---

## 再実行（2026-07-08・repeat撤廃版）

**背景：** 上記FAILを受けOpusが`p3_bus_scenario.py`を修正。`route repeat`属性を撤廃し、1往復のみ（pickup→shelter→pickup の静的ルート＋busStop 2停）の構成に変更。今回は「バスが実際に走行しbusStopで停車する基礎」の確認に目的を限定（多往復は本実装B-cのTraCI setRouteで扱う）。**1台につき`<stopinfo>`2件（pickup停・shelter停）出れば基礎OK**。

### 生成（再実行）
- コマンド：`SUMO_HOME="$SUMO_WIN" PYTHONPATH="$SUMO_WIN/tools" python3 scripts/p3_bus_scenario.py smoke --buses 1`（終了コード0）
- 4ファイルとも再生成成功。コンソール「[OK] 全バス停が bus vClass 通行可レーンに敷設できた。」。
- **修正確認：** 新`scenario_b_smoke.rou.xml`の`<route ...>`から`repeat`属性が消えた（片道エッジ列のみ、末尾も先頭と同じ`3459`で終わる往復経路。`repeat`なし）。`<stop busStop=... duration="300" />`が2つ（pickup・shelter）。

### TC-B-3（再判定）：SUMO実行がエラーなく完走する
- **実測：** 終了コード=**0**。`Disconnected route`エラーは**消失**。log要点：
  ```
  Loading net-file ... done (7567ms).
  Loading additional-files from 'bus_stops.add.xml' ... done (8ms).
  Loading route-files incrementally from 'scenario_b_smoke.rou.xml' ... Loading done.
  Simulation version 1.26.0 started with time: 0.00.
  Simulation ended at time: 21600.00.
  Reason: The final simulation step has been reached.
  Vehicles: Inserted: 1  Running: 0  Waiting: 0
  ```
  致命的エラー・警告なし。バス1台がInsertされ、Running:0＝正常に走行完了して離脱。
- **再判定：** **PASS**

### TC-B-4（改め）：1往復のbusStop停車
- **実測：** `grep -c "<stopinfo" ../results/scenario_b_smoke_stopinfo.xml` = **2件**（期待通り）。内訳：
  | # | busStop | lane | started | ended | duration | persons |
  |---|---------|------|---------|-------|----------|---------|
  | 1 | `bs_origin_0023` (pickup) | 3459_0 | 3.00 | 303.00 | 300s | 0 |
  | 2 | `bs_shelter_shelter_019` (shelter) | 6779#4_0 | 1040.00 | 1340.00 | 300s | 0 |

  各busStopで各1件、duration=300s通り停車。tripinfo：`bus_std_1` depart=0.00 → **arrival=2028.00**（arrival値あり＝完走）、routeLength=7449.95m、stopTime=600.00s（2停×300s）、arrivalLane=`3459_0`（＝出発レーンに帰着、pickup→shelter→pickupの往復完了）、waitingTime=0.00・rerouteNo=0。
  ※ 乗客数(persons)は0：本スモークは人流を注入していないため空車走行。基礎（走行＋停車）の確認としては期待どおり。
- **再判定：** **PASS**（1往復2件成立。バス走行・busStop停車・出発地帰着すべて確認）

### 総合再判定
**再実行＝PASS。** repeat撤廃版で、SUMOロードエラー解消（TC-B-3 PASS）・バス実走行＋busStop 2停＋出発地帰着（TC-B-4 PASS）を実測で確認。「バスが実際に走行しbusStopで停車する基礎」は成立。要検証2（bus vClass通行可）も引き続きPASS。

**Opusへの申し送り（更新）：**
- バス走行・停車・往復ルートの基礎は動作確認済み。B-c本実装での多往復は、確定方針どおりTraCI setRoute動的方式で扱う（静的routeでの多往復＝repeatは不可が確定済み）。
- 乗客(person)注入・乗降(loadedPersons)の検証は本スモーク範囲外。B-b/B-c実装時に別途スモークが必要。
- pyproj依存は再実行でも前提（導入済み環境で実行）。requirements明記の推奨は据え置き。
