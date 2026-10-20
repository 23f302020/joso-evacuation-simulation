# 受付・代替行動：実SUMO技術試験と起点位置の開始前監査

> 最新：2026-10-18。現行入力28/52unit/共通21/35改変/全14smokeと新READYの独立13検査PASS。初回core ch261018_002を開始し15分監視ACTIVE。正式記録0/70。最新状態はcontext/専用CLIを参照。本文の日付付き旧記述は実装経緯として保持する。

2026-10-17。最終goal ACTIVE。研究core 0、技術未READY。前回goal turnは新入力を作成・独立検証した**progress**、今回も実装と実測により次の作業を具体化したprogressである。待機/阻害による停止ではない。

## 1. 実装と実試験

`jdrt_realtime_choice.py`に登録済みの受付・受理・期限・乗降・取消・徒歩代替を実装した。旧境界整合の物理制御11関数を新ファイルへ複製し、旧ファイルは変更していない。新CLIにはstatus/check/smokeだけを提供し、core start/recordは未提供。本体もREADY証跡の必須項目欠落・空のchecksを拒否する。

18対象unitがPASS。無予測条件のfuture表を反復しない、入力時刻オフセット、READYなし/空チェックのcore拒否、SUMOが保持した過去経路prefixの返却を含む。期待する避難人数をunitへ固定していない。

技術試験は`joso-jdrt-runner`へ明示拡張して実施した。`skill-creator`を読み、quick_validateはPASS。旧系列のCLI/許可/実装SHAゲートは保全した。ローカルSUMOは1.26.0。公式Change Vehicle StateとローカルAPIを参照した。

| 試験ID末尾 | 結果 | 原因・処置・検証の位置づけ |
|---|---|---|
| probe_01 | FAILED保全 | appendWalkingStageの必須arrivalPos不足。停止解除直後の位置API無効値を厳密な同一座標判定でFAILとして検出 |
| probe_02 | FAILED保全 | arrivalPosを修正。走行中/交差点内取消は動作したが、駐車解除直後の座標無効値でFAIL。前後のlane位置/odometerを追加記録 |
| probe_03 | 4case PASS | 解除直後は座標を欠測として区分し、次の有効観測で同じlane進捗・連続odometerを確認。停止中の取消は再出庫せず待機へ変更 |
| probe_04 | 4case PASS | actual route/indexとsubscriptionを記録。SUMOが過去経路prefixを保持する事実を確認 |
| probe_05 | 現行コード4case PASS | 返却経路=SUMO実経路も検査。停止解除→300秒乗車→輸送→300秒降車、external取消、internal取消保留、期限同時取消→徒歩を確認。各case Error/teleport/衝突0 |
| smoke_01 | FAILED保全 | sumolib.getEdgesの既定withInternal=Trueを見落とし、internalの車道を禁止した。externalだけを対象に修正 |
| smoke_02 | FAILED保全 | setRoute後にSUMOが保持する既通過prefixを、実行器側で捨てたためindex不整合。実経路と実indexを保持するよう修正 |
| smoke_03 | 1800秒完走 | 23人/6要求の技術群。一次監査17項目PASS。ただし後続の原本保存等で実装SHAが変わっているため現行READY根拠へ転用しない |
| smoke_04 | 現行版1800秒完走 | 一次監査17項目PASS、実装SHA一致。正式run検証器・全14設定の証明ではなくcore採用不可 |

正式ID/開始終了時刻/PID/例外はworkspaceの`technical`・`smoke`のmanifestとdriver_logs/operations.jsonlを正本とする。IDはすべて`choice_*_20261017_*`。ディレクトリの再利用/削除/一次出力の上書きなし。15分より短く完了し、同じexec handleを完了まで確認した。旧15分監視はPAUSEDのまま、重複automationは作成していない。

probe_05とsmoke_04からは実行コードのバイト原本も`implementation/`へ保存しSHA一致を確認する構造にした。初期技術試行はコードSHAだけの記録であり、全試行にコード原本が保存されているとは主張しない。研究coreはまだない。

## 2. 一次監査の範囲と残り

