# 受付・代替行動系列：状態遷移と会計 v1

2026-10-17。protocol `realtime_choice_v1`。研究規則は[新PAP](常総市JDRT_受付代替行動_PreAnalysisPlan_v1.md)。本書は実装/検証に必要な粒度を固定する。新実行器は未READY。

## 1. 人物状態と要求状態を分ける

人物：not_ready → waiting_origin / travelling_walk / travelling_car。DRT利用者はwaiting_origin → assigned_origin → boarding → onboard → alighting → terminal。waiting_origin/assigned_originの取消後はfallback_pending → travelling_walkまたは徒歩不能理由による終端。boarding以後は取消して原点へ戻さない。

人物の最終結果と要求の結果は別列にする。例：要求cancelled_timeout、人物admitted_walkは両立する。要求servedであっても施設満員なら人物capacity_rejected。要求acceptedだけを避難完了へ数えない。

要求の結果はnot_requested（非意思者/R0）、pending、accepted、boarding、onboard、alighting、served、rejected_input、cancelled_timeout、cancelled_vehicle_failure、failed_after_boarding、time_limitに区分する。origin未接続/固定終点未設定は受付eventの後にrejected_inputと理由を残す。人物の終端はadmitted、boundary_exit、capacity_rejected、no_origin_connection、no_route、walk_limit、initial_or_current_closed、route_cut、stranded_drt、time_limit。途中状態を人物最終CSVへ残さない。終端理由と最終mode、初期意思・取消履歴を別保存する。

## 2. 時刻・遷移の契約

| 事象 | 条件・作用 | 必須event/列 |
|---|---|---|
| 準備完了 | ready_secに到達。非選択者は通常徒歩、選択者はoriginで要求1回。origin未接続も要求受付結果と人物不能を残す | person_ready、request_received、ready_sec/received_sec/deadline_sec |
| 受付待ち | pending、person=waiting_origin。徒歩actorを作らない。current graphで候補を評価 | cycle counts、candidate各項、origin閉鎖重複時間 |
| 配車受理 | idle車のみ、推定迎車到着<deadline、推定降車完了≤H、R2は追加Gate。1person対1vehicle | request_accepted、accepted_sec/vehicle_id、選択candidateキー |
| 迎車中 | person=assigned_origin、車両pickup。徒歩を開始しない。人はまだ車内人数へ入れない | vehicle active_person、pickup route、actual position |
| 未乗車取消 | now≥deadlineかつboarding未開始、または迎車車両の物理失敗。要求一度だけcancel | request_cancelled、cancel_sec/reason、cancelled_vehicle_id |
| 代替開始 | 同origin/同terminal、現時点の歩行経路と距離を検査。成功時だけ徒歩actorを1体作る | fallback_attempt、fallback_sec、route/length、actor ID |
| 乗車開始 | 車がoriginで実際に停止、now<deadline。person=boarding、request=boarding、車両boarding | boarding_started_sec、origin edge、vehicle ID |
| 乗車完了 | 開始から300秒。person=onboard、request=onboard、車内人数1 | boarded_sec、onboard_count |
| 降車開始/完了 | 実際の固定終点停止→300秒。完了後に共通施設会計/退出へ進む | alighting_started_sec、alighted_sec、onboard_count=0 |
| 窓末 | 進行中を人物time_limit。要求はserved/cancelled/failed等の既終端を保持し、進行中だけtime_limit | horizon_finalize、最終status、途中最後状態 |

同一controller時刻の順序は、①直前stepの到着/物理失敗、②現在時刻までの閉鎖、③期限取消（期限同時の乗車開始より先）、④準備完了/通常出発・代替、⑤車両の乗降状態更新、⑥終点到着・共通容量割当、⑦配車で固定する。物理閉鎖の先行0.5秒は毎stepで扱い、この整数controller順序から省略しない。到着/降車完了がHと同時なら採用可能、boarding開始がdeadlineと同時は不可。判定時刻は実eventから再計算する。

