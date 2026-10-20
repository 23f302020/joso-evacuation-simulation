# 常総市JDRT 現実条件版：人物対応・観測仕様（判断入力）

> 2026-10-16追加：USACEの5分水位/地形を取得・候補照合。現在の領域/時計/交通条件の具体案は[実時間版の開始前判断案v1](常総市JDRT_実時間版_開始前判断案_v1.md)。本資料の未採用値はそのまま実行へ移さず、新run未開始。

作成：2026-10-15 JST。対象：常総市08211。状態：**技術仕様の提案・採用未定**。

ユーザーは2026-10-15に「現在の運用＋2015年型洪水（推奨）」を選択した。本書はその反実仮想を対象に、新系列PAP・Parameter Registryを確定するための判断入力である。入力生成、実装、smoke、full runを許可する文書ではない。人口版、交通手段割合、予約分布、車両運用、避難所条件、計算刻み、受入閾値は正式判断前のTBDとする。既存v2、Scenario C、先行REAL-R0の入力・コード・runは変更しない。

## 1. 既存データで確認した人物差

次表は入力CSVの整数列を合計し、origin_idで対応させて再計算した値。現実人口の推定精度を保証する値ではなく、既存系列間の構造差を示す。

| 項目 | JDRT v2入力 | 先行REAL-R0入力 | origin別値が異なる件数 |
|---|---:|---:|---:|
| 総人口 | 21,539 | 21,539 | 0 |
| 高齢者 | 6,191 | 6,246 | 144 |
| Type3 | 2,320 | 2,294 | 58 |
| Type4 | 935 | 937 | 44 |
| 車を持たない対象者 Type3＋4 | 3,255 | 3,231 | — |
| 自家用車台数 | 8,164 | 7,960 | — |

- v2は`derived/agent_types.csv`を`jdrt/input_adapter.py::_make_evacuees`で人物化する。IDは`origin_XXXX_type4_NNNN`、`origin_XXXX_type3_mobility_limited_NNNN`、`origin_XXXX_type3_NNNN`。Type3支援必要群の連番はその他Type3と独立している。全人口の個人乗員台帳はv2の人物結果に含まれない。
- R0はScenario Cの`scenario_c_agent_types.csv`と全人口の`scenario_c_mode_ledger.csv`を使用する。`scenario_c_car_walk.py::build_scenario_c_agent_types_for_rate`は秘匿群に対応した年齢按分と、市全体の非保有率に対する整数配分を用いる。IDはType1〜4別の連番。15%は実測ではなく参照仮定である。
- R0は車乗員18,308人を`car_occupancy_ledger.csv`で7,960台へ、徒歩割当3,231人を`walk_person_ledger.csv`へ対応させる。徒歩route生成不可・距離超過でSUMOへ投入されない人物も台帳から削除しない。
- 同じorigin、総人口、文字列IDがあっても、系列間のType/年齢配分と連番の意味が異なる。**v2結果とR0結果を同一人物の対応比較として結合しない。** 新系列で採用する人口版・年齢/保有配分はTBD。既存R0は共通条件の完全一致を将来確認するまで正式比較へ再利用しない。

## 2. 共通人物・交通手段台帳案

人口版を1つ固定し、同一seedのR0/R1/R2が同じ人物集合を参照する。人物IDは交通手段やTypeの変化から独立した`population_version + origin_id + person_ordinal`を候補とする。既存IDは`source_person_id`として出典対応を保持し、新旧の一対一対応が証明できない場合は`not_identifiable`と記録する。擬似個人を実在の住民と同定しない。