[監査スクリプト](../../06_研究結果/jdrt/goal_20261017/G4_smoke一次会計監査.py)は、生成側の判定関数を使わず人物/要求/施設/eventを再会計し、要求状態列、乗降300秒、期限、取消後の代替、閉鎖全件・3時計、全道路の0件込み完全キー集合、全遷移、SHAを再確認した。smoke_04では道路1,648,518行、閉鎖6,783件、遷移1,025行を読取。source不変も確認した。

このPASSは**一次監査の範囲だけ**である。残るのは候補経路/現在速度/scoreの再計算、毎stepの二重移動/乗車とVKT、全coreの共通実現、故意改変拒否、全14設定smoke、失敗/窓末/満員/閉鎖と乗降を組み合わせた実SUMO反例、CLIの正式記録/復旧/共通実装ゲート。これらを満たすまでREADY・採用としない。研究効果の方向解釈を行っていない。

## 3. 新たに確認した起点位置の不整合

事実：登録origins表にはedge_idがあるが、道路内の人物/車両の縦断位置がない。現在コードの歩行者追加はpos=0、DRTのpickup stopは対象edgeの車道lane長−1m、私有車は既定のdepartPosである。接続158originのpassenger graph道路長は15.25〜489.77m。これは単なる表示の差ではなく、同一originという比較条件の物理的な実装を点検すべき根拠である。数値は[位置監査JSON](../../06_研究結果/jdrt/goal_20261017/G4_起点位置_開始前照合.json)を参照する。

徒歩を一方的に長く/短くしたり、DRTを瞬間移動させる方法は採らない。ユーザーの「より現実的なシミュレーション・数式から考察」の委任に従い、70セル開始前の必須整合課題CH-POSとして扱う。現行技術smokeで主要効果を判断せず、core 0の段階で全条件に共通な位置規則を事前固定する。

### 次に実行する順序

1. 原本origin座標とbounded netの座標系・offset・車道/歩道lane形状を照合し、選択済みedge上へ同じ起点を対応させる。位置データの追加で対象人口・edge選択・Type・意思/準備seedを再選別しない。
2. 原座標の道路への投影を第一候補にする。車体/stop位置の制約によるclampが必要なら、その移動量と理由を保存する。歩道は同じ迎車地点へ対応する位置を使い、モード間の縦断差・横断距離を検査する。無記録で端点へ移さない。既定の0/末端を維持する案と、一律末端へ移す案も比較し、根拠と限界を記録する。
3. 具体的規則が検証できた時点で、PAP/Registry/状態仕様へ実行前の変更理由・影響を追記する。変更前の文書/JSON/準備器をSHA一致で別アーカイブし、registered01と全smokeを履歴として保持する。新規入力版を排他作成し、旧manifestを手で書き換えない。
4. 起点位置、迎車stop、私有車出発、通常/代替徒歩の位置を同じ規則へ結合する。徒歩初期経路長には出発位置を反映する。迂回時の距離上限の適用範囲もPAPと実装で照合する。施設側の停車/歩行終点についても点検し、実態の入口測量と混同しない。
5. 新入力の独立再検証、実SUMOの元位置/stop/二重移動・距離、全14設定、正式検証/記録ゲートを通してから、同じ70セルを開始する。新しい研究結果を見て都合のよい条件だけを選択しない。

本書は投影位置を取得/採用したという宣言ではない。技術上の事実から次の作業を更新した記録である。取得済みの座標と座標系を確かめたうえで具体条件を固定する。Drive読取のみ、外部送信/公開更新なし。最終goalはACTIVE。

## 4. 駐車車両と配車用速度の照合も開始前に行う

コード上、DRTはSTOP_PARKINGのstopを使う一方、道路snapshotのgroupedには駐車状態による除外がなく、その速度0がtravel_secの更新にも入る。実SUMO試験でも駐車中と路上復帰の位置が異なることを観測した。現状のraw associated-edge観測を、そのまま走行車両の交通速度と同一視しない。

CH-OBSとして、ローカルSUMOの駐車状態API/edge観測を実試験で照合し、駐車・再出庫待ち・路上車両を区別する。raw件数の会計を維持しつつ、配車の交通速度へ何を使うかを明示し、PAP/観測仕様の実行前変更記録と現行全条件smokeへ結合する。現時点で新しいフィルタを採用/実装したとはしない。起点位置と併せてcore開始前に解消する。


