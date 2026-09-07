# context.md — 現在地

> **性格：** 変更頻度が高い「今どこにいるか」だけを書く。恒久ルールは `CLAUDE.md`、過去の経緯は `00_全体整理/決定ログ.md`。
> **更新のしかた：** 状態が変わったらこのファイルを上書きする。経緯は消さず `00_全体整理/決定ログ.md` へ追記する。

**最終更新：** 2026-09-07（常総市限定JDRT v2中核7/20、seed 42は3/4）

---

## 一行で言うと

**Phase 1・2・3、主結論、先生コメント対応Scenario Cは確定済み。常総市限定JDRT v1は保全し、v2 seed23423完了・B3/B2/P1 seed42も全ゲートPASS、中核7/20。**

---

## フェーズ状態

| Phase | 内容 | 状態 |
|-------|------|------|
| Phase 1 | 自家用車避難（道路閉鎖＋Dijkstra・茨城県内41市区町村） | ✅ 完了 |
| Phase 2 | SUMO/TraCI 交通シミュレーション（41市区町村 small/10pct、full は代表6市区町村） | ✅ 完了 |
| Phase 3 | シナリオA/B比較・段3Rレプリケーション・感度分析・成果物化 | ✅ 完了（主結論ヌル確定） |
| 追加研究 | 先生コメント対応：車のみ詳細化・車＋徒歩Scenario C・同条件静的分析 | ✅ 全15run・統合評価完了 |
| JDRT | 常総市限定：動的配車・将来道路閉鎖情報の活用 | 🔄 v1は保全。v2 seed23423の4方式とB3/B2/P1 seed42がCOMPLETED/valid、全ゲートPASS。中核7/20、次はP2-L15 seed42 |

---

## 研究主結論（確定・2026-07-12／決定105〜111）

**主指標 Type3/4 避難完了率の A/B 差は「本モデルの分解能では検出されない」＝ヌル。**

- 15組合せの符号が非一貫（raw 正13/負2・保守 正13/負2）
- raw 点推定 **+1.234721%pt**・帯 **[−3.088349, +22.970757]%pt**
- 保守 点推定 **+1.209964%pt**・帯 **[−3.088349, +22.633452]%pt**（max=B#4対A#2・決定139）
- 帯がゼロをまたぐため **方向主張は全面禁止**

**副次的発見：** 強い初期条件感応性（regime bimodality）を第一級の発見として扱う。同一モデルでシードのみを変えたときの大差は、単一run避難シミュレーションの初期条件脆弱性を示す（決定107）。

**正本：** `開発メモ/方針判断_fable5/07_段4_結論・感度/段4_主指標ヌル確定_方針判断_fable5.md`

---

## 残タスク

| # | 内容 | 状態 |
|---|------|------|
| 1 | 既存A側正本3runから車のみ詳細データを再集計 | ✅ 完了（CSV 9種・67,174行、全検証PASS） |
| 2 | 公的なメッシュ別車保有データを調査 | ✅ 完了（直接250m値なし、PT市区町村集計は登録制） |
| 3 | 車・徒歩人口配分を正式化 | ✅ 完了（10/15/20%、各21,539人、重複・未割当0） |
| 4 | 歩行速度・浸水時歩行条件の根拠調査 | ✅ 完了（一般1.00m/s、高齢0.58m/s、STRICT/WADE） |
| 5 | Scenario Cの徒歩経路・車両route実装 | ✅ 完了（3感度入力、会計・SHA・1秒検査PASS） |
| 6 | 静的分析とSUMOの共通条件固定 | ✅ 完了（9,720経路行・72集計行、会計・閉鎖・SHA検証PASS） |
| 7 | Scenario Cの新規実験・評価 | ✅ 15/15run、CSV 11種・12,645行、再生成SHA一致、26テストPASS |
| 8 | JDRT実装方針・タスク管理・初期Python基盤・常総市workspace分離 | ✅ 完了（JDRT 25件、unit全体137件PASS） |
| 9 | JDRT Pre-Analysis Plan・Parameter Registry | ✅ 正式固定（B3対P2-L15、Type4主指標、5seed、8入力SHA） |
| 10 | JDRT常総市入力アダプター・run記録 | ✅ 人物3,255、request 1,440、車両5、避難所9、自家用車8,164、unit 146件PASS |
| 11 | JDRT TraCI controller・情報分離統合テスト | ✅ 全体165件PASS |
| 12 | JDRT小規模smoke | ✅ 閉鎖なし10要求・22人全員避難、閉鎖あり10要求・19人理由別終端、両方SUMOエラー0 |
| 13 | JDRT HTML | 第1・2段階✅、v2中核7/20の進捗へ手保守更新、実画面QA⚠️、第3段階は比較評価後 |
| 14 | JDRT中核full実験 | 🔄 v1は保全。常総市限定v2中核7/20。次はP2-L15 seed42 |
| 15 | 論文提出用編集 | 年末まで保留 |

