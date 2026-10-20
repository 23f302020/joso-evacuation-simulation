# 常総市JDRT 実時間B Parameter Registry v1

登録：2026-10-16。研究条件の正本は[新PAP](常総市JDRT_実時間B_PreAnalysisPlan_v1.md)と[機械Registry](../../04_プログラム/config/jdrt_realtime_b_v1.json)。これは登録値・入力実測の閲覧用一覧である。

| 項目 | 登録値・位置づけ |
|---|---|
| 空間範囲 | USACE正面積セルunion。origin中心点が域内の人物全員 |
| 人物 | 11,965人、167起点。Type1=7,114、Type2=3,052、Type3=1,255、Type4=544 |
| 母集団の参照 | 元21,539人の人口・Type・乗員台帳。現在人口の実測ではない。域外9,574人は別台帳 |
| 私有車 | 4,424台の元乗員割当を保持。出発時刻は車両単位で共通 |
| 道路 | 外部edge17,812。追加の欠測79edgeを物理netに保持しつつ移動graphから隔離 |
| 除外理由 | 域外/一部交差30,417、路面高未検証構造1,044、way未対応4、地形/セル欠測79。現実の不通認定ではない |
| 洪水 | USACE 2015校正計算の水位−地形。実測ではない。5m以下間隔、全lane照合 |
| 時間 | 2015-09-10 12:50–18:50 JST、21,600秒、native73時点。時差タグは原本に無くJSTはイベント照合の解釈 |
| 閉鎖 | 車道0.5m、徒歩0.1m以上。native300秒の初回到達、区間保存、初期閉鎖保持、再開なし |
| 4施設 | 石下小195、水海道第一高519、水海道小193、豊田小100、合計1,007。開始時開設・初期0の仮定 |
| 退出 | 外周接続104。内部の橋梁除外切断を退出先にしない。主要受入分子へ加えず分母へ保持 |
| JDRT | Type3/4各50%の選択仮定。一般セダン4台、乗客3席、相乗りなし、仮想拠点shelter_3 |
| その他仮定 | 参照非保有率15%、準備0–7,200秒、乗降各300秒、margin300秒、通常流入/救援追加0 |
| 徒歩 | Type3=1m/s、Type4=0.58m/s、上限3km |
| 情報 | R0車+徒歩、R1予測なしJDRT、R2のみTrue閉鎖+900秒。閉鎖時刻の予測誤差 |
| 配車 | 待ち・pickupを実行可能候補集合でmax正規化（max0なら0）。脆弱性Type4=1。R2閉鎖緊急度は逆残余のmax正規化。重み各1、同点人物ID順 |
| Gate | pickup+乗車300+終点所要+margin300 < 予測閉鎖残余。等号は拒否 |
| 時計・観測 | SUMO0.5秒、controller1秒、配車60秒、全対象道路の0件を含むsnapshot60秒、全step遷移 |
| 主指標 | Type4全544人中の6時間以内域内施設受入。退出・不能・満員などを分母から除かない |
| セル | seeds23423,42,1,7,101、各R0→R1→R2、計15。全5seed前に方向解釈しない |

## 実装と検証の補足

歩行はSUMOのinternal/crossing/walkingarea接続を含む道路位相から経路を作る。striping初期化の制約により歩行laneの物理権限は残し、閉鎖edgeをcontrollerの徒歩graphから除いて経路変更/不能を記録する。全stepの実進入監査が0であることを採用条件とし、権限を残すことを通行許可の根拠にしない。普通車・JDRTは車道権限も閉じる。技術smokeは近距離人物のfixtureであり研究結果へ含めない。

入力manifestのBUILT_PENDING_INDEPENDENT_VALIDATIONは構築時の不変状態。採用ゲートは別のinput_validation.json（現行検証器SHA付きPASS）である。旧run・旧入力を上書きしない。

## 一次根拠

[入力manifest](../../04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_b/inputs/build02/manifest.json)・[入力独立検証](../../04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_b/input_validation.json)・[技術準備監査](../../05_タスク管理/jdrt/JDRT-実時間B_開始準備監査.md)。原本USACEのLifeSim人口・避難/死亡パラメータは導入していない。


