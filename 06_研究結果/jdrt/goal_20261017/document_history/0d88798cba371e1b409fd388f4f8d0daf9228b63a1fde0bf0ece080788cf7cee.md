# 受付・代替行動：事前登録分析と一次出力の対応

2026-10-18。PAP §7と機械Registryの既存分析を実行するための対応表である。指標・比較・分母・除外規則を追加変更しない。研究結果は未集計で、技術smokeは列の存在確認にだけ使う。

## 分析開始条件

専用スキルから登録70セルすべてについて独立validate PASS、6ファイル記録完了、台帳のprotocol/cell/run一意を確認する。登録セル集合との一致、共通5実装SHA、入力manifest、各runの開始時READY原本と全一次出力SHAを再照合する。未完了・部分記録・未診断失敗・異なる実装・旧系列・fixture/smokeを混ぜない。欠けたセルを除いて主比較を発表しない。

## 指標の計算元

| 事前登録項目 | 一次出力・列 | 計算と検証 |
|---|---|---|
| Type4施設受入率 | `person_results.csv`: person_type, status, admitted_sec。`facility_results.csv`: terminal_id, capacity, admitted | 入力の全Type4を分母N4に保持。Hまでの施設受入人数/N4。人物受入と施設会計を照合し、要求servedや退出を受入へ加えない |
| Type3・全人口受入、退出・終点到達・理由別未完了 | person_type, status, arrival_sec, admitted_sec, terminal_id | statusと終点種別を併用。終点到達と施設受入を別集計。失敗・満員・未出発・時間切れを分母から落とさない |
| 全Type4未受入時間積分 | admitted_secとH、入力Type4集合 | U4=Σmin(Ai,H)/(H N4)。未受入・退出はAi=H。受入時刻0は欠測へ変換しない。これは域外危険時間ではない |
| 受付から各段階、取消・徒歩代替 | `request_results.csv`と人物表: received_sec, accepted_sec, boarding_started_sec, boarded_sec, alighting_started_sec, alighted_sec, cancel_sec, fallback_sec, deadline_sec, cancel_reason | 段階別人数と全要求の状態を残す。乗車完了と降車完了、要求servedと人物受入を区別。R0の要求0も明示 |
| 待ち時間と打切り | received_sec, boarding_started_sec, cancel_sec, deadline_sec、終了H | 全受付要求を対象に、乗車開始/未乗車取消/窓末未解消を区別して待ちの観測時間・終端種別を保存。完了者だけの平均を全要求の改善と呼ばない。空欄と0秒を区別 |
| origin閉鎖下の未乗車待ち | origin_ped_closed_wait_sec, origin_vehicle_closed_wait_sec | 歩道/車道を別集計。未乗車待ちとの重なりを意味し、死傷や屋内退避の安全性を推定しない |
| 総・空車走行 | `vehicle_results.csv`: kind, distance_m, observed_distance_m, observed_empty_distance_m | 私有車/DRTを分け、native距離と観測距離の検証済み会計を併記。空車距離を旅客距離へ足して二重計上しない |
| 候補拒否・選択 | `candidates.csv.gz`, `dispatch_cycles.csv.gz` | cycle/stageの全候補数、排他的主拒否理由と各booleanを別集計。候補0のcycleも残す。未来情報を読まないR1の契約を保持 |
| 全道路の0件込み観測・閉鎖進入 | `edge_observations.csv.gz`, `snapshot_actor_observations.csv.gz`, `transitions.csv.gz`, nativeログ | 制御後snapshotの同phase actorから再集計。駐車込みrawと配車用路上速度を区別。閉鎖予定/物理呼出し/観測上限と曖昧遷移を検証 |

列名は現行`cs261018a_02`のヘッダから確認した。実coreで全人口・全時間の会計が通ることは、列が存在するだけでは証明されない。各runの独立検証が必要である。

## 比較の行と分母

各D/u/seedでR1−R0、R2P900−R1、R2P0−R1、R2P900−R2P0を全件保存する。主指標は人数差と100×率差（%pt）を併記する。同一D/seedのR0は需要2水準で共用するため、重複した独立標本に数えない。D1−D0、u50−u05、差の差もPAPどおり条件付き機構診断として全件併記する。

5seedの各値・平均・最小・最大を出す。現実の母集団の信頼区間・有意差・因果効果の一般化に置き換えない。R2はGateと緊急度のパッケージ差、P0は入力格子上の診断条件である。新旧系列差を単一改良や予測情報の効果としない。

## 数式による制約の説明

入力の終点表からType4の施設固定数・手段別接続を再計算し、施設ごと人数njと容量CjによるΣmin(Cj,nj)を容量上限として示す。Type3等との共用、準備・移動・閉鎖・待ち期限があるため、この上限が達成可能人数を保証するとは説明しない。

乗降だけの仕事量比ρH=N(b+a)/(MH)は入力の要求数N・乗降時間b,a・台数M・Hから算出する。ρH>1なら全要求を乗降だけでも完了できず、ρH≤1でも移動/閉鎖/期限を含む実現可能性は保証されない。実受理・乗車・降車・施設受入と上限の差を一要因へすべて帰属しない。

取得済みの現行運用資料、2015年型水理のモデル入力、新規の需要/待ち/供給仮定、未取得の橋面高・災害時実測値を、最終報告で明確に区別する。提出用論文の編集保留は継続する。