## registered02：位置・観測・距離の登録と実行検証（2026-10-17T09:55:58.635552+09:00）

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0。位置/観測/距離の開始前追補を登録しregistered02を作成、独立入力28検査PASS（275地点、人口/需要/準備/終点/70セル不変）。共通乗降位置・前後を区別する経路・駐車を除く配車速度・毎step観測/徒歩距離を実装。23unit・現行実SUMO7case・D0/u05/R1/seed23423の1800秒smokeがPASS。一次会計17検査と位置/観測11検査で道路1,648,518行・actor25,169行・候補53行を照合。技術未READY。次は正式run検証器の候補選択/予測Gate全成分・最短経路・距離反例/故意改変→統合境界試験→全14設定smoke→record/preflight。旧15セル249根拠/4実装SHA・旧登録01と失敗試行は保全。旧監視PAUSED、Drive読取のみ、外部送信なし。

位置/観測の開始前追補はユーザーの最終goal委任と「より現実的なシミュレーション・数式」の判断軸に基づく。原座標の投影を採用し、一律末端への配置と既定posの維持は不採用。車道/歩道対応点差最大約2.61m、参照点アクセス最大約280.15m、65地点のclampを表に保存。参照点を入口測量とせず、仮想アクセス時間の共通省略を明記。旧PAP/Registry/設定/準備器等12ファイルをSHA付きでアーカイブし、旧registered01の源泉SHAも保存した。

probe06のfloat完全等値判定による失敗を保全し、before/after位置の不変を検査してprobe07で全7case PASS。その後の実行器組込後、probe08/09の全7case PASS。後方徒歩、任意stop位置、駐車をedge交通に含めないこと、stage置換で位置を維持することを実測。personinfoの過去walk length合算が再経路前後で二重計上するため、予定長/通過部分/速度積分を分離した。

smoke05は0.5秒で未挿入車両subscriptionの無効座標を欠測検出しFAILED保全。ローカルSUMOのgetPendingVehiclesとactive IDを照合する場合だけdeparture_pendingとして独立記録し、路上速度/走行距離へ加えない。原因不明の欠測は停止ゲートのまま。smoke06は1800秒完走。checkのWindows PID生存確認でWinError87を検出し、OpenProcessのSYNCHRONIZE権限とゼロ待機だけの読取処理へ変更。生存中の所有テスト子processを停止しないことと終了判別を検査。CLI自身を登録5実装SHAに含め、別の未追跡helperを増やしていない。smoke07実行中のcheckでRUNNING/pid_alive=true/sim660秒を確認し、同じhandleで完了を確認した。

現行smoke07はCOMPLETED、全3600step・1801controller・31snapshot、Error/警告/衝突/teleport/閉鎖後進入/曖昧遷移0。人口23/要求6の技術群であり研究人口の効果比較ではない。毎step25,169行は路上13,171・駐車11,936・再出庫待ち30・初回出発待ち32。独立監査が速度積分・車両/空車の観測距離・二重移動なし・全道路のraw/traffic分解・過去snapshotに基づく候補位置補正所要53行を照合しPASS。17+11の二監査ともcurrent_implementation_match=true、core_adoption_permitted=false。候補の最短性/選択/score/Gate全成分、stage再経路の距離反例、tripinfo末端VKT、故意改変、共通core実現、統合実行器fixtures、全14設定、record/preflightは残る。

新図は`03_研究設計文書/図表・UML/JDRT_受付代替行動_位置・観測・距離_v2.html`を独立生成し、旧v1は保全。生成根拠SHAと計算スクリプトを記録。旧15セルの249根拠と4実装SHAを再照合し全PASS。Drive編集/外部送信/公開更新なし。全試験15分未満、旧監視PAUSEDを維持。


## 候補独立監査とsmokeの分岐被覆（2026-10-17T10:03:43.325897+09:00）

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0。位置/観測/距離追補とregistered02の独立入力28検査PASS、23unit・現行probe10全7case PASS。予測なしと予測900秒smokeの候補最短性/全Gate成分/score/選択を独立監査した。短距離群だけでは予測残余が全件無限大のため、技術群に将来閉鎖経路を追加。現行R2P900 smokeは31人/10要求・1800秒完走、候補100行中有限予測/緊急度35行、一次会計17/位置観測11/候補選択13検査PASS・SHA一致。技術未READY。現在、R2P0/u50の追加7200秒smoke choice_smoke_u50r2p0_seed23423_20261017_01 を開始済み。次は同じrunをcheckし完了/例外を保全して3監査。その後、正式run検証器への統合・距離反例/故意改変・実行器の統合境界試験→全14設定→record/preflight。旧15セル/旧入力01/全失敗を保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