**完了済みPhase 3へ追加run・追加seedを加えない。** AC7・不動点反復、第3巡、ダンピング反復、再配分変更は禁止のまま。Scenario CはPRE-8で承認された別実験15runだけを実行する。

詳細設計：`開発メモ/先生コメント対応_20260826/11_追加研究_詳細進行設計.md`  
タスク正本：`05_タスク管理/先生コメント対応_20260826.md`

JDRT実装方針：`03_研究設計文書/jdrt/常総市JDRT_実装方針.md`  
JDRT PAP判断入力：`03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_判断入力版.md`  
JDRT Parameter Registry判断入力：`03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_判断入力版.md`  
JDRT正式PAP：`03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_v1.md`  
JDRT正式Parameter Registry：`03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_v1.md`  
JDRT機械可読設定：`04_プログラム/config/jdrt_parameters_v1.json`  
JDRT v2正式PAP：`03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_v2.md`  
JDRT v2正式Parameter Registry：`03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_v2.md`  
JDRT v2機械可読設定：`04_プログラム/config/jdrt_parameters_v2.json`  
JDRTタスク正本：`05_タスク管理/jdrt/JDRT_実装タスク管理.md`

---

## タスク状態（Phase 3 実装・評価）

| ID | 内容 | 状態 |
|----|------|------|
| P2-DOC-2 | Phase 2本文を統合本文へ直接統合 | ✅ 完了（2026-07-22・単独ドラフトは重複のため作成しない） |
| P3-SEED | `--sumo-seed`：B側 `p2_traci_bus.py`／A側 `p2_region_pipeline.py` | ✅ 完了（`be1f50c`／`678cad2`） |
| P3-ROUTE | 確定route `scenario_b.rou.xml`（`3d6977…8297`・9,515台） | ✅ 復元（決定論的再生成・CRLF・第2巡route退避済） |
| P3-ARCHC | 先行条件C：B側archiveへ入力route同梱 | ✅ 完了（`419ceaf`・決定85） |
| P3-B5 | 段3 B確定run | 停止（不動点非収束）→ 段3Rへ移行 |
| P3-B5R | 段3R レプリケーション（B側5run＋A側3run） | ✅ 全8run完走 |
| P3-E1/E2 | 人単位・Type別評価と A/B比較 | ✅ 完了（帯付き実データ一本化・決定128〜140） |
| P3-E3/S/V | 主指標確定・感度分析・成果物HTML/Excel化 | ✅ 完了（E3本文確定稿・S系終了・V1〜V5・決定145〜149） |
| AUD-0〜5 | 監査 | ✅ 完了 |

**完了済み（P2-DOC系）：** 比較解釈（P2-DOC-3）・先生コメント対応表（P2-DOC-5）・図P2-5・表P2-4・表P2-6・SUMO引用/バージョン記録（P2-DOC-4 → `03_研究設計文書/phase2/Phase2_SUMO引用・再現性メモ.md`）・実装後検証チェックリスト（P2-DOC-6 → `06_研究結果/phase2/Phase2_最終検証チェックリスト.md`）