| 新規台帳候補 | 主キー・必須列 | 制約・不明値 |
|---|---|---|
| population_master.csv | population_version, person_id, origin_id, mesh_code, person_ordinal, age_group, baseline_car_access, person_type, assistance_category, source_person_id, source_record_ref, evidence_class | 1人1行。Typeは基準時の年齢・車アクセスから固定。R1/R2でJDRTへ移ってもType4を別Typeへ付け替えない。支援必要度/世帯は未知ならnull＋理由。originを世帯とみなさない |
| person_realization.csv | population_version, seed, person_id, readiness_time_sec, departure_intent_time_sec, adoption_draw_ref, request_time_draw_ref, walking_speed_mps, sampling_spec_sha | 3条件共通の外生的実現値。利用率や時刻分布・変数間依存はTBD。利用しない変数のnullにはnot_applicableを付ける |
| person_mode_by_condition.csv | seed, condition_id, person_id, baseline_mode, assigned_mode, conversion_reason, service_eligibility, decision_ref | 各条件・各人1行。自家用車/家族近隣送迎/徒歩/従来救援/JDRT/移動手段なしを区別。未根拠の交通手段は勝手に人口へ配分しない |
| vehicle_master.csv / vehicle_occupancy.csv | seed, condition_id, vehicle_id, vehicle_role, vtype_id, sumo_vclass, capacity_people, origin_edge_id, available_from_sec / vehicle_id, person_id, boarded_sec, alighted_sec, trip_id | 車と乗員を別表で対応。運転者を母数に含むかPAPで固定。1台1回の静的乗員と複数tripの動的乗員を混同しない。定員・乗降イベント単位で重複検査 |
| request_master.csv / request_members.csv | seed, condition_id, request_id, request_time_sec, pickup_edge_id, shelter_id, party_size / request_id, person_id | R1/R2の要求集合・人物割当・時刻は同一。1要求をCSV内の文字列配列だけで保存せず、人物対応を別行で検証可能にする。R0は要求なしをmanifestに明示 |
| person_outcome.csv | run_id, person_id, assigned_mode, final_status, terminal_reason, depart_sec, boarding_start_sec, pickup_completed_sec, shelter_arrival_sec, alighting_completed_sec, terminated_sec, source_event_ids | 全人口1人1行。完了定義は各modeの安全な避難先での受入完了へ統一する案。車の到着だけから乗員全員の降車完了を仮定する場合は規則を登録。時間は秒、空欄と0を区別 |

人口保存は、origin×年齢×Typeの入力整数会計、全人口のID一意性、各条件のmode分割、要求member、乗員、最終状態で独立に確認する。主要交通手段を1つ持つことと、送迎・JDRT等の複数区間に乗ることは別である。複数区間を採用する場合は`journey_leg_id`で時間区間を分け、同時二重輸送を禁止する。採用しない場合は1人1輸送区間として明示する。

## 3. 3条件の共有・許可差と乱数

| 比較 | 共有して固定するもの | 許可差案 |
|---|---|---|
| R0/R1/R2共通 | 人口版・個人属性・origin・mesh・基準避難先、True車道/歩道閉鎖、net、車種挙動設定、外生的出発意図、背景需要のID/台数/出発予定/速度係数等、観測・受入規則 | 混雑による実際の出発遅延、経路、到着は内生結果なので一致を要求しない |
| R1−R0 | JDRT転換対象となる人物も同じ人口台帳上で保持 | JDRT導入と対象者の交通手段転換、そこから必然的に生じる車両・占有の差。自家用車からの転換・同乗車の存廃を許す範囲はTBDとして列挙する |
| R2−R1 | fleet/定員/拠点、要求ID/member/時刻、mode、乗降規則、配車更新間隔、重みのうち非予測部分 | 予測閉鎖情報と、それを利用する閉鎖緊急度・Feasibility Gateに必要な処理だけ。予測以外の重みや候補生成規則を同時変更しない |