追加した独立監査G4_候補選択独立監査.pyは生成側の判定関数をimportせず、reverse距離で最短所要、全候補行列、actor実位置、登録位置、開通経路、各boolean/拒否理由、予測/所要、正規化score、tie選択と受付event、cycle件数を再計算する。R1_07と旧R2P900_01は13検査PASS。ただし初回は加算順の違い最大2.274e-13秒を数値不一致とした。失敗reportを別名保全し、合計の数値照合だけ1e-9秒の絶対許容差とし、Gateの厳密なboolean判定は別に検査する。

旧R2P900_01の候補53行は全てforecast_remaining=infinite、非ゼロ緊急度0であり、予測分岐の十分な被覆ではなかった。技術smokeだけ、既存終点経路に将来閉鎖を持つType3/4・意思マスク別の最大2人を追加し、対象ID・候補数をmanifestへ明示した。全研究人口・意思・準備seed・70セル・coreのHは変更なし。実装SHA変更前のsmokeと監査は履歴へ保全し、現行READYへ転用しない。probe10は7case PASS。現行R2P900_02は31人/10要求で完走し、候補100行中有限予測35・非ゼロ緊急度35。17+11+13項目PASS、Error/警告/teleport/衝突/閉鎖後進入/欠測0。ただしGateは全候補Trueで、短窓1800秒では閉鎖後の実行分岐を覆わない。

そこで登録済みR2P0/u50の追加技術smokeを7200秒まで進める。新IDはchoice_smoke_u50r2p0_seed23423_20261017_01、初回manifest status=RUNNING・PID=17784、開始=2026-10-17T10:02:44.241052+09:00。研究coreは0。実行中のコード/入力を変更しない。同じCLI check/handleで完了を確認し、終了後の3監査・分岐不足/例外を記録する。15分到達なら同じPID/時刻/進捗の観測を記録し、再起動しない。新core/監視再開は正式READY後だけ。


## 追加7200秒smokeの終了・三監査・候補故意改変（2026-10-17T10:06:32.953908+09:00）

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0。位置/観測/距離追補とregistered02の独立入力28検査PASS、23unit・現行probe10全7case PASS。有限予測経路を含む技術コホートを追加し、現行R2P900/u05の1800秒とR2P0/u50の7200秒smokeを完走。後者は31人/19要求、全道路6,434,538行・actor89,275行・候補180行を一次会計17/位置観測11/候補選択13検査で照合PASS、現行5実装SHA一致。候補の故意改変10種類を拒否。技術未READY・実行中0。次は徒歩再経路/距離上限・乗降と閉鎖等の実SUMO統合反例、候補13検査を含む正式run検証器へ統合、全14設定smoke、record/preflight。Gate偽20行はpickup経路なしとの重複で、forecast単独拒否や歩行再経路/上限停止の被覆は未完。旧15/旧登録01/全試行を保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

run=choice_smoke_u50r2p0_seed23423_20261017_01、開始=2026-10-17T10:02:44.241052+09:00、終了=2026-10-17T10:04:10.194470+09:00、実壁時計約86秒で完了。実行中に同じ専用CLI checkでPID生存・sim4860秒・例外なしを確認し、同じexec handleで完了まで待った。driver_logs/monitoring.jsonlへ経過/完了を保存。15分未満なので重複監視automationは作成していない。

一次会計は31人/19要求、全道路6,434,538行、閉鎖9,467件、遷移1,834行を照合PASS。位置/観測はactor89,275行（路上39,163・駐車50,048・再出庫32・初回出発32）、候補180行と車両/空車/徒歩速度積分/二重移動/道路分解を照合PASS。候補13検査は4stage/121cycle、最短経路・現在位置・全Gate成分/score/選択/受付を照合PASS。17/11/13は別々の部分検証であり、正式core採用を許可しない。全SHAは現行と一致。

