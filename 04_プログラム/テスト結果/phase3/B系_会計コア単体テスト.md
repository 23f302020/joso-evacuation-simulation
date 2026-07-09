# Phase 3 B系 会計コア単体テスト

**対象：** `04_プログラム/scripts/p3_bus_accounting.py`（バス乗降会計のコアロジック・TraCI非依存）
**テストファイル：** `04_プログラム/scripts/test_p3_bus_accounting.py`（pytest、28ケース）
**目的：** 実装コードは編集せず、`_Bc実装ブループリント_fable5.md` §3（乗降会計）・§5（品質担保：不変条件I1〜I8・受け入れ基準・乗降検証スモーク設計）に基づき、queue初期化・乗車優先順・降車・残queue会計の正しさを検証する。
**実行環境：** WSL `python3`（3.12.3）。`pytest` は未導入だったため `python3 -m pip install --user --break-system-packages pytest`（pytest 9.1.1）で導入。pandas はユーザーsite導入済み（3.0.3）。

---

## 実行コマンド

```bash
cd "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム"
python3 -m pytest scripts/test_p3_bus_accounting.py -v
```

`scripts/` に `__init__.py` が無いため、pytest のデフォルトのrootdir挿入により `scripts/` が `sys.path` に追加され、`import config` / `import p3_bus_accounting` がそのまま解決される（conftest.py等の追加は不要）。

---

## 実測結果

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
collected 28 items

TestInitQueues::test_basic_split_type3_excludes_mob PASSED
TestInitQueues::test_rounds_and_clamps_non_negative PASSED
TestInitQueues::test_mob_greater_than_type3_all_produces_negative_type3_uncla_mped PASSED
TestInitQueues::test_multiple_stops_sum_matches_source PASSED
TestBoardPassengersPriority::test_welfare_bus_prioritizes_type4_then_mob_then_type3 PASSED
TestBoardPassengersPriority::test_standard_bus_prioritizes_type3_then_mob_then_type4 PASSED
TestBoardPassengersPriority::test_person_type_mapping_type3_mob_is_person_type_3 PASSED
TestBoardPassengersPriority::test_capacity_not_exceeded_when_demand_exceeds_capacity PASSED
TestBoardPassengersPriority::test_zero_queue_at_stop_produces_deadhead_board PASSED
TestBoardPassengersPriority::test_welfare_zero_demand_stop PASSED
TestBoardPassengersPriority::test_exact_capacity_match_empties_queue PASSED
TestBoardPassengersPriority::test_passenger_id_unique_across_multiple_boardings PASSED
TestAlightPassengers::test_duration_equals_arrival_minus_board PASSED
TestAlightPassengers::test_deadhead_trip_still_advances_trip_seq_and_logs_bus_row PASSED
TestAlightPassengers::test_onboard_reset_after_alight PASSED
TestAlightPassengers::test_terminated_flag_propagates_to_bus_row PASSED
TestBoardingSmoke::test_three_trips_clear_20_person_queue PASSED
TestBoardingSmoke::test_fourth_trip_onward_is_deadhead PASSED
TestBoardingSmoke::test_invariant_i1_boarded_equals_alight_plus_residual PASSED
TestEndOfSimulationBoundary::test_boarded_but_not_alighted_before_sim_end_is_not_arrived PASSED
TestSettleStrandedToRescue::test_bus_transport_total_counts_only_arrived PASSED
TestSettleStrandedToRescue::test_residual_queue_by_stop_is_a_copy_not_a_reference PASSED
TestSettleStrandedToRescue::test_rescue_after_bus_formula PASSED
TestSettleStrandedToRescue::test_empty_queues_zero_residual PASSED
TestQueueTotal::test_sums_all_categories_all_stops PASSED
TestQueueTotal::test_zero_for_empty_dict PASSED
TestLoadBusUnitsAndStopMeta::test_load_bus_units_capacity_and_welfare_flag PASSED
TestLoadBusUnitsAndStopMeta::test_stop_meta_from_plan_maps_stop_to_origin_and_key_code PASSED