boarding開始後はdeadlineを越えても処理を継続できる。乗車開始から完了までの300秒に閉鎖で車両が失われればfailed_after_boarding/stranded_drt。まだ車内人数0でも原点へ戻して代替を発生させない。この区間を単なる配車受理と同一視しない。

## 3. 取消車両の物理的扱い

人の取消は迎車車両を削除/テレポートさせない。車内人数0、active_personを解除し、cancel_pending_vehicleを記録する。externalなら現位置から同edgeの安全な待機stopへ変更、internalなら次の開いたexternalへ出てから待機を設定する。その間は新要求へ割当不可。待機到達後idleへ戻す。閉鎖された次edgeなら通常の物理除去と車両failed終端を適用する。新規の初期depot出庫で置換しない。

旧予約のpickup stopが残っていないことを実SUMOで確認し、曖昧な車両位置やAPI失敗を黙ってidleへ変換しない。取消後の走行も総/空車距離へ含める。元request IDとの取消eventを残す。技術的にこの契約が達成できなければREADYにしない。

## 4. 不変条件と独立再計算

- 1人物の能動移動は徒歩actor、元自家用車乗員、DRT乗客の最大1。待機/迎車中は0。source IDも一意。
- 各要求は受付1回、配車受理最大1回、取消最大1回、代替試行最大1回。受付数=選択意思人数（R0は0）。未接続要求も受付後に理由付き終了し、欠落させない。
- 任意時刻にDRT車内人数≤1、車両active_personと要求vehicle_idは一致。acceptedとboardingは車内人数0、onboard/alightingは1。
- 人物全集合は最終statusで排他的全数会計。要求全集合は独自の最終statusで会計。要求取消を人物未完了へ一律変換しない。
- 受入人数=admitted人物数=facility会計の和。全mode共通容量超過0。受入は施設/退出と独立に再照合する。
- matched candidateはcycle/stage/time/vehicle/personキーが受理eventへ1対1。期限/H/Gateの各項をCSV・現在観測・Registryから再計算し、結果列のbooleanだけを信用しない。
- boarding_started<deadline、boarded−boarding_started=300、alighted−alighting_started=300。Hで打切られた区間は完了扱いにしない。
- cancel後にboarded/alightedが出ない。fallback actorはcancel以前に存在しない。boarding以後にfallbackは出ない。
- route/距離/閉鎖3時計/全step遷移/0件込みsnapshot/SUMO Error等は既存の厳格な独立検証を維持する。

## 5. 観測成果物

person_results：初期/最終mode、D、意思u05/u50、received/accepted/boarding_started/boarded/alighting_started/alighted/fallback/arrival/admitted各時刻、最終status/理由、固定terminal、origin、待機時の道路閉鎖重複。旧pickup_secの曖昧名はboarded_secへ対応列を明記する。

request_results：各要求ID/person/vehicle、受付・受理・取消・乗降の時刻、要求の最終status、取消理由、人物最終statusとの参照。R0は要求0行でもヘッダと0件manifestを作る。

events：全状態遷移のbefore/after、actor/request/vehicleキー、実時刻、reason、route/position。候補CSV、配車cycle CSV、施設/車両/道路/遷移CSV、SUMO/driverログ、共通実現表、manifestとvalidationを保存する。無限大はvalue空欄とvalue_kind=infinite等で表現し、missingと区別する。

## 6. 必須実試験

1. 未受理→期限同時取消→徒歩、配車済み迎車→期限取消→車両待機/徒歩、期限直前の乗車開始→300秒継続、期限同時は取消優先。
2. internal上の取消、取消後に残るpickup stopの除去、閉鎖された次externalの車両除去、元位置からの代替歩行。二重actor/架空の原点回帰0。
3. 乗車/降車各境界と閉鎖、満員時の要求servedと人物capacity_rejected、退出と施設の分離、窓末の全員/要求会計。
4. R0/R1に未来表を読ませないspy/改変テスト、予測表だけを変えたR2候補差、全14設定のsmoke、記録/再読/重複・部分書込拒否。

以上は期待する避難人数のテストではない。反例fixtureと原本再計算で、契約違反を検出するための検証である。