分岐被覆の実測：{"finite_forecast_rows": 70, "gate_false_rows": 20, "forecast_as_primary_reject": 0, "walk_reroute_events": 0, "walk_budget_stops": 0}。Gate偽20行は排他的主理由no_pickup_routeであり、予測単独拒否を実行器で検証済みとはしない。徒歩再経路と上限停止も未発生。次はこの分岐を確実に発生させる実SUMO統合fixtureと正式検証器を先行し、単に同じsmokeの成功回数を増やさない。

G4_候補監査_故意改変試験.pyは、元runを編集せずメモリ上で位置/所要/予測時刻/score/選択欠落/候補欠落/Gate/path/urgency/有限値偽装NaNの10種類を変更し、それぞれ予定の独立検査で拒否した。道路観測は全時刻と非ゼロtrafficを保持する67行の読取fixtureへ縮約し、変更なしbaselineがPASSすることを先に確認した。完全な道路会計は別監査で全行照合済み。全core共通入力、歩行stageと末端VKT、全体会計/故意改変、統合fixtures、全14設定、正式CLI/record/preflightは未完。


## 共通実行器の統合16ケース・観測phaseと独立監査（2026-10-17T10:40:16.895761+09:00）

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0。registered02の独立入力28検査を保持、26unit・スキル検証PASS。本番と同じ実行器の人工16ケースがcf26101710で全PASSし、一次CSV/event/SHA・経路index/版・VKT末端補正・制御前後phase・道路全件再集計・native道路IDとの交通/駐車判定を独立検証PASS。毎step29,514行/snapshot actor231行の人工試験であり研究効果ではない。候補10種＋統合9種の故意改変を拒否。再経路後の速度上限逸脱を登録速度の再指定で修正、全初期試行と旧研究を保全。技術未READY・実行中0。次は正式run検証器への統合（全研究人口/共通実現、全観測/候補/会計、距離・閉鎖、採用境界/故意改変）→現行全14設定smoke→6ファイルrecord/preflight。旧監視PAUSED、Drive読取のみ・外部送信なし。

新実行器にはfixture専用入力モードを追加し、protocol=realtime_choice_fixture_v1、purpose=fixture、research_adoption_permitted=falseを固定する。入力は一意のtechnical/run_id/fixture_inputsだけを許し、core/smokeへ渡せない。実行結果は同run_id/executionへ保存する。人工網/人物/閉鎖/位置/設定とコード原本/SHAは実研究から分離した。現行suiteはcf26101710、開始2026-10-17T10:30:05.119190+09:00、終了2026-10-17T10:31:27.450441+09:00。同じhandle93904を完了まで観測し、RUNNING/PID生存・途中caseを確認した。全16件完了し、実行中0。いずれも15分未満で、旧監視はPAUSEDのまま。

初期失敗は全保全：choice_fixture_20261017_01は265文字の保存パスでSUMO起動前にFAILED、短いcase IDへ変更。cf26101702は0車両CSVヘッダ推定でFAILED、明示した列へ修正。cf26101703は人工網の歩道接続がなくcase FAIL、walkingareas/crossingsを生成。cf26101704はstage置換直後に歩行1.014978m/sを観測し上限1.0で停止、Stageに速度がシリアライズされないローカルAPIを確認し、置換後にsetSpeedを再指定。速度検査を緩めていない。cf26101705は8case後、予測拒否の後に実道路が閉鎖され新しい最短迂回路が現れると受付可能だったため、「永続拒否」という試験仮説が誤りと判明。T950（期限900より後）の純粋な予測拒否/timeoutと、T700の拒否→閉鎖後迂回→受付を別人工caseにした。旧runを改変せず、研究条件変更なし。10:14:58の操作logのRUNNING記述は古い進捗であり、当時の正本status=FAILEDであったことを後続訂正logへ残した。

cf26101706全13case、cf26101707/08全15case、cf26101709/10全16caseを完了。段階ごとの更新は後方車両の前進閉路/経路なし、私有車の閉鎖迂回event/経路版、毎step route_index/route_version、制御前後phase、snapshot_actor_observationsの追加。旧suiteとsmokeは履歴で、現行SHAのREADYへ転用しない。

