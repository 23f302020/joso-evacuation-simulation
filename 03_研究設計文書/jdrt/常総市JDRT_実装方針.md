# 常総市JDRT 実装方針

> 作成日：2026-08-11  
> 対象：常総市（自治体コード08211）  
> 状態：初期実装方針確立  
> 参照設計：`開発メモ/joso_design_docs_integrated_v3/`

## 1. 目的

既存Phase 1〜3と車＋徒歩Scenario Cを変更せず、常総市に限定した新しい研究系列として、避難希望者の現在位置、待ち時間、脆弱性、道路閉鎖の見込みを用いる動的な乗合車両配車を実装する。

最初の実装ではSUMOを起動しない。配車判断に必要な状態、実行可能性判定、配車方式の交換口、人物会計を小規模な固定入力で検証する。これらが成立してからTraCI統合へ進む。

## 2. 既存成果との境界

- Phase 1〜3の入力、正本run、評価結果、結論を変更しない。
- 既存の`Scenario C`は車＋徒歩実験を指すため、新研究では`JDRT`接頭辞を使用する。
- `p2_traci_bus.py`の既存バス状態機械、とくに`step_bus`を変更しない。
- 確定route、既存output、HTML正本を変更・再生成しない。
- JDRTのコードは`04_プログラム/scripts/jdrt/`、将来の出力は`04_プログラム/output/sumo/regions/08211/experiments/jdrt/`へ分離する。
- 常総市以外の地域別SUMO出力は`07_アーカイブ/茨城県他市町村_SUMO_20260811/`へ分離し、JDRTの実行経路から外す。

## 3. シナリオ識別子

| ID | 内容 | 用途 |
|---|---|---|
| JDRT-B0 | 既存固定計画型 | 連続性確認 |
| JDRT-B1 | 現在位置から近い要求を選択 | 基礎Baseline |
| JDRT-B2 | 現在の旅行時間を使用 | 強Baseline |
| JDRT-B3 | 待ち時間と脆弱性を使用 | 洪水情報追加前の比較 |
| JDRT-P1 | 完全な将来閉鎖情報を使用 | 理論上限 |
| JDRT-P2 | 誤差を含む将来閉鎖情報を使用 | 現実性を持つ比較 |

シナリオIDは既存A/B/Cの名称と混在させない。

## 4. レイヤ分離

### 4.1 Python側

- 避難者、要求、車両、道路状態の管理
- 配車候補の作成と実行可能性判定
- 配車方式の選択
- 将来閉鎖情報の管理
- event、manifest、人物・車両会計
- 研究用集計

### 4.2 SUMO/TraCI側

- 道路上の車両走行
- 現在の速度、旅行時間、混雑の取得
- 時刻別道路閉鎖の適用
- 決定済みroute・stopの反映

DispatcherはTraCIを直接呼ばず、Python側で作成した`NetworkState`だけを受け取る。

## 5. True WorldとPerceived World

実際にSUMOへ適用する閉鎖時刻と、Dispatcherが判断に用いる予測閉鎖時刻を別の型・別の引数として管理する。

- True World：実際の道路閉鎖にだけ使用する。
- Perceived World：Dispatcherの判断にだけ使用する。

初期Dispatcherの公開APIへTrue Worldを渡さない。これにより、将来の正解を誤って配車へ利用する情報リークを構造的に防ぐ。

## 6. 初期モジュール構成

```text
04_プログラム/scripts/jdrt/
  __init__.py
  workspace.py    # 常総市08211専用の実行・出力パス
  domain.py       # 状態・入力を表す型
  dispatch.py     # 実行可能性判定と配車方式
  validation.py   # 人物・交通手段・最終状態の会計
  input_adapter.py # 正式設定・入力SHA検証と常総市入力生成
  run_records.py  # 独立runのevent log・manifest

04_プログラム/tests/unit/
  test_jdrt_domain.py
  test_jdrt_dispatch.py
  test_jdrt_validation.py
```

初期段階完了後、正式PAP・Parameter Registry v1に基づいて設定ローダー、常総市入力アダプター、run記録基盤を追加した。SUMO controllerは次段階で個別タスクとして追加する。

## 7. 初期公開API

### 7.1 `domain.py`