## 実行器の技術版（2026-10-16 08時台）

過去走行routeが後の道路閉鎖で不正と判定されるSUMO setRoute制約を実SUMOで再現。新共通実行器jdrt_realtime_b_routehistoryfix.pyは、検査済み残経路を一意なroute IDで適用してから駐車解除する。位置/累積距離/所要時間維持と12テスト、3条件smokeを検証。原実行器は採用済みrunのSHA照合用に保持。研究入力・PAP・配車条件は不変。詳細は準備/進行監査とrecovery_r2_20261016。


## 徒歩閉鎖処理の技術版（2026-10-16 08:40）

新セルはjdrt_realtime_b_pedclosurefix.pyを使用。閉鎖発生時に交差点内部で保留した人物経路を各stepで再確認し、次道路が閉鎖済みなら進入前に停止、次道路が開通していれば安全な外部edgeに出てから再探索する。15単体テスト・3条件smoke PASS。入力/主要指標/速度/閾値/分母/検証ゲート不変。既採用runは旧実装SHAを保持し、比較前に版差影響を監査する。


### 車両交差点閉鎖の失敗保全・別版修正（2026-10-16T12:53:10.218838+09:00）

実時間B 8/15採用。R2 seed1 rtb_core_r2_seed1_20261016T123627は自家用車の閉鎖進入1件で独立FAIL、INVALID保全し後続停止。車両の交差点内保留後の再確認漏れを別実行器jdrt_realtime_b_junctionfix.pyで修正。18テスト・実SUMO交差点再現PASS、現行3条件smoke再検証中。PASSとpreflight READY後のみ同じR2 seed1を別IDで再開。入力/PAP/Registry/閉鎖進入0ゲート不変。旧8採用実装SHA一致、比較前の実装版影響監査を維持。

該当actor scen_c_origin_0228_0004は146#11→146#12をlower5999.5/upper6000.5、closure6000で進入。閉鎖時のinternal通過を時系列と実SUMO小型試験で再現。旧処理は閉鎖イベント時にだけ確認してinternalをskipし、既に進入決定した車両はlane permission変更だけでは停止しなかった。新処理は全stepで実route indexを用いて残経路だけ確認。次external閉鎖なら進入前にroute_cut除去し乗員を終端保持、次が開いて将来経路が閉鎖なら安全なexternalまで保留してreroute、走行済み閉鎖だけならclear。参照不一致を例外にし、路線再開/検査無効化/閾値緩和をしない。実SUMOではlegacyが21.0にinternal・21.5に閉鎖bへ進入、fixedは21.0に除去し進入0・両case Error0。試験初回のルートパス誤指定によるimport失敗はattempt00として保全。18テストの初回PASS後、ゲートに必要な実出力ログを保存するため再実行しPASS・SHA結合。新実行器/CLI/テスト差分・旧ソース/旧unit gate・8採用実装SHA照合はrecovery_vehicleclosure_20261016へ保存。既採用結果の版差の影響範囲を比較前に監査する。

新実行器SHA256：`f8215cee83cb6690a38bc59f62f412463e45add624b8b88aba67940982f3bcfe`。外部送信・Drive編集なし。


### 時刻境界の研究判断保留（2026-10-16T13:12:17.461950+09:00）

修正版R2 seed1 rtb_core_r2_seed1_20261016T125611もupper5400.0=closure5400の進入1件で独立FAIL・INVALID保全。unit18/3条件smoke PASSの実績とは区別し、運用ゲートHOLDで再起動を遮断。実時刻の適用と移動前制御の最大0.5秒先行の違い、既記録8セルとの比較条件、共通15セルの新規実行案を[再開判断案](常総市JDRT_実時間B_時刻境界・再開判断案_v1.md)へ保存し、ユーザー判断待ち。機械Registry/PAP/入力時刻は未変更。既記録8セルを新主比較から分離する案も未採用。