**完了済みタスクの詳細：** `05_タスク管理/phase2/Phase2_実装タスク管理.md`・`05_タスク管理/phase3/Phase3_実装タスク管理.md`

---

## 段3R レプリケーション実測値（参照用）

| 側 | run数 | 実測 |
|----|-------|------|
| B側 | 5run（seed 23423/42/1/7/101） | n' = {75, 122, 125, 125, 165}・**中央値125**・min–maxレンジ90 |
| A側 | 3run（seed 23423/42/1） | not_arrived = {479, 1854, 450} |

- 全run `git_dirty_scripts=false`・会計完全（各run arrived + not_arrived = 9,569）
- **A#2（not_arrived 1,854）は帯内保持・除外禁止**（決定81・99）。「モデルが初期条件seedに敏感である事実そのものが結果」
- B#4に `missing_fcd_count=2`（F級非該当・層分解引用時に注記義務）
- S系（バス10台感度・5run）：バス到着 n' = {120, 24, 180, 281, 257}・10台E1符号表 raw 正10/負5・非一貫 →「増車してもヌルは頑健」（決定115）

---

## 直近の同期記録

| 日付 | 内容 |
|------|------|
| 2026-09-07 | JDRT v2 P1 seed42 `core_v2_p1_seed42_20260827_codex01`の完走済み成果物を確認・独立検証。COMPLETED/valid、人物9避難＋3,246立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、Type4 4・Type3 5、DRT 49.229187km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,479行/SHA全PASS。中核7/20、途中比較なし、次はP2-L15 seed42 |
| 2026-08-27 | JDRT v2 B2 seed42 `core_v2_b2_seed42_20260827_codex01`完了。COMPLETED/valid、人物43避難＋3,212立ち往生＝3,255、request16完了＋1,424立ち往生＝1,440、controller21,600・観測43,200、teleport/collision/未処理Error全0。Parameter・入力8・出力9・event1,535行/SHA全PASS。中核6/20。途中比較なし、次はP1 seed42 |
| 2026-08-27 | JDRT v2 B3 seed42 `core_v2_b3_seed42_20260827_codex01`完了。COMPLETED/valid、人物57避難＋3,198立ち往生＝3,255、request22完了＋1,418立ち往生＝1,440、controller21,600・観測43,200、teleport/collision/未処理Error全0。Parameter・入力8・出力9・event1,567行/SHA全PASS。中核5/20。途中比較なし、次はB2 seed42 |
| 2026-08-27 | JDRT v2 P2-L15 seed 23423 `core_v2_p2_l15_seed23423_20260827_codex01`完了。COMPLETED/valid、人物8避難＋3,247立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、controller21,600・観測43,200、teleport/collision/未処理Error全0。Parameter・入力8・出力9・event1,483行/SHA全PASS。seed23423の4方式完了・中核4/20。途中比較なし、次はB3 seed42 |
| 2026-08-27 | JDRT v2 P1 seed 23423 `core_v2_p1_seed23423_20260826_codex01`完了。COMPLETED/valid、人物20避難＋3,235立ち往生＝3,255、request6完了＋1,434立ち往生＝1,440、controller21,600・観測43,200、teleport/collision/未処理Error全0。Parameter・入力8・出力9・event1,494行/SHA全PASS。中核3/20。P1は理論条件で単一セル解釈なし、次はP2-L15 seed 23423 |
| 2026-08-26 | JDRT v2 B2 seed 23423 `core_v2_b2_seed23423_20260826_codex01`完了。COMPLETED/valid、人物23避難＋3,232立ち往生＝3,255、request8完了＋1,432立ち往生＝1,440、controller21,600・観測43,200、teleport/collision/未処理Error全0。Parameter・入力8・出力9・event1,501行/SHA全PASS。中核2/20。単一セル間の方向解釈なし、次はP1 seed 23423 |
| 2026-08-26 | JDRT v2最初の技術ゲート`core_v2_b3_seed23423_20260826_codex01`完了。COMPLETED/valid、controller 21,600、0.5秒観測43,200、人物3,255・request1,440保存、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,553行/SHAを独立再計算し全PASS。避難53人（Type4 46、Type3 7）、完了request19、DRT 133.063kmは単一セル記述で方式間解釈なし。v2中核1/20、次はB2 seed 23423 |
| 2026-08-26 | JDRT-V2-I1完了。CLIでv1/v2設定を明示分離し、completedセルをParameter SHA単位で判定。SUMO 0.5秒stepごとに離脱・到着・teleport・距離を観測し、controllerは整数秒に1回だけ実行。collision/gridlock teleportをログから分離してvalid条件とmanifestへ追加。該当10件・unit全171件PASS、v2 B3 seed 23423 preflight READY（08211、人物3,255、request1,440、DRT5、自家用車8,164、入力SHA8）。v2 full runは未実施。次はB3 seed 23423技術ゲート |
| 2026-08-26 | ユーザー指示により実装対象を常総市08211だけに限定したJDRT v2を開始。v1 runは保全し比較へ混在させない。v2はSUMO step 0.5秒、controller 1秒、各step技術観測、collision action teleport、teleport/collision 0を固定。B2/B3/P1/P2-L15×5seedの全20セルを再実行し、最初のB3 seed 23423が不合格ならv2内で追加調整せず停止する。PAP v2、Parameter Registry v2、JSON設定、技術判断記録を実run前に作成・JSON構文とSHAを確認。現在は実行器改訂中、v2 run 0/20 |
| 2026-08-26 | JDRT-R2 teleport診断完了。固定seedのSUMOは同一条件で原則決定的、`time-to-teleport=-1`はgridlockだけを無効化し、衝突既定actionはteleport。4件は同一内部lane上の実衝突。無変更再実行・seed置換・衝突action無効化を却下。結果観測後にPAPを緩和せずR2を技術停止。再開には共通条件再設計とB2を含む中核20セルの新version再実行判断が必要 |
| 2026-08-26 | JDRT-R2 B3 seed 23423初回 `core_b3_seed23423_20260826_codex01` は完走したが、自家用車side collision teleport 4件により `status=INVALID / valid=false`。人物3,255・要請1,440の会計、Parameter・8入力・event・全9出力SHAは一致。Error 4件はcontroller捕捉済みroute拒否4、未処理0。正式比較から除外してrunを保全し、原因診断が終わるまで次セルを開始しない |
| 2026-08-26 | JDRT-B2 full正式セル `core_b2_seed101_20260826_codex01` 完了。3,255人中24人避難（Type4 9、Type3 15）、1,440要請中8件完了、DRT総走行33.821km、空車14.949km、teleport 0。Error総数1はcontroller捕捉済みroute拒否1、未処理0。人物・要請・Parameter・8入力・event・全9出力SHA検証PASS。B2全5seedが正式完了しJDRT-R1完了。次はR2 B3 seed 23423。方式間の方向比較はまだ行わない |
| 2026-08-26 | JDRT-B2 full正式セル `core_b2_seed7_20260826_codex01` 完了。3,255人中19人避難（Type4 9、Type3 10）、1,440要請中7件完了、DRT総走行35.137km、空車19.711km、teleport 0。Error総数1はcontroller捕捉済みroute拒否1、未処理0。人物・要請・Parameter・8入力・event・全9出力SHA検証PASS。B2は4/5、次はseed 101。方式間の方向比較は行わない |
| 2026-08-26 | JDRT-B2 full正式セル `core_b2_seed1_20260826_codex01` 完了。3,255人中18人避難（Type4 7、Type3 11）、1,440要請中6件完了、DRT総走行20.992km、空車7.744km、teleport 0。Error総数2はcontroller捕捉済みroute拒否2、未処理0。人物・要請・Parameter・8入力・event・全9出力SHA検証PASS。B2は3/5、次はseed 7。方式間の方向比較は行わない |
| 2026-08-26 | JDRT-B2 full正式セル `core_b2_seed42_20260826_codex01` 完了。3,255人中21人避難（Type4 7、Type3 14）、1,440要請中7件完了、DRT総走行22.376km、空車8.248km、teleport 0。Error総数1はcontroller捕捉済みroute拒否1、未処理0。人物・要請・Parameter・8入力・event・全9出力SHA検証PASS。B2は2/5、次はseed 1。方式間の方向比較は行わない |
| 2026-08-11 | JDRT-B2 full正式セル `core_b2_seed23423_20260811_codex10` 完了。3,255人中18人避難、1,440要請中6件完了、DRT総走行30.178km、teleport 0、人物・要請・SHA会計PASS。SUMO Error総数1はcontroller捕捉済みroute拒否1、未処理0としてPAPを技術的明確化。単一B2セルであり方式間の方向比較は行わない。全178テストPASS。次はB2残り4seed |
| 2026-08-11 | JDRT実SUMO smoke完了。SMK1は1台・10要求・22人が全員避難、状態event各10件、未処理0、SUMOエラー0。SMK2は789秒に580 edge閉鎖、配車前9件・迎車前1件を理由別終端、19人会計一致、SUMOエラー0。技術確認であり方式比較結果ではない |
| 2026-08-11 | JDRT TraCI controllerを実装。配車、乗車、避難所移動、降車、True closure適用、閉鎖後再経路、立ち往生を状態管理し、DispatcherにはPredicted closureだけを渡す境界を固定。JDRT 40件・全体161件PASS、実SUMO runなし |
| 2026-08-11 | JDRT入力アダプター・run記録基盤を実装。8入力SHA検証、人物3,255・request 1,440・車両5・避難所9・自家用車8,164・閉鎖8時点を読込。event/manifest上書き防止を含めunit 146件PASS |
| 2026-08-11 | ユーザーの明示許可によりCodexがJDRT条件を正式判断。B3対P2-L15、Type4 935人主指標、Type3/4 3,255人上限需要、fleet 5、5seedをPAP/Registry v1へ固定。8入力SHA・行数・会計PASS |
| 2026-08-11 | JDRT PAP・Parameter Registryの判断入力版を作成。HTMLトップを常総市中心へ更新し`jdrt.html`を追加。6ページ・189ローカルリンク欠落0、unit 137件PASS。実画面QAはBrowserのローカルURL制約で未完 |
| 2026-08-11 | JDRTを08211専用workspaceへ固定。他市町村SUMO出力40自治体・1,415ファイル・約3.74GBをSHA付きで`07_アーカイブ/`へ移動。全SHA一致、HTMLリンク切れ0、unit 137件PASS |
| 2026-08-11 | 常総市限定JDRTの実装方針→タスク管理→初期基盤の順で着手。domain/dispatch/validationを既存コードから分離し、JDRT 17件・unit全体129件PASS。full runなし |
| 2026-08-11 | C8-E1・DOC完了。15run統合評価CSV 11種・12,645行、再生成SHA一致、26テストPASS。追加runなし |
| 2026-08-11 | C4 3run完了、C8-R3完了。C4完了率中央値79.191235%。PRE-8全15runが有効完了、次はC8-E1 |
| 2026-08-11 | C3 WADE 3run完了・全技術PASS。完了率中央値74.706347%。run summaryはC1と全seed一致、解釈はE1まで保留 |
| 2026-08-11 | C8-R3 C3 WADEのseed 23423・1が技術PASS。seed 42実行中、全体有効11/15run |
| 2026-08-11 | C8-R2 C2感度6run完了。10%完了率中央値81.210827%、20%中央値75.077766%。全技術PASS、方向解釈は15run評価まで保留 |
| 2026-08-11 | C2 10% seed 23423を`bad allocation`後に単独再実行し技術PASS。C8-R2は有効5/6。元invalidは保存、次は20% seed 23423を単独再実行 |
| 2026-08-11 | C8-E0評価器実装。一次出力SHA再照合、15セル欠落・valid重複時停止。Scenario C関連25テストPASS。結果生成は15run後 |
| 2026-08-10 | C8-R1 C1基準3run完了。全run技術PASS、完了率中央値74.706347%、範囲73.392451〜75.611681%。次はC8-R2 6run |
| 2026-08-10 | C8-I2〜I4・TST・SMK1〜3完了。STRICT 8/8閉鎖・進入違反0・SUMO Error 0、WADE浅水低下→復帰5人、同一seed主要6ログSHA一致。次はC1基準3 full run |
| 2026-08-10 | C8-I1完了。3感度の全車人物を同一originの車両へ排他的に割当。4不足originを総数保存で補正し、乗員会計・20テストPASS。full run未実施 |
| 2026-08-10 | PRE-8で技術ゲート後の全15runを承認。実装を乗員会計・入力・動的制御・記録・評価へ分け、C8-D1〜DOCへタスク化。次はC8-I1 |
| 2026-08-08 | PRE-7統合実験前仕様完成。主指標を21,539人分母で固定し、3seed×基準・保有率・WADE・高齢者速度の計15run、人物会計、除外・停止規則を事前登録。PRE-8判断待ち |
| 2026-08-08 | S6同条件静的分析完了。405 origin×8時点×3方針の9,720経路行と72集計行を生成。会計、閉鎖集合、閉鎖edge通過0、11ファイル再生成SHA不一致0を確認。full run未実施 |
| 2026-08-08 | S5 Scenario C入力実装完了。pedestrian net、SUMO確定徒歩OD、3感度person・車tripを生成。15%は徒歩936人出力・2km超2,057人・経路なし238人・車7,960台。1秒検査全PASS、full run未実施 |
| 2026-08-08 | S1車のみ詳細再集計完了。A側正本3runからCSV 9種・67,174行とmanifestを生成し、全会計・再生成SHAゲートPASS |
| 2026-08-08 | 先生コメント対応の7段階を採用。詳細進行設計、タスク対応、経過報告への記録を完了。実装・runは未着手 |
| 2026-08-02 | 構成整理。`CLAUDE.md` を「振る舞い」「現在地（本ファイル）」「決定ログ」に3分割。研究内容の状態変更なし |
| 2026-07-22 | P2-DOC-2 を完了とした（統合本文へ直接統合済みのため）。論文提出用編集は年末まで保留 |
| 2026-07-20 | V5（HTMLダッシュボード最新化）完了・push `86a5990`。決定155〜158により HTML5ページ＋CSSは手保守正本 |
| 2026-07-18 | 実ファイル確認により E3本文確定稿・決定121/125・V1 Excel・視覚QA代替がすべて完了済みと確認 |
| 2026-07-13 | E3前 最終go/no-goゲート5条件すべてPASS（決定145） |
| 2026-07-12 | 研究主結論ヌル確定（決定105・106） |

---

## 参照先

| 知りたいこと | 見るファイル |
|-------------|-------------|
| どこに何があるか | `00_全体整理/INDEX.md` |
| 恒久ルール・禁止事項 | `CLAUDE.md` |
| 過去の判断経緯 | `00_全体整理/決定ログ.md` |
| Phase 3 進捗の詳細 | `05_タスク管理/phase3/Phase3_実装タスク詳細_常総先行.md` |
| 最終成果 | `06_研究結果/phase3/Phase3_研究結果.md`・`06_研究結果/研究結果・結論固定_20260721.md` |