`SUMO --seed`が同じという条件だけでは、条件をまたぐ同一人物・同一車両への全乱数割当一致を証明できない。SUMOは用途別RNGを持ち、車両生成時に速度係数等の乱数も使用する。JDRT追加や生成順の変化による対応ずれがあり得る、という技術上の制約として扱う。[SUMO Randomness](https://sumo.dlr.de/docs/Simulation/Randomness.html)（確認2026-10-15）。

提案：需要・採用・予定時刻・歩行速度・車種/速度係数等、共有すると宣言した外生変数は、系列版・seed・entity_id・変数名をキーに一度生成して保存し、3条件へ同じ値を渡す。入力SHAとentity別実現値ハッシュを検査する。残るSUMO内部乱数の対応は別欄`internal_rng_pairing_status`へ`not_guaranteed`等で明記し、共有背景需要が同じことと実現した交通軌跡が同じことを区別する。内部乱数まで一致させる方式の採用はTBDであり、乱数を全面除去する条件変更を本書では決めない。

## 4. 道路観測：母数・ゼロ・欠測

現状のR0 `write_edge_congestion`は60秒FCDから**車両が写った外部edgeのみ**を保存し、internal laneを除外する。行がないedgeは0台と欠測を区別できない。v2 `FullRunTraCIPort.observe_step`は0.5秒ごとの技術観測、60秒ごとの全体速度/halting集計であり、道路別の全母数を保存しない。これらをそのまま新系列の道路別完備データと呼ばない。

| 出力案 | 必須列・定義 |
|---|---|
| observation_edge_universe.csv | net_sha, edge_id, edge_function, sumo_vclass, lane_ids_ref, initial_allowed, geometry_ref, inclusion_status, exclusion_reason, closure_mapping_status, region_flags。母数は静的に固定したnet上でそのclassが通れるlaneを1本以上持つ外部edge集合。passenger/bus/pedestrianを混ぜず、必要class一覧はPAPで固定 |
| observation_coverage.csv | run_id, tick, observed_time_sec, domain, expected_entity_count, successful_entity_count, status, error_code。観測成功を記録し、観測欠損と需要0を分ける |
| edge_timeseries.csv | run_id, snapshot_tick, sim_time_sec, edge_id, sumo_vclass, vehicle_role_scope, count, speed_sum_mps, mean_speed_mps, halting_count, closure_effective, observation_status。成功した0台edgeはcount=0/halting=0/速度平均=null。観測失敗はcountもnullとし、0へ変換しない |
| edge_window_summary.csv（採用時） | interval_start_sec, interval_end_sec, edge_id, class, expected_ticks, observed_ticks, vehicle_time_sec, halting_vehicle_time_sec, distance_m, estimator_id。スナップショットと時間窓平均を別ファイル・別指標として定義し、60秒の1点を60秒平均と呼ばない |

歩行netの外部歩行可能edge、最大連結成分、投入対象origin/shelter、crossing/walkingarea/internalをそれぞれ区分し、件数とSHAを保存する。自動生成された横断施設・歩行空間を現実の歩道整備実態と呼ばない。最大連結成分から外れるoriginやroute未生成者は人口分母から消さず、理由付き非投入・未完了へ残す。歩行指標の母数は「全人口」「徒歩割当」「SUMO投入」「観測active」を別に持つ。

「避難所周辺」「閉鎖地点周辺」の距離・方法、JDRT経路周辺の定義、停止速度閾値、観測欠損許容率はTBD。地図上の交差だけを道路接続や閉鎖共有とみなさない。橋梁・立体交差の高さ、交差道路への浸水範囲波及は入力マッピングの責任範囲として根拠を求め、未知なら不確実性として保持する。

## 5. 計算刻み・閉鎖適用順序・閉鎖後進入

新系列の全条件に同一の`simulation_step_sec`を適用し、0.5秒案と1秒案のいずれを採用するかPAPで固定する。既存v2の0.5秒とR0の1秒を同一条件として混ぜない。観測は**毎SUMO step**、配車controllerは独立した登録間隔、閲覧用の道路出力は60秒候補と分離する。刻みの変更時は距離積分・停止継続時間を`speed × dt`、`stopped_ticks × dt`へ対応させ、既存R0コードの1秒加算をそのまま流用しない。

時刻は整数tickと秒を併記し、floatを`int()`で切り捨てない。提案の順序は以下。正式採用時に実装・smokeで境界を検証する。

1. tick tで有効になる車種別/歩行者別のTrue閉鎖を、次の区間[t,t+dt)の移動前に適用する。予定閉鎖時刻が刻みに一致しない場合の丸め・有効時刻はTBDとし、予定時刻と実適用時刻を両方保存する。
2. 現在地が閉鎖対象になったentityを`closure_caught_on_edge`として記録する。閉鎖前進入者が捕捉された事象と、閉鎖後に新たに進入した違反を分離する。除去・再経路・待機の行動規則は全条件共通で登録する。
3. 配車/歩行/背景交通の制御を登録順で行い、SUMOを1step進める。進行後の出発・到着・teleport・edge遷移・現在地を観測する。t=0、閉鎖時刻ちょうど、到着と閉鎖同tick、終了時刻ちょうどの優先順位をテストする。

新規`closure_application.jsonl`案：`run_id, event_seq, source_event_id, scheduled_sec, effective_tick, effective_sec, edge_id, target_vclass, old_allowed, new_allowed, mapping_status, application_status, error_code`。同時刻の複数閉鎖は順序を固定し、重複を検出する。車道/歩道で時刻が異なるなら別事象として保持。元入力が時刻順でない/同一edgeに複数時刻がある場合、暗黙の`setdefault`採用をせず、累積閉鎖か再開を含むかを検証する。

新規`edge_transition.jsonl`案：`run_id, event_seq, entity_kind, entity_id, vehicle_role, vclass, observed_tick, from_edge, to_edge, previous_route_index, current_route_index, route_version, entry_time_lower_sec, entry_time_upper_sec, closure_effective_sec, classification, evidence_quality`。

- 進入対象はpassenger/bus等の登録classと歩行者を別々に照合する。閉鎖permissionは対象lane/classへ適用し、他classの既存禁止を上書き消去しない。
- internal edge/crossing/walkingareaは外部edgeとの対応辞書を保存する。単に`:...`を削除して進入判定から抜かない。対応不能な遷移は`unresolved_internal_transition`として計数する。
- 毎stepの現在edge観測だけでは、その間に通過した短いedgeや交差点内の全進入時刻を保証できない。route indexの飛越とroute変更履歴を保存し、復元可能な中間edgeは記録する。閉鎖境界をまたぎ時刻を特定できないものは`ambiguous`であり「違反0」へ丸めない。厳密な全進入ゼロ保証に必要な追加出力/計測方式と曖昧事象の採否閾値はTBD。
- v2の`CLOSED_EDGE_ENTRY`やR0の`closed_edge_entry_violation`は観測した検出事象であり、網羅的な全車両遷移台帳ではない。既存runへ新しい観測を遡及追加しない。

TraCIのsimulationStep後に取得する観測と制御時刻の関係は実装順に依存する。[SUMO TraCI Python](https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html)（確認2026-10-15）。上の順序は既存コードの保証ではなく、新系列で検証する提案である。

## 6. 配車候補・Feasibility Gate観測

現状の`JDRTController._candidate`は容量・閉鎖・経路不可で候補を落とし、`dispatch.is_assignment_feasible`はboolのみを返す。`_dispatch`には方式依存の候補準備・枝刈りがあり、selectへ渡らなかった組がある。最終未完了理由をGate拒否数へ代用できない。

候補ログは各判断サイクルの**実際に検査した組**の記録とし、全要求×全車両が評価されたと偽らない。提案ファイルは次の2種類。具体名は正式実装時に固定する。

| 出力案 | 必須schema |
|---|---|
| dispatch_cycle.jsonl | run_id, cycle_id, tick, observed_sec, waiting_request_count, idle_vehicle_count, candidate_universe_definition, enumerated_pairs, precheck_rejected_pairs, route_attempted_pairs, route_failed_pairs, gate_evaluated_pairs, gate_passed_pairs, selected_pairs, skipped_pairs, skip_reason_counts, dispatcher_version, forecast_snapshot_sha |
| candidate_evaluation.jsonl | run_id, cycle_id, evaluation_seq, request_id, vehicle_id, evaluation_stage, request_status, vehicle_status, party_size, remaining_capacity, route_version/hash_ref, pickup_travel_sec, boarding_sec, shelter_travel_sec, safety_margin_sec, predicted_earliest_closure_sec, predicted_margin_sec, required_time_sec, gate_applied, gate_pass, rejection_flags, primary_rejection_reason, waiting_score, vulnerability_score, pickup_score, flood_score, total_score, selected, skip_reason, error_code |

`required_time = pickup + boarding + shelter travel + safety margin`と予測残余の**厳密不等式**を各行から再計算できること。到着後の降車時間をGateに含めるか等の研究条件は新PAPへ明記し、既存v2から暗黙に変更しない。予測閉鎖なしは数値0やJSON Infinityではなくnull＋`no_predicted_closure`。予測不要のR1は`gate_applied=false`とし、不適用を通過件数へ含めない。

候補除外理由は状態不一致/定員不足/現在閉鎖/経路不可/予測余裕不足等を分ける。多重不適合はflagsで残し、集計用の主理由の優先順位を固定する。予測通過後の落選は`not_selected`でありGate拒否ではない。同じ組を再評価した回数と、ユニーク組数を両方算出可能にする。

loggerへ渡すデータは配車が実際に受け取った観測/予測だけとする。True将来閉鎖による事後の正誤評価はrun終了後の別joinで行い、R1/R2の公開入力APIへ監査目的のTrue未来情報を混入させない。候補ログを有効にしただけで選択・乱数消費・結果が変わらないことをsmokeで検査する。

## 7. 避難所収容人数・時間台帳

既存`derived/shelters_sumo.csv`のcapacity=0はv2 adapterが不明値Noneへ変換し、PAPは容量制約を使わない。新系列で同じ0を実収容0人と解釈し直さない。容量不明・閉鎖・未開設・満員を区別する。

| 台帳案 | 主な列・規則 |
|---|---|
| shelter_schedule.csv | shelter_id, valid_from_sec, valid_until_sec, capacity_people, capacity_status, open_status, welfare_compatible, evidence_ref, evidence_date, evidence_class。capacity_statusはknown/unknown/unlimited_assumption等。実値0はknownかつ0。未知に無制約を選ぶ場合は仮定を明示しPAPで採用 |
| shelter_event.jsonl | run_id, event_seq, tick, shelter_id, person_id, journey_leg_id, event_type, before_occupancy, delta_people, after_occupancy, capacity_at_tick, accepted, rejection_reason, alternate_shelter_id, reservation_id。入所/退所/拒否/代替/予約を区別 |
| shelter_timeseries.csv | run_id, tick, shelter_id, open_status, capacity_people, capacity_status, admitted_cumulative, departed_cumulative, occupancy_people, reserved_people, rejected_cumulative。全modeの人物を同じ会計へ入れる |

容量を予約で確保するか、物理到着で消費するか、同tickの先着順とtie break、途中退所、満員時の代替先・移動をPAPで決める。未知ならTBD。予約人数と現地滞在人数を二重加算しない。降車完了/避難完了は実際の受入・開設・容量判定と整合させる。origin固定避難先を共有するか、動的代替先を許すかは研究方法の判断であり本仕様では確定しない。

## 8. 新出力の必須検査・受入条件案

以下の0件・完全一致は構造的整合性検査の提案。研究上の採用規則、許容欠損、未知値扱いは新PAP承認前に実行条件へ固定しない。

| 検査対象 | 提案する受入条件・検出する失敗 |
|---|---|
| 来歴・版 | protocol/Parameter/全入力/net/実装/出力SHA一致。対象地域・母数・実現値版を明示。不一致・重複有効セルを停止し自動選択しない |
| 人口・ID・属性 | 全人口、origin/Type/年齢別整数会計一致。ID重複0、欠落0、条件横断の静的属性差0。既存v2/R0からの無証明同一人物joinを拒否 |
| mode・要求・乗員 | 1人1主要mode、無理由未割当0、同時二重輸送0。要求member集合がJDRT対象と一致。各時点の乗員≦登録定員。fleet0でもゼロ除算せず不適用を保存 |
| 条件間許可差 | 共通台帳SHA/外生実現値一致、R1/R2要求・fleet一致。R0/R1の差分whitelist外は0。True未来情報漏えい0。SUMO内部乱数の一致保証範囲を報告 |
| 終状態・時間 | 成功＋失敗＋非出発等の理由付き終端＝全人口。要求→乗車開始→乗車完了→安全避難先到着→受入完了の順序。失敗の時間nullを0へ補完しない |
| Gate | cycle/stage会計一致、候補行からstrict Gateを再計算一致。not_applicable/経路失敗/予測拒否/落選を区別。情報なしを拒否0と報告しない |
| 道路母数・coverage | class別固定edge集合と各出力のキーを照合。0台と観測失敗を区別。期待tick/実観測tick・欠損/曖昧事象を保存。許容欠損率・受入閾値はTBD |
| 閉鎖・遷移 | 登録時刻/有効時刻/permission適用を全classで照合。予定閉鎖事象の未処理0。捕捉/新規進入/内部遷移不明/曖昧時刻を分離。網羅性不足から違反0を主張しない |
| 避難所 | 全mode受入人物の重複0、occupancy=初期＋入所−退所、known容量超過0、未開設受入0。不明容量/代替規則が未登録なら開始ゲートを閉じる |
| 数値・観測粒度 | 毎step dtの積分単位一致、60秒snapshotとwindow平均の混同0。0台速度平均null。開始/終了/閉鎖境界、短edge飛越、class不許可laneをテスト |
| 技術ゲート・記録 | 未処理Error、teleport/collision/gridlockの許容は新PAPで固定。先行方針の0要件を勝手に緩和しない。不合格を保存、run再利用/上書き/削除禁止。スキル検証・正式記録完了後に次セルへ進む |

テスト案：最小の共通人物で3条件のmode転換・車乗員会計、0 fleet/0要求、行欠測と0台、閉鎖直前/同tick/直後、同時刻到着と満員、internal経由の閉鎖edge遷移、Gate等号不合格、R1への未来情報漏えいを検出する。大規模再runでテストを代替しない。

## 9. 既存公開APIとの接点・責任分界

| 調査したファイル・API | 既存の責務 / 新系列へ接続する際の判断 |
|---|---|
| scripts/jdrt/input_adapter.py::load_joso_input_bundle, JDRTInputBundle | v2用の凍結Type3/4人物/要求/5台を構築。新全人口版を上書き投入せず、新系列adapter/別版の責務として分離する案 |
| scripts/jdrt/controller.py::TraCIPort, SumoTraCIPort, JDRTController.step | 現在地・閉鎖適用・経路・状態更新の境界。True制御/知覚情報/監査観測を分け、既存step_busは対象外 |
| scripts/jdrt/dispatch.py::is_assignment_feasible, FloodRiskAwareDispatcher.select | bool選択APIを変えずside-channel記録するか、新系列で構造化評価へ分離するかは実装時判断。選択順序とtie breakを変えない |
| scripts/jdrt/full_run.py::FullRunTraCIPort.observe_step, build_result_rows | 毎step技術観測・60秒全体集計・人物結果の接点。道路class母数・全人口乗員・候補ログは現行出力だけでは不足 |
| scripts/scenario_c_car_walk.py::build_scenario_c_agent_types_for_rate | 年齢/保有配分の出典。人口版採用の研究判断をせず、再現可能な生成根拠として参照 |
| scripts/scenario_c_routes.py::build_pedestrian_network, pedestrian_edges, largest_pedestrian_component | 歩行net/対象edge/成分の責務。現実歩行可否・橋梁浸水の根拠を自動保証しない |
| scripts/scenario_c_integrated.py::run_integrated, initialize_person_state, add_disallowed_on_edges | R0の車＋徒歩制御・非投入人物保存・class許可。1秒前提の時刻/停止/距離積分は新刻み採用時に別系列で再設計が必要 |
| scripts/jdrt_realistic_r0.py::preflight, run, write_edge_congestion | 先行R0固有入力とFCD由来道路表。新3条件共通executorや完備edge観測の実装済み証拠にはしない |
| .agents/skills/joso-jdrt-runner/scripts/real_r0_cell.py | 既存先行R0系列のstatus/check/validate/record。新PAP承認前にstart-nextを呼ばない。新系列のスキル更新は実装段階の別作業 |

本書による公開API・研究入力・実行器・データ形式の変更は**なし**。上表の出力schemaは採用前の案であり、新実験の開始権限を与えない。

## 10. 根拠ファイルSHA-256

以下は読取調査時点のローカル一次資料。長い出力先の相対基点を明示し、code/config/inputのSHAを記録する。Web根拠は上記公式URLと確認日で示す。

基点：リポジトリルート。詳細な共通人口差は `06_研究結果/jdrt/データ取得監査/現実条件根拠検証_20261015.json` でも別計算した。

| 参照ファイル | SHA-256 |
|---|---|
| `04_プログラム/scripts/jdrt/input_adapter.py` | `edc4b770b6e2d7b60ea609b9984d4c0de04f1c17e040a2dfa94c665bfd5381b3` |
| `04_プログラム/scripts/jdrt/controller.py` | `135f0f41fe5c170b33a977b970cd7594d99b1a004e8aec62d4fc737f50f842d1` |
| `04_プログラム/scripts/jdrt/dispatch.py` | `ab8638e9963952bd435e4de2ec2c5b94124c0a4c6630eddc5c11f5963eb75a60` |
| `04_プログラム/scripts/jdrt/full_run.py` | `e269988275e078d1247b7013648b7a55e3701b5cbe7e7a52fb48d191489c3842` |
| `04_プログラム/scripts/scenario_c_car_walk.py` | `58d200cc58cdf2d9ac73a28e8c3f8fcc79e8dca417c59397d1f6c9387a939f07` |
| `04_プログラム/scripts/scenario_c_routes.py` | `285c64b334ae285c2684e637b9d27aaea169bb7600de35555e7f2c84ba26f348` |
| `04_プログラム/scripts/scenario_c_integrated.py` | `372712073c7281b8d2c50e514804b952a7401fdde78a0696a483962ec0f1c6a3` |
| `04_プログラム/scripts/jdrt_realistic_r0.py` | `24aed86a707f939175d2087a27240b8c9acb5e329fd4303835d2c58362f3dec3` |
| `.agents/skills/joso-jdrt-runner/scripts/real_r0_cell.py` | `77c84a4a4e4faa5f7b8728543b11e16dcebfd715a962922efd5ec77a55d20acc` |
| `04_プログラム/config/jdrt_parameters_v2.json` | `c878760eeff72b47110784f17bd98856dc292dd2fcb98636a42c632f6507b411` |
| `04_プログラム/config/jdrt_realistic_parameters_v1.json` | `605d83baf1065454449a255c18946ed50fa720d6d0b126c210d54d46982a3780` |
| `04_プログラム/output/sumo/regions/08211/derived/agent_types.csv` | `1d38fefd691c83b44a6b148678cce2fa4f7595ae2991e9291a7fb10d605f1c72` |
| `04_プログラム/output/sumo/regions/08211/derived/rescue_od.csv` | `493dbc46b7fad53b9ed65129bf5127dd3091a0a9a07ad6a82f4bba4ea3e2050b` |
| `04_プログラム/output/sumo/regions/08211/derived/shelters_sumo.csv` | `4f325976efd23af4c3c4fa716710b17375491d7c4d2f120e1cf1b24b80ce08fa` |
| `04_プログラム/output/sumo/regions/08211/experiments/scenario_c/inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_agent_types.csv` | `c3b703fc74a5072081a7d37e521893f133d95ac8a88ba3b7295b0d14c292ccb3` |
| `04_プログラム/output/sumo/regions/08211/experiments/scenario_c/inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_mode_ledger.csv` | `910a32b7e18dd03b7bbefb95ecab8ed6abf69bdc891669e629e43f53906df74f` |


### 時間軸の追加確認（2026-10-15）

既存閉鎖の元時刻は数日間をモデル6時間へ線形圧縮している。モデル900秒の誤差を実災害の15分と解釈しない。新系列の時計選択は[具体仮定案](常総市JDRT_現実条件版_仮定シナリオ設計案_v1.md)§1で採用前に判断する。

- `04_プログラム/output/sumo/regions/08211/derived/time_mapping_sumo.csv`：`2316f275396c9bacd48056733e4c3e2c706a45b922111c76ee185b49046b54a5`
- `04_プログラム/output/sumo/regions/08211/derived/closure_timeline_sumo.json`：`04b35335f8acf495e5e9f5916ad31d36900d1b4e66f8dd50fe1b07cc62d68e1f`


### 実時間再構築の採用判断

2026-10-15、ユーザーは「実時間6時間・15分を評価できる洪水入力の再構築を先行する」を選択。圧縮時計は新系列に採用しない。上記のclock/TBDは新しい非圧縮入力と初期状態・評価窓を取得/検証してから固定する。既存の入力・コードSHA表は旧系列の参照時点として保全する。