============================== 28 passed in 2.29s ==============================
```

**28件全PASS（FAILなし）。**

---

## 不変条件（ブループリント §5）の検証状況

| # | 不変条件 | 検証テスト | 結果 |
|---|---|---|---|
| I1 | Σboarded = Σalight + Σonboard(終了時) + Σ送届(打切り) | `TestBoardingSmoke::test_invariant_i1_boarded_equals_alight_plus_residual`、`test_fourth_trip_onward_is_deadhead`（Σboarded+残queue=初期queue） | PASS |
| I2 | queue["type3"], ["type4"] 等が各ステップ非負 | `TestBoardPassengersPriority::*`（容量超過需要・queue=0・福祉0人など境界含む）、`TestInitQueues::test_mob_greater_than_type3_all_...`（異常値クランプ） | PASS（実装内 `assert q[category] >= 0` も無エラーで通過） |
| I3 | passenger_id ユニーク＝二重計上なし | `test_passenger_id_unique_across_multiple_boardings`、スモーク3件 | PASS |
| I4 | vehicle_log にバスIDが1件も無い（JB-4） | 本モジュール単体では vehicle_log を扱わないため対象外（`p2_traci_bus.py` 側の結合テストで要検証。本テストでは代わりに bus_rows/passenger_rows のみで人数計上されることを確認） | 対象外（申し送り） |
| I5 | Σbus_candidate_population(整数化後) = Σ初期queue | `TestInitQueues::test_multiple_stops_sum_matches_source` | PASS |
| I6 | residual_queue ≈ 救出走行輸送能力（±丸め） | `TestSettleStrandedToRescue::test_rescue_after_bus_formula`（式の再現） | PASS（式は再現一致。実データでの輸送能力側との突合はP3-IMPL-0側のスケールで別途要検証） |
| I7 | 各バス trip_seq ≤ 理論上限 | 本テストの範囲外（時間軸込みのループ制御は `p2_traci_bus.py` 側。本モジュールは `trip_seq` をインクリメントするのみで上限管理を持たない＝仕様通り） | 対象外 |
| I8 | duration_s = arrival_time_s − board_time_s（全乗客） | `TestAlightPassengers::test_duration_equals_arrival_minus_board`、スモーク各件 | PASS |

**乗降検証スモーク（ブループリント §5 記載の期待値）：** バス1台(standard, capacity=8)・1停・queue初期`{type3:20}`で、3往復`8,8,4`人乗車・20人全員`arrived==True`・全員`person_type==3`・4往復目以降`deadhead==True`を実測確認（`TestBoardingSmoke`）。ブループリント記載の期待値と完全一致。

---

## カバーした観点

- **queue初期化：** type4/type3_mob/type3の正しい分離（mobはtype3_no_carの部分集合として減算）、非整数・負値の丸め＋非負クランプ、複数停の合計整合。
- **異常値クランプ：** `type3_mobility_limited_candidate_pop > type3_no_car_non_elderly_pop`（本来ありえないはずのデータ）でも `type3` が負値にならず0にクランプされることを確認（`test_mob_greater_than_type3_all_produces_negative_type3_uncla_mped`）。
- **乗車優先順（判断6-5）：** 福祉車→type4→type3_mob→type3、標準車→type3→type3_mob→type4 の両方向を、queueが混在するケースで実測。
- **境界：** queue=0（全便deadhead）、queue<capacity（1往復で完了）、容量超過需要（capacity以下にクランプ）、福祉車が来たがtype4=0の停。
- **降車：** duration_s計算、deadheadでもtrip_seq進行・bus_log行生成、onboardリセット、terminatedフラグ伝播。
- **sim終了直前の境界：** 乗車後にalight_passengersが呼ばれない場合、`arrived==False`のまま（=逃げ遅れ計上される設計）であることを確認。
- **settle_stranded_to_rescue：** bus_transport_total（arrived==Trueのみ集計）、residual_queue_by_stopが元queuesの参照ではなくコピーであること、rescue_after_bus計算式の再現。
- **load_bus_units / stop_meta_from_plan：** CSV読込からのBusUnit生成（capacity・is_welfare判定）、停→origin_id/KEY_CODE/shelter_idマッピング。

---

## 発見した不具合

**なし。** 実装した28ケース（不変条件I1・I2・I3・I5・I6・I8の直接検証、優先順位、境界値、異常値クランプを含む）はすべて期待どおりの挙動でPASSした。バグ修正は行っていない（本タスクの方針通り、実装コード `.py` 本体は無編集）。

## 申し送り

- I4（vehicle_logにバスIDが無いこと）とI7（trip_seq上限）は、本モジュール単体では検証対象外（TraCIループを持つ `p2_traci_bus.py` 側の結合テスト・実行ログでの確認が必要）。
- I6は会計式自体の再現一致は確認したが、「救出走行の実輸送能力（rescue台数×k）との突合」は実データ規模でのB3〜B5の1巡検証（ブループリント§4 JB-5の重要な注記）で別途行う必要がある。
- `settle_stranded_to_rescue` の `rescue_after_bus_vehicles_raw` は負値になり得る（バス輸送だけで必要人数を上回る場合）。クランプ（0未満は0扱いにするか等）の要否は仕様側の判断待ちと見られるため、実装は現状（負値もそのまま返す）で問題ないかP3-IMPL-0側の意図を確認されたい（コード上のバグではなく仕様確認事項）。

---

## 結論

会計コア（`p3_bus_accounting.py`）は、ブループリント §3（乗降会計）・§5（不変条件I1〜I8のうちモジュール内で検証可能なI1・I2・I3・I5・I6・I8、乗降検証スモーク）の仕様通りに動作していることを28件のpytestで確認した。全件PASS、不具合の発見なし。