独立監査はproducerをimportせず、全人数/要求・イベント鎖、厳密期限/300秒乗降、全閉鎖と3時計、毎step二重移動・速度上限/積分・車両/空車距離、実route index/版と閉鎖後進入、同phaseの全道路0件込み再集計、SUMO道路別IDとの交通/駐車判定、共有容量/退出、徒歩予算/再経路の通過分/位置、backend距離と到着末端/丸め、候補全成分/最短/score/選択を再計算。各case名の現象が実際に発生したことを別に必須検査し、空のループによるPASSを認めない。全16case PASS。毎step29,514行、snapshot actor231行は人工ケース合計であり実研究の人口/達成数ではない。

生のstop中断警告は迎車閉鎖のskips stop一件、乗車中/降車中閉鎖のaborts stop各一件を原文とcaseに分類して保持。Error/衝突/teleport/閉鎖後進入0。未知の警告を一括で無視する規則を作らず、正式run検証へ分類を移す。到着車両の距離差は、最後の観測lane位置から終点までの残りとSUMO文字列の丸め幅で検証。終点edge外の末端区間の一般化は正式検証器で証明が必要。

候補監査10種、統合監査9種のメモリ上の故意改変を全拒否。位置/index/phase・歩行速度/積分・backend VKT・乗車時間・snapshot速度・native駐車所属・再経路event欠落を検査し、原runは変更していない。監査器はSHA付きバイト原本をauditor_historyへ保存。新図v3は観測phase/index/到着末端を示す独立HTMLで、v1/v2を保全。26unitとスキル検証PASS。旧15セルの249根拠/4実装SHAとregistered02のsources/artifactsは再照合して不一致0。

次は[正式run検証器の統合手順](JDRT-受付代替行動_正式検証器_統合手順.md)に従い、全研究人口/共通実現、全観測/候補/会計/距離、採用境界と改変拒否をcanonical検証器へ統合する。その後に現行14設定smoke、専用CLIの正式記録・6ファイルtransaction/rollback、保存容量/単一writer/READYを完了してから70セルを開始する。部分監査や人工ケースのPASSを研究採用へ昇格しない。Drive編集/外部送信/公開更新なし。


### 専用CLI・開始証跡の実装 2026-10-17T17:53:53.225844+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY・実行中0。READY原本のrun内保存/一次証跡拘束、正式採用validate、6ファイルrecord/途中記録rollback/孤児復旧/単一writer/status/1セル起動を実装し、隔離48unit PASS。旧cf13全21とcf14単独は共通実装更新により履歴として保全。次は固定した共通5実装で全21ケースの実SUMO・独立再計算/故意改変→全14設定smoke→容量/READY生成を検証し、通過後70セルを逐次実行・15分監視。容量は実測拡大4倍＋5GiB余裕の1セル予約を毎回再確認し、残全件投影も明示する。旧系列/失敗/図v5は保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

READYは入力/全21/全14/現行unit/35種故意改変/実装5ファイル/SUMO・TraCI・NumPy/SciPy依存を一次成果物SHAへ拘束する。開始時に原本をrunへ保存し、正式採用で再照合。途中journalは保存before/plannedバイトとSHAからのみ復旧し、無関係な編集は自動上書きしない。Popen前に起動状態を確保し、child PID/セル/READY SHAが一致した内部executeだけを許す。新IDを使用、失敗も保全。

容量の技術判断：残全70件の悲観投影を一度に満たす制約ではなく、保存済みデータを保持して毎回1セル分の保守的予約を確認する。実測smokeのbytesを全人口・全時間へ拡大し4倍余裕＋5GiBを加える。全件が収まる保証とはしない。実core取得後は実容量も監視し、不足時は後続停止・保存先検討へ移る。観測縮減/旧run削除はしない。これは保存運用だけの判断でPAP/主要指標/比較/除外規則は変更しない。

48unit PASS（unittest対象4モジュール）。実READYは未生成・core開始なし。最終suite/all14とpreflightを実測するまで技術未READYを維持。


### 最終共通版21case開始 2026-10-17T17:54:24.039716+09:00

`cf26101715`、PID=29676、session79350。同じhandleを終了まで監視。技術試験のみ・本実験0。RUNNING中はscripts/入力変更なし。