- `TransportMode`
- `EvacueeStatus`
- `RequestStatus`
- `VehicleStatus`
- `Evacuee`
- `DRTRequest`
- `DRTVehicle`
- `NetworkState`
- `ForecastState`
- `AssignmentCandidate`
- `JDRTWorkspace`

`ForecastState`は予測閉鎖時刻だけを保持し、真の閉鎖時刻を保持しない。

`JDRTWorkspace`は自治体コードを`08211`に限定し、他市町村コードを拒否する。JDRTのrun探索は`08211/experiments/jdrt/runs/`だけを対象とし、地域ルート全体や既存Scenario Cを列挙しない。

### 7.2 `dispatch.py`

- `is_assignment_feasible`
- `NearestDispatcher`
- `DynamicTravelTimeDispatcher`
- `WaitingVulnerabilityDispatcher`
- `FloodRiskAwareDispatcher`

すべてのDispatcherは候補一覧から1件を選ぶ小さな責務に限定する。経路探索、SUMO操作、ファイル出力は行わない。

同点時は`request_id`、`vehicle_id`の順で決定し、同じ入力から同じ選択を返す。

### 7.3 `validation.py`

- `validate_unique_person_modes`
- `validate_population_accounting`
- `validate_final_state_conservation`
- `validate_vehicle_capacity`

検証関数は不整合時に理由を含む`ValueError`を送出する。

## 8. 実行可能性判定

候補はスコア計算前に次を満たす必要がある。

```text
予測pickup時間
+ pickup後の避難所到達時間
+ safety margin
< route上の最早予測閉鎖までの残り時間
```

すでに閉鎖済みのedgeを含む候補、定員を超える候補、予測閉鎖時刻が不足する候補は選択対象外とする。閉鎖されないrouteは残り時間を無限として扱う。

`safety margin`等の正式値は初期コードへ固定しない。呼び出し側から明示的に渡す。

## 9. 初期実装の不変条件

- `person_id`、`request_id`、`vehicle_id`は各集合内で一意。
- 1人に複数の主要交通手段を割り当てない。
- DRT対象者へ救出走行を同時に割り当てない。
- 車両の乗車人数は定員以下。
- `evacuated + stranded + cancelled + active = 対象人口`を維持する。
- DispatcherはWAITING要求だけを対象とする。
- DispatcherはTrue Worldを受け取らない。
- 同一入力に対する選択順序は決定論的。

## 10. 研究判断と技術実装の境界

次の値は研究方針判断後にParameter Registryで確定し、初期コードへ埋め込まない。

- DRT利用対象者と利用率
- 救出走行の置換率
- fleet、定員、乗降時間
- 車両基地、運行開始時刻
- dispatch間隔、safety margin
- 待ち時間・脆弱性・洪水リスクの重み
- 避難所容量・利用可能時間
- seedとfull実験条件

単体テスト内の数値は計算例のための合成値であり、研究の正式パラメータではない。

## 11. 段階的な実装順

1. ドメイン型と不変条件
2. 実行可能性判定
3. B1〜B3とP1/P2の選択規則
4. 人物・交通手段・車両会計
5. 小規模固定入力による単体テスト
6. 常総市入力アダプター
7. event log・run manifest
8. TraCI controller
9. 車両1台・要求約10件のsmoke
10. Pre-Analysis Plan承認後のfull実験

## 12. 初期実装の受入条件

- 新規コードが既存Phase 1〜3モジュールを変更しない。
- SUMOなしで単体テストが実行できる。
- 実行可能性判定が境界条件を含めてテストされる。
- 各Dispatcherの選択が決定論的である。
- True WorldがDispatcher APIへ含まれない。
- 人物、交通手段、最終状態、車両容量の不整合を検出できる。
- 既存JDRT以外のテストに回帰を発生させない。
- アクティブな地域ルート直下は`08211`と`_management`だけとし、他市町村はmanifestとSHA付きアーカイブから復元可能にする。

## 13. この段階で行わないこと

- full SUMO run
- 既存A/B/Cの再実行
- 実測結果に基づく重み調整
- Pooling
- Spatial Forecast Error
- 道路のDEGRADED状態
- 分散基地最適化
- DRL、MILP、任意DARP