### 最終共通版21case・独立検証完了 2026-10-17T17:57:50.037328+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、技術未READY。READY証跡/正式採用/6ファイル記録/復旧/単一writer/1セル起動を実装し48unit PASS。固定した共通5実装のcf26101715全21実SUMOケースと独立再計算がPASS、35種改変を拒否・一次357ファイル不変。全14設定smokeをcs261017aで逐次実行中（sequence session3285、各smoke完走・独立PASS後だけ次へ、失敗時停止）。次は全14/容量/READY生成を検証→70セル逐次実行・15分監視。旧系列/失敗/図v5は保全、旧監視PAUSED、Drive読取のみ・外部送信なし。

cf15: 17:54:03.358428〜17:56:10.390193 JST、PID29676、session79350 exit0。独立監査session76864 exit0。根拠：`06_研究結果/jdrt/goal_20261017/正式検証器_表会計候補_20261017T175640.json`。smoke14は同一common5で短縮H1800秒、各runのmanifest/CSV/独立検証を保持し、研究台帳には採用しない。稼働中コード/入力を編集しない。


### smoke同乗者準備時刻の独立検出・修正 2026-10-17T17:59:42.520861+09:00

{"at_jst": "2026-10-17T17:59:42.520861+09:00", "action": "smoke_private_crew_readiness_diagnosed_and_fixed", "failed_run": "cs261017a_01", "failed_sequence": "cs261017a", "sequence_session": 3285, "sequence_exit": 1, "reason": "index_mod10 per person overrode shared crew ready; 5 passengers moved before ready; FSM independent rejection correct", "disposition": "original manifest preserved and run INVALID via skill reject; no ledger adoption; no subsequent setting started", "research_input_crew_audit": {"23423": {"vehicles": 4424, "inconsistent": 0}, "42": {"vehicles": 4424, "inconsistent": 0}, "1": {"vehicles": 4424, "inconsistent": 0}, "7": {"vehicles": 4424, "inconsistent": 0}, "101": {"vehicles": 4424, "inconsistent": 0}}, "research_input_changed": false, "unit_PASS": 49, "implementation_sha256": {"04_プログラム/scripts/jdrt_realtime_choice.py": "ca7a5ceb7f07753100b7234e62f31c078ef92e82d13b6b30c748c334178f1c68", "04_プログラム/scripts/jdrt_realtime_choice_inputs.py": "4256cecd124bd83d35ef9c0f587edabbbe0e69e5a5d40ac23fe5bfe40ab2d05f", "04_プログラム/scripts/jdrt_realtime_choice_validate.py": "9f01a5ed79446a278fed8bd9be889d8286d3b5726463257e63030af8a22de034", "04_プログラム/scripts/jdrt_choice_policy.py": "f67811982026bb83944628fabe10844c62eb665809058a4a7c8ca30296a098c7", ".agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py": "b1b2831a4b79afe2fb3733498af387eb3b5a145ab5bfe32d5bf44672aad2120b"}, "next": "new full21 cf26101716 plus independent audit, then new14 sequence; prior cf15 historical after common source repair"}


### 進行記録の一時rename競合 2026-10-17T18:03:05.850560+09:00

{"at_jst": "2026-10-17T18:03:05.850560+09:00", "action": "smoke_batch_checkpoint_rename_failure_preserved", "sequence": "cs261017b", "core": 0, "simulation_started": false, "completed": 0, "failure": "WinError5 atomic rename of new sequence checkpoint before subprocess creation", "cause": "short-lived filesystem sharing conflict consistent with immediate retry succeeding; originating owner not identified", "repair": "batch checkpoint rename retries PermissionError at most6 attempts with0.2s spacing; persistent failure stops before next command; no common implementation change", "next": "new sequence prefix cs261017c, same current cf16/audit prerequisites"}


### 全14設定完了・開始前再照合 2026-10-18T09:48:28.032534+09:00

最終goal ACTIVE。受付・代替行動70セルは登録済み・研究core 0、実SUMO稼働0。専用CLI/READY来歴/正式採用/6ファイル記録/復旧/1セル起動を実装し49unit PASS。修正後cf26101716全21ケース・独立再計算/35改変・一次357ファイル不変がPASS、cs261017c全14設定smokeも2026-10-17 18:15:10 JSTに完走・各独立PASS。旧smoke時刻不整合と進行記録rename競合は理由付き保全。2026-10-18 09:45から現行入力28検査/49unit/全35技術run/容量のpreflight再照合中（session19561）。次はREADYを実証→新系列監視を整合→70セルを1件ずつ開始・15分監視・検証/記録。独立図v6を新規作成。旧研究と失敗保全、Drive読取のみ・外部送信なし。

根拠：`06_研究結果/jdrt/goal_20261017/最終14設定・共通21_技術証跡集計_20261018.json`。smoke列は18:03:06.804411〜18:15:10.291028 JSTで12分03秒、各runの開始/終了/PID/manifest/検証報告を保存。15分を超える単一技術runなし。cf16は17:59:50.796474〜18:01:52.408016 JST、PID5448・session67470 exit0。独立session75326 exit0。図v6は旧図と別ファイル、SVG XML/全ローカルリンクPASS・GUI描画未確認。


### Windows venv起動不成立・原本保全・修正 2026-10-18T09:55:18.852705+09:00

最終goal ACTIVE。受付・代替行動70セルの研究core 0・実SUMO稼働0。旧共通版は入力28/49unit/全21・35改変/全14smoke・1,190証跡でREADYだったが、初回ch261018_001はWindows venvランチャーと実行子のPID差を本人確認で拒否し、SUMO/研究run作成前に停止・原起動記録付きFAILED保全。PID親子確認と実行PID記録を修正、実project Pythonの予約executeハンドシェイクをSUMOなしで実証し52unit PASS。短期rename競合の限定再試行も試験済み。共通5実装更新で旧READY/全技術試験は履歴化、現行版をcf26101801→独立/改変→cs261018a全14→preflightの順に再検証する。監視jdrt-b-15は新系列設定を保持し再検証中PAUSED。次のREADY後に再有効化して新IDの最初の1セルを開始する。図v6/旧研究/全失敗保全、Drive読取のみ・外部送信なし。

{"at_jst": "2026-10-18T09:55:18.852705+09:00", "action": "windows_venv_redirector_identity_fix", "failed_launch": "ch261018_001", "research_run_directory_exists": false, "core_started": false, "unit_tests_pass": 52, "regression_evidence": "actual project venv Popen child/parent identities live; actual reserved execute handshake with only runtime.run mocked in isolated owned root; no SUMO/research writes", "repair": "accept exact reserved PID or Windows immediate parent launcher with liveness; save distinct launcher/executor PIDs; bounded6 PermissionError rename retries, persistent denial fails closed", "implementation_sha256": {"04_プログラム/scripts/jdrt_realtime_choice.py": "27d30780164733dc465d2874473755500cefe803c4dc068cef6051b9b61f2c68", "04_プログラム/scripts/jdrt_realtime_choice_inputs.py": "4256cecd124bd83d35ef9c0f587edabbbe0e69e5a5d40ac23fe5bfe40ab2d05f", "04_プログラム/scripts/jdrt_realtime_choice_validate.py": "9f01a5ed79446a278fed8bd9be889d8286d3b5726463257e63030af8a22de034", "04_プログラム/scripts/jdrt_choice_policy.py": "f67811982026bb83944628fabe10844c62eb665809058a4a7c8ca30296a098c7", ".agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py": "4841f1caf0399ac3e0190a2d11f9923363a84b863088891807980a1cc08c2846"}, "monitor_status": "PAUSED", "next": "new complete prerequisites via G4pipeline_20261018a", "summary": "最終goal ACTIVE。受付・代替行動70セルの研究core 0・実SUMO稼働0。旧共通版は入力28/49unit/全21・35改変/全14smoke・1,190証跡でREADYだったが、初回ch261018_001はWindows venvランチャーと実行子のPID差を本人確認で拒否し、SUMO/研究run作成前に停止・原起動記録付きFAILED保全。PID親子確認と実行PID記録を修正、実project Pythonの予約executeハンドシェイクをSUMOなしで実証し52unit PASS。短期rename競合の限定再試行も試験済み。共通5実装更新で旧READY/全技術試験は履歴化、現行版をcf26101801→独立/改変→cs261018a全14→preflightの順に再検証する。監視jdrt-b-15は新系列設定を保持し再検証中PAUSED。次のREADY後に再有効化して新IDの最初の1セルを開始する。図v6/旧研究/全失敗保全、Drive読取のみ・外部送信なし。"}
