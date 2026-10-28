# 常総市JDRT 実装タスク管理

> 作成日：2026-08-11  
> 対象：常総市（08211）  
> 実装仕様：`03_研究設計文書/jdrt/常総市JDRT_実装方針.md`  
> 状態：v1は技術停止して保全。常総市限定v2中核20/20、seed 23423・42・1・7・101完了

## 1. 目的と範囲

### 現状把握・GitHub入口の更新（2026-10-28）

- [x] 現状把握MD/HTMLに、実験系列ごとの固定条件・変更条件・進行度・確認済み結果を掲載。
- [x] 現行native監査v3の正式記録済み9回について、人物CSVからType4全544人の施設受入・退出を再計算し、台帳・SHAと照合。
- [x] READMEを現在地・条件表・結果・正式記録の入口へ更新。10:43 JST時点の本実験稼働0と技術停止を区別。
- 表示・リンク・記録同期の確認範囲は[更新検証](../../00_全体整理/現状把握_更新検証_20261028.md)を参照。研究実行・再開・正式採用を追加する作業ではない。

既存Phase 1〜3と車＋徒歩Scenario Cを凍結したまま、常総市限定のJDRTを独立実装する。本表は、方針確立、研究判断、基盤実装、SUMO統合、実験、評価を順序付きで管理する。

PAP・Parameter Registry、常総市入力、TraCI統合、smoke、full実験器まで完了した。v1の強Baseline B2はpaired 5seedを完了したが、B3 seed 23423は自家用車の衝突teleport 4件によりPAPゲート不合格となった。v1の採用条件を緩和せず旧runを保全する。ユーザーの新version開始指示を受け、常総市08211だけを対象に、SUMO step length 0.5秒、controller 1秒、各step技術観測、衝突teleport 0を固定したv2 PAP・Parameter Registryを実験前に作成した。v2はB2を含む4方式×5seedを全て再実行し、v1結果を混在させない。v2実行器はParameter SHA分離、0.5秒観測、整数秒controller、衝突件数記録を実装し、unit全171件とpreflightを通過した。最初のB3 seed 23423技術ゲートは合格し、現在はv2中核20/20、seed 23423・42・1・7・101完了。

## 2. 進捗ボード

| ID | タスク | 状態 | 依存 | 成果物 | 受入条件 |
|---|---|---:|---|---|---|
| JDRT-D0 | 常総市JDRT実装方針を固定 | ✅ | ユーザー指示、Integrated Architecture v3 | `03_研究設計文書/jdrt/常総市JDRT_実装方針.md` | 境界、API、実装順、禁止事項が明文化済み |
| JDRT-TM0 | 実装タスクを依存順に管理 | ✅ | JDRT-D0 | 本ファイル | 研究判断、実装、実験が分離されている |
| JDRT-G1 | 新研究系列開始を現在地・索引へ同期 | ✅ | JDRT-TM0 | `context.md`、各索引 | 既存成果凍結とJDRT着手が両方記録される |
| JDRT-PAP0 | PAPの判断入力を作成 | ✅ | JDRT-D0 | `03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_判断入力版.md` | 固定候補と要決定事項が分離され、正式判断前にrunを開始できない |
| JDRT-PAP | Pre-Analysis Planを正式決定 | ✅ | JDRT-PAP0 | `常総市JDRT_PreAnalysisPlan_v1.md` | RQ、B3対P2-L15、Type4主指標、5seed、採用条件を結果確認前に固定 |
| JDRT-PR0 | Parameter Registryの判断入力を作成 | ✅ | JDRT-D0 | `03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_判断入力版.md` | 候補値、根拠区分、不確実性、感度候補が一覧化される |
| JDRT-PR | Parameter Registryを正式決定 | ✅ | JDRT-PR0 | `常総市JDRT_ParameterRegistry_v1.md`、JSON設定 | 根拠、不確実性、感度範囲、8入力SHAが記録済み |
| JDRT-I1 | ドメイン型を実装 | ✅ | JDRT-D0 | `scripts/jdrt/domain.py` | ID、状態、交通手段、予測情報を型で表現できる |
| JDRT-I2 | 実行可能性判定とDispatcherを実装 | ✅ | JDRT-I1 | `scripts/jdrt/dispatch.py` | B1〜B3/P1/P2の選択が決定論的 |
| JDRT-I3 | 会計検証を実装 | ✅ | JDRT-I1 | `scripts/jdrt/validation.py` | 重複手段、人口不一致、容量超過を検出できる |
| JDRT-I4 | パッケージ公開口を実装 | ✅ | JDRT-I1〜I3 | `scripts/jdrt/__init__.py` | 必要なAPIだけをimportできる |
| JDRT-TST1 | 初期基盤の単体テスト | ✅ | JDRT-I1〜I4 | `tests/unit/test_jdrt_*.py` | JDRT 17件、unit全体129件PASS |
| JDRT-ISO1 | 常総市08211専用workspaceを実装 | ✅ | JDRT-TST1 | `scripts/jdrt/workspace.py` | 他市コード拒否、JDRT runs以外を列挙しない。JDRT 25件PASS |
| JDRT-ARC1 | 他市町村SUMO出力のmanifest・復元手順を作成 | ✅ | JDRT-ISO1 | `07_アーカイブ/茨城県他市町村_SUMO_20260811/` | 40自治体・全1,415ファイルの元パス・容量・SHA・復元方法を保存 |
| JDRT-ARC2 | 他市町村SUMO出力を物理移動 | ✅ | JDRT-ARC1 | archive `regions/` | 約3.74GBを移動。08211と_managementを残し、削除なし |
| JDRT-ARC3 | 移動後のリンク・テスト・manifest検証 | ✅ | JDRT-ARC2 | manifest・地域一覧HTML | 全SHA一致、リンク切れ0、unit 137件PASS、常総市容量不変 |
| JDRT-WEB1 | HTML第1段階：常総市JDRT入口と計画説明 | ✅ | JDRT-PAP0、JDRT-PR0 | `output/index.html`、`output/jdrt.html` | 常総市を現在の中心として示し、未実施結果を掲載しない |
| JDRT-WEB2 | HTML第2段階：smoke後の技術説明 | ✅ | JDRT-SMK2 | `output/jdrt.html` | 構成、状態遷移、会計、技術テストを研究結果と区別して掲載 |
| JDRT-WEB3 | HTML第3段階：full実験結果 | ✅ | JDRT-E1、個人/mesh記述集計 | `output/jdrt.html`→`06_研究結果/jdrt/JDRT-v2_中核比較.html` | 一次CSVから生成した全20セル・主比較・定義/制限へ接続。値をHTMLへ手入力しない |
| JDRT-WEBQA | HTML構文・リンク・表示検証 | ✅ 対象ローカル確認 | 各WEB段階 | 下記2026-10-15完了後節 | 現在表示6ファイルの参照欠落0、対象HTML3件の構造不整合0。現状把握/入口/中核比較の実画面と入口→比較遷移を確認。公開版再配信・他画面幅は未実施 |
| JDRT-A1 | 常総市入力アダプター設計 | ✅ | JDRT-PAP、JDRT-PR、JDRT-TST1 | 正式JSON・入力SHA・公開型 | 08211正本だけを読み、既存ファイルを書き換えない |
| JDRT-I5 | 常総市入力アダプター実装 | ✅ | JDRT-A1 | `scripts/jdrt/input_adapter.py` | 人物3,255、request 1,440、車両5、避難所9、自家用車8,164、閉鎖8時点の会計一致 |
| JDRT-I6 | event log・run manifest実装 | ✅ | JDRT-I5 | `scripts/jdrt/run_records.py` | 独立run、設定・入力SHA、event SHA、finalize後追記禁止を検証 |
| JDRT-I7 | TraCI controller実装 | ✅ | JDRT-I2、I5、I6 | `scripts/jdrt/controller.py` | NetworkState経由の配車、乗降状態、True closure適用、閉鎖後再経路探索を実装 |
| JDRT-TST2 | 情報リーク・会計・route統合テスト | ✅ | JDRT-I7 | `tests/unit/test_jdrt_controller.py` | True/Predicted分離、1人1回の保存則、閉鎖進入、TraCI API境界を含む全体165件PASS |
| JDRT-SMK1 | 1台・約10要求の閉鎖なしsmoke | ✅ | JDRT-TST2 | `runs/smk1_no_closure_20260811_codex02/` | 10要求・22人、全員避難、全状態各10件、未処理0、SUMOエラー0 |
| JDRT-SMK2 | 1台・約10要求の閉鎖ありsmoke | ✅ | JDRT-SMK1 | `runs/smk2_with_closures_20260811_codex04/` | 789秒に580 edge閉鎖、配車前9件・迎車前1件を理由別終端、19人会計一致、SUMOエラー0 |
| JDRT-R1 | 強Baselineのpaired full実験 | ✅ 5/5 | PAP、PR、SMK2 | `core_b2_seed23423_20260811_codex10`、`core_b2_seed42_20260826_codex01`、`core_b2_seed1_20260826_codex01`、`core_b2_seed7_20260826_codex01`、`core_b2_seed101_20260826_codex01` | 事前固定5seedが全てCOMPLETED / valid、会計・SHA・teleport・未処理ErrorゲートPASS |
| JDRT-R2 | Perfect/Noisy Forecast実験 | ⛔ 技術停止（正式0/15・invalid 1件） | JDRT-R1 | `JDRT-R2_full実験記録.md`、validated runs | B3 seed 23423が衝突teleport 4でPAP不合格。受理基準を緩和せず、共通条件再設計の明示承認まで後続run停止 |
| JDRT-V2-PAP | 常総市限定v2の技術改訂を事前登録 | ✅ | v1 R2技術診断、ユーザー指示 | `常総市JDRT_PreAnalysisPlan_v2.md`、`常総市JDRT_ParameterRegistry_v2.md`、`jdrt_parameters_v2.json`、技術判断記録 | v1/v2分離、0.5秒step、1秒controller、衝突0、最初のB3ゲート、全20run再実行をv2 run前に固定 |
| JDRT-V2-I1 | v2実行器・manifest・衝突検出を実装 | ✅ | JDRT-V2-PAP | `scripts/jdrt/full_run.py`、unit test、`JDRT-v2_実装記録.md` | Parameter SHA単位の重複判定、0.5秒観測、整数秒controller、collision件数記録、unit 171件、preflight PASS |
| JDRT-V2-G1 | B3 seed 23423 v2技術ゲート | ✅ | JDRT-V2-I1 | `core_v2_b3_seed23423_20260826_codex01`、`JDRT-v2_full実験記録.md` | COMPLETED/valid、teleport・collision・未処理Error 0、controller 21,600、観測43,200、会計・SHA全PASS |
| JDRT-V2-R | v2中核4方式×5seed | ✅ 20/20 | JDRT-V2-G1 | v2 validated runs、`JDRT-v2_full実験記録.md` | seed 23423・42・1・7・101完了。直近`core_v2_p2_l15_seed101_20261015_skill01`、次は中核20セルの集計・評価 |
| JDRT-V2-SKILL | 1セル実行・検証・記録をリポジトリ内スキル化・モデル運用最適化 | ✅ | JDRT-V2-Rの運用実績 | `.agents/skills/joso-jdrt-runner/`、`JDRT-v2_セル検証台帳.jsonl` | 1セルずつ開始し、独立検証PASS後だけ5文書＋JSONLを同期。通常経路はtool対応の低コストモデル＋low/medium reasoningを許容し、異常・復旧・変更・研究解釈時は上位モデルへ昇格。構文、スキル構造、status、validate、record冪等性がPASS |
| JDRT-V2-AGENTDOC | エージェント読込文書を現行JDRT v2運用へ整理 | ✅ | JDRT-V2-SKILL | `AGENTS.md`、`CLAUDE.md`、`context.md`、各索引、公式調査メモ | AGENTS.mdを32KiB未満へ短縮、現在地読了境界・正本階層・1セル制約・記録規則を同期し、参照パス検証PASS |
| JDRT-E1 | 中核比較・登録方式の補助記述比較 | ⚠️ 主比較完了・副指標2項目未取得 | JDRT-V2-R | `06_研究結果/jdrt/JDRT-v2_中核比較_*` | 全20再検証・一次再集計、Type4/DRT対象全体、stranded、成功者P95、待ち、empty VKTと対応seed差を算出。PAP副指標の候補拒否と閉鎖後進入は直接復元不可。取得監査へ明記 |
| JDRT-S1 | 段階的Robustness | ⬜ | JDRT-E1 | 感度結果 | 全因子直積を避け、停止規則を満たす |
| JDRT-E2 | 個人・mesh・政策単位分析 | ⚠️ 個人/mesh記述済み | JDRT-E1 | `中核比較_individual_primary.csv`、`中核比較_mesh.csv` | 同一人物の獲得/喪失と地域集計を保存。現実政策効果・機構の因果解釈は取得不足と新系列PAPのため未完 |
| JDRT-REAL0 | バスなしを含む現実条件追加実験の詳細方針 | ⚠️ 方針固定・R0先行実体あり | JDRT-V2-R、ユーザー判断 | `03_研究設計文書/jdrt/常総市JDRT_現実条件追加実験_詳細方針_v1.md` | 先行R0の正式採用は保留。v2完了・評価後にデータ棚卸しと新PAP固定を行い、R0/R1/R2×5seedを独立系列で実施する |
| JDRT-V2-MONITOR | 全登録セルの監視・完了記録・独立一覧 | ✅ | JDRT-V2-R | `06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html` | 全20セルPASS/記録・一覧生成・表示確認済み、監視PAUSED |
| JDRT-DOC | 経過報告・論文・再現性記録 | 🔄 | 各段階 | 文書・図表 | B2全5セル、R1完了、R2初回invalidを方向比較なしで記録済み。各段階で同期継続 |

## 3. 現在からの実装順

```text
JDRT-PAP0 / JDRT-PR0 判断入力
    ↓
JDRT-PAP / JDRT-PR 正式判断
    ↓
JDRT-WEB1 常総市中心の入口・計画説明
    ↓
JDRT-A1 / JDRT-I5 常総市入力アダプター
    ↓
JDRT-I6 / JDRT-I7 記録・TraCI統合
    ↓
JDRT-TST2 / JDRT-SMK1 / JDRT-SMK2
    ↓
JDRT-WEB2 技術説明
    ↓
JDRT-R1 / JDRT-R2（v1技術停止・保全）
    ↓
JDRT-V2-PAP / JDRT-V2-I1 / JDRT-V2-G1 / JDRT-V2-R
    ↓
JDRT-E1 / JDRT-E2
    ↓
JDRT-WEB3 結果表示 / JDRT-WEBQA
    ↓
JDRT-REAL0 現実条件版のデータ棚卸し / PAP / 実装 / 中核15セル / 感度 / 評価
```

テスト不合格の場合は後続へ進まず、原因を当該タスク内で修正する。

## 4. 研究判断が必要な項目

以下は技術実装で独断採用せず、`05_タスク管理/スキル・エージェント運用.md` §0の「事実確認→選択肢・根拠・不確実性→ユーザー判断→事前登録→実装・検証」で確定する。旧特定モデルへの必須引継ぎは適用しない。

- Primary comparison
- Primary Outcome
- DRT利用対象者・利用率
- 救出走行置換規則
- fleet・定員・乗降時間
- safety margin・dispatch間隔
- 配車重みと政策目的
- 避難所利用条件
- seed・full run数・感度範囲

これらを初期Pythonコードへ正式値としてハードコードしない。

## 5. 実装不変条件

- 既存Phase 1〜3・Scenario Cのコードとoutputを変更しない。
- `step_bus`を変更しない。
- DispatcherへTrue Worldを渡さない。
- 1人1主要交通手段を維持する。
- DRT利用者と救出走行を二重生成しない。
- 車両定員を超えない。
- 人物最終状態の保存則を維持する。
- run出力を上書き混在させない。
- 研究指標をコード・テストへ正本値としてハードコードしない。

## 6. 停止条件

| 条件 | 対応 |
|---|---|
| 人物・交通手段・最終状態の会計不一致 | 後続実装とrunを停止 |
| DispatcherがTrue Worldを参照可能 | APIを修正するまで停止 |
| 同一入力で選択結果が変化 | tie-breakと入力順を修正 |
| capacity violation | 配車候補生成・検証を修正 |
| 既存Phase 1〜3ファイルへの意図しない差分 | JDRT変更を分離するまで停止 |
| PAP・Parameter Registry未確定 | smoke/full runへ進まない |
| 未処理SUMO Error、teleport、入力SHA不一致 | 当該runを不採用として保存し後続停止 |
| controllerが捕捉した個別bus route拒否 | Error総数と捕捉済み件数を両方保存し、当該bus/requestを理由付き終端。未処理0・保存則成立時のみrun継続 |

## 7. 状態記号

| 記号 | 意味 |
|---|---|
| ✅ | 完了・受入条件確認済み |
| 🔄 | 作業中 |
| ⬜ | 未着手 |
| ⬜ 判断待ち | 研究方針の正式判断が必要 |
| ⬜ 承認待ち | 実行前の明示承認が必要 |
| ⚠️ | 実装済みだが検証または外部条件が未完 |

## 2026-10-09 再開前監査と今後の方針

### 確認範囲と結果

現在地、恒久ルール、索引、JDRTタスク、v1/v2 PAP、v2 Registry・JSON、現実条件版方針・JSON、両系列のヘルパー・workflow、v2実行器の関連箇所、R0実行器、実験記録・台帳・manifest、関連HTMLを確認した。全研究ファイルの全文監査や凍結済みPhase 1〜3の再実行は行っていない。

- 再開時にPython/SUMOの稼働なし。B3 seed101に完了未記録セルがあり、独立検証PASS後にスキルrecordで同期した。
- v2の有効17セルをすべて独立再検証し、全件PASS。関連JDRT単体テストは59件PASS。git diff --checkは成功。
- 過去のFAILED/INVALID runは保全され、有効セルと分離されている。
- 評価JDRT-E1の依存先を停止済みv1のJDRT-R2からJDRT-V2-Rへ訂正した。
- jdrt.htmlの古い7/20とseed42次セル表示を除去し、進捗はcontext.mdを正本として確認する説明へ変更した。ブラウザ実画面QAは今回も未実施。

### 未解決事項と優先順

1. 現行v2を固定条件のまま完了する。残りはseed101のB2、P1、P2-L15。各セルで実行→独立検証→recordを完結させてから次へ進む。
2. 全20セルを検証・記録した後、PAPの同一seed P2-L15−B3差、中央値・最小・最大・符号、Type4/全体、未完了理由、待ち時間、P95、空車VKTを集計する。途中の方式間方向主張はしない。
3. 現実条件版の文書と実体を整合させる。REAL-R0には先行実装とseed23423のCOMPLETED/validセルがあるが、方針・決定ログはv2完了後の着手と新PAP固定を要求している。変更判断を確認できるまで正式採用と後続実行を保留し、既存runを保全する。詳細方針の「未着手」「残り6セル」も更新が必要。
4. R0ヘルパーの既存検証はPASSだったが、人物会計は主にengineのtechnical_validと行数を参照している。正式採用前に人物ID一意性、乗員対応、交通手段重複、完了人数、閉鎖イベント・未処理Errorを一次出力から独立再集計する必要がある。
5. 道路混雑CSVはFCDから車両が存在する道路だけを出力している。車両0の道路・内部交差点を含まないため、全道路の網羅観測とは呼べない。対象道路、0台行、時刻/道路IDの欠損基準、混雑の判定を新PAPで固定する。R0設定のstep/観測間隔は現状engine側の既定値への依存があり、設定との一致検証も必要。
6. R0の非保有率15%は実測値ではない。R1/R2の同一人物対応・利用率・予約時刻・fleet等を事前固定し、v2対象3,255人の値とR0全人口21,539人の完了率を直接比較しない。
7. 記録処理を改修する場合、文書と台帳のトランザクションを点検する。v2ヘルパーは5文書更新後にJSONLを追記し、全文書にrun IDがあると台帳確認前にALREADY_RECORDEDを返す。R0ヘルパーは実験記録と台帳の2ファイルだけを更新する。通常recordは今回成功したが、部分失敗時の復旧と全必須文書同期は別の技術修正候補である。

研究条件、採用ゲート、step_bus、凍結済み成果物は変更していない。既存dirty差分を戻していない。

**実行中（2026-10-09開始）：** B2 seed101 `core_v2_b2_seed101_20261009_skill01`。preflight READY、起動後checkはRUNNING/PID生存。完了後にvalidate→recordを行うまで次セルを開始しない。

## 2026-10-09 エージェント運用更新（完了）

ユーザー依頼によりAGENTS.mdを最新のOpenAI公式資料を軸に見直した。自律的な調査・新規実装・検証・記録、必要範囲の読込、重要操作前だけのFact-Forcing Gate、完了条件と研究判断境界を明記した。CLAUDE.md、モデル運用基準、JDRT SKILL.mdの重複指示を同期。旧モデル固定の分担は履歴として保全した。PAP・固定パラメータ・採用ゲート・実行器・run成果物は変更していない。UTF-8・コードフェンス・参照先・スキルmetadata・AGENTS.mdのサイズ（32KiB未満）・対象差分を確認した。コード変更を伴わないためシミュレーションと単体テストの再実行は行っていない。

## 2026-10-09 スキルによる継続運転と詳細記録の改善

確認日時：2026-10-09T15:37:17+09:00。

### 実行と観測

ユーザー指示「シミュレーションを進めてください。skillsを使用しシミュレーションをスタートさせ、skillsで更新が必要な部分は自由に更新して良い。進めるうえですべて詳細に適宜記録すること。（エラー・改善方法・更新内容も含めての挙動）」を受け、joso-jdrt-runnerで状態確認。B2 seed101 `core_v2_b2_seed101_20261009_skill01`は既に開始済みでPIDが生存しており、二重起動せず継続した。開始時のpreflight READY、v2固定条件は以前のdriver stateを参照する。

最新check：`{"last_event_sim_time_sec": 1560, "last_event_type": "REQUEST_ASSIGNED", "manifest_status": "RUNNING", "observed_event_count": 48, "pid": 5644, "process_alive": true, "ready_to_record": false, "run_id": "core_v2_b2_seed101_20261009_skill01", "started_on": "2026-10-09"}`。

最新status：`{"completed_unrecorded": [], "completed_valid": 17, "next_incomplete": {"scenario": "JDRT-B2", "seed": 101}, "recorded": 17, "running": [{"run_id": "core_v2_b2_seed101_20261009_skill01", "scenario": "JDRT-B2", "seed": 101}]}`。

直近event時刻はイベント観測であり、現在のSUMO時計や完了率ではない。driver stderrのこの時点の行数は `{"warning_lines": 167, "error_lines": 0}`。Warningには道路閉鎖後の出発edge不許可、経路なし、接続なし、緊急制動が含まれる。途中集計のErrorが存在すればcontroller捕捉済みかを完了時に独立検証する。途中のログ値だけで採用しない。run内SUMOログはこの時点でバッファリング中の可能性があり、driver stderrも保全する。

### 発見した問題・原因・修正

1. 旧recordは5文書を更新後、別処理で台帳へ追記していた。台帳書込失敗が文書のrollback対象外で、ALREADY_RECORDEDも台帳を確認しなかった。台帳を同じrollback範囲に含め、冪等判定とstatusに台帳確認を追加した。
2. 新照合で、旧実験記録の17セルに対し台帳は4セルしか登録されていなかった。台帳導入前の13セルをvalidateで独立再検証し、全PASS後にskill record処理で補完した。補完中の5文書はbyte単位で不変だった。現在は17セルで一致し、未記録0。台帳の行順は補完した実際の記録順であり、セル順はcore_indexで確認する。
3. 過去セル補完時に現在地が古い完了数へ戻る可能性を避け、後続セルが既に実験記録にある場合は台帳だけを補完する処理を追加した。過去の要約文書が最新run IDだけを持つ場合も考慮した。
4. CLI操作の時刻・timezone・コマンド・run ID・所要秒・結果・例外型/メッセージをdriver_logs/operations.jsonlへ保存するようにした。導入前の操作を遡って自動記録したとは扱わない。ログ書込失敗も明示し、実際のstart/record結果確認前に再試行しない。
5. checkへ完結したevent行数・直近event時刻/種別・driver stateの開始日を追加。書込中の未完結行を除外する。最初の実装確認でmanifestにstarted_atがないことを確認したため、実在するstate.started_onへ修正した。時刻を推測して補わない。

### 検証と制限

skill-creatorを使用。独立した一時ディレクトリへ正本記録をコピーし、記録冪等性、台帳欠落での次run禁止、台帳補完、書込障害注入とbyte復元、過去セル補完時の現在地維持、操作結果/例外の保存、event未完結行の扱いを検証した。最終回帰7件はすべてPASS（2026-10-09、1.028秒）。quick_validateはPASS、git diff --checkはPASS。

複数ファイルの更新は捕捉できた例外へのrollbackであり、電源断・強制終了・継続するfilesystem障害への完全なcrash atomic性は保証しない。同時に複数のrecordを実行しない。操作ログの保存にも同じ単一writer前提がある。記録用テストは実データの数値を一次資料から取得し、研究結果の期待値を固定しない。

変更ファイルSHA-256（今回の版の再現用）：

```json
{
  ".agents/skills/joso-jdrt-runner/scripts/jdrt_cell.py": "d7071a227b0ec55c12348991462ea021111c8b2d4251a82be934e47cfa943c62",
  ".agents/skills/joso-jdrt-runner/tests/test_recording.py": "93355ad641f1efb1268efb41ab46311346453a4aca8a7dbcbb35a3c4a9192afb",
  ".agents/skills/joso-jdrt-runner/SKILL.md": "4c6afb5bb5acb3ae62413f7b75aa6e77830b23f3a53aea0b63b93c111f779779",
  ".agents/skills/joso-jdrt-runner/references/workflow.md": "682748a805e440697e8c00accf5b4d92b79ef4892c0a58a6dc2060a48803ae03"
}
```

SUMO実行器、step_bus、入力設定、PAP、採用条件、run成果物は変更していない。実行中のB2終了後はvalidate→record→6成果物確認→status。PASSと記録確認が済むまでP1 seed101を開始しない。REAL-R0は正式採用保留を維持する。

## 2026-10-15 全登録セルの継続監視と結果一覧生成の準備

確認時刻：2026-10-15T09:53:02+09:00。

ユーザー指示「すべてシミュレーションを進め、進行状況を監視し、終了したら記録して。すべてのシミュレーションが完了したらすべてのシミュレーションの結果を一覧で表示する新たな独立ファイルを作成してください。」に基づき、現在登録済みのJDRT v2中核20セルを全件完了させる継続運用を開始した。凍結済みPhase 1〜3/Scenario C、保全v1、正式採用保留のREAL-R0を追加実行する指示とは解釈しない。

### B2 seed101の完了確認・正式記録

`core_v2_b2_seed101_20261009_skill01`は再開時にCOMPLETED/valid・PID終了・最終event21600秒だった。独立validate PASS後、スキルrecordで18セル目として採用し、5文書とJSONL台帳にrun IDがあることを確認した。人物42避難＋3213立ち往生＝3255、Type4完了13、Type3完了29、request17完了＋1423立ち往生＝1440。DRT総VKT103.91010651652621km、空車VKT69.76997524146276km、成功者P95 18322秒。Warning1439、Error1はcontroller捕捉済みroute拒否1、未処理0、teleport/collision/gridlock0。設定SHA1/1、入力SHA8/8、出力SHA9/9、event1551行/SHA、controller21600回、観測43200回が一致。指標はvalidate結果と不変成果物から取得した。

以前のタスク/経過報告の監視メモにもrun IDがあったため、recordのrun IDによる冪等判定は当該経過報告への新しい詳細節を省略した。完了値をこの節へ明記し、実験記録と台帳の正式結果も保持する。経過報告にrun IDがあることだけを新規完了値掲載の保証とは扱わない。

### 次セル開始と監視

P1 seed101 `core_v2_p1_seed101_20261015_skill01`をスキルstart-nextで開始。preflight READY、v2/0.5秒step/1秒controller、8入力SHA、3255人・1440要求・DRT5台・自家用車8164台を確認。新規runであり既存runの再利用なし。

最新check：`{"last_event_sim_time_sec": 60, "last_event_type": "REQUEST_ASSIGNED", "manifest_status": "RUNNING", "observed_event_count": 6, "pid": 6160, "process_alive": true, "ready_to_record": false, "run_id": "core_v2_p1_seed101_20261015_skill01", "started_on": "2026-10-15"}`。

最新status：`{"completed_unrecorded": [], "completed_valid": 18, "next_incomplete": {"scenario": "JDRT-P1", "seed": 101}, "recorded": 18, "running": [{"run_id": "core_v2_p1_seed101_20261015_skill01", "scenario": "JDRT-P1", "seed": 101}]}`。

このchatのheartbeat監視automation IDは`jdrt-v2`、名称は「JDRT v2 全セル完了・結果一覧の監視」。15分間隔、ACTIVEとして作成・view確認済み。実行中はcheck、完了時はvalidate PASS→record→6成果物確認→statusの後だけ次の1セルを開始する。P1の次はP2-L15 seed101。正常で変化のない確認は通知しない。意味のある進捗・異常・全完了と一覧完成を通知する。孤立RUNNING、FAILED/INVALID、SHA/会計不一致は後続開始を止め、原因調査・対応・必要な判断を記録する。定期監視はローカルアプリ/実行環境が利用可能なときに動作する。

### 独立結果ファイル

生成器：`.agents/skills/joso-jdrt-runner/scripts/jdrt_results.py --project-root .`（専用venv Pythonで実行）。

生成先：`06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html`。この確認時点では未生成。全20セルの完了・記録、実行中/未記録0、最終セルの5文書同期、全セル独立再検証PASSを満たした後にだけ新規作成する。未完了/未記録/重複/不合格なら既存ファイルも書き換えない。

一覧はオフラインで開ける単独HTML。全採用セルの方式・seed・run ID、Type4人数/935と率、DRT対象完了人数/3255と率、Type3完了、立ち往生、要求会計、成功者P95、総/空車VKT、Warning/Errorの処理内訳、teleport/衝突、controller/観測回数、SHA検証を表示する。母数は設定から取得し、人口全体21539人の完了率とは区別する。同一v2設定の採用外runを別表にし、一次manifestへのリンクと生成元SHA・独立検証詳細を埋め込む。途中の優劣主張はしない。

全件完成後は結果ファイルを開き、現在地・タスク・索引・決定ログ・経過報告を更新して通知し、automation `jdrt-v2`をPAUSEDへ変更する。正式PAP未固定の追加系列へ自動拡張しない。

### スキル更新・検証・制限

skill-creatorを使用し、一覧生成器、`tests/test_results.py`、SKILL.mdとworkflowの監視/一覧手順を追加。全体索引へ生成器を登録。テストは既存7件と新規3件の計10件PASS（1.417秒）。検証対象は記録rollback、台帳補完、実行中event行、途中一覧拒否、失敗時の既存出力維持、一次記録からの全行表示・分母・HTMLエスケープ。quick_validate PASS、構文解析PASS、git diff --check PASS。

実環境で生成コマンドを実行し、18/20・P1実行中のためNOT_GENERATED/ValueError・終了コード1で停止し、完成版ファイルが存在しないことを確認した。これは意図した未完了ゲートで、シミュレーションエラーではない。全20セル揃った状態の最終生成・実画面検証はその時点で実施する。

固定PAP・入力設定・実行器・step_bus・run成果物は変更していない。操作と診断の一次ログは`experiments/jdrt/driver_logs/operations.jsonl`と各runのevent/SUMO/driverログに保全する。

## 2026-10-15 監視：P1 seed101採用・最終セル開始

確認日時：2026-10-15T10:35:40+09:00。heartbeat `jdrt-v2`による継続処理。

`core_v2_p1_seed101_20261015_skill01`のCOMPLETED/valid、PID終了、最終event21600秒を確認。スキルvalidateはPASS、recordはRECORDED（19/20）。5文書とJSONL台帳へのrun ID反映、未記録0・RUNNING0を確認した後、最後のP2-L15 seed101をstart-nextで1セルだけ開始した。正式結果は以下のとおり。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 22 / 3,233 |
| Type4 / Type3避難完了 | 17 / 5 |
| 完了 / 立ち往生request | 7 / 1,433 |
| DRT総VKT | 63.826115 km |
| 空車VKT | 43.026289 km |
| 到着時刻P95 | 8,375 sec |
| event | 1,495 |
| Warning / Error | 1,205 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

設定SHA 1/1、入力SHA 8/8、出力SHA 9/9、event SHA、人物・request会計、VKT・ログ集計を独立再計算し全PASS。Errorは全件controller捕捉済みroute拒否で未処理0。採用条件を緩和していない。既存監視メモのrun IDにより経過報告の完了詳細追記が省略され得るため、この節でも結果を明記した。

最終セルrun ID：`core_v2_p2_l15_seed101_20261015_skill01`。preflight READY、固定v2設定と8入力SHAを確認。起動後check：`{"last_event_sim_time_sec": 0, "last_event_type": "CORE_RUN_STARTED", "manifest_status": "RUNNING", "observed_event_count": 1, "pid": 24960, "process_alive": true, "ready_to_record": false, "run_id": "core_v2_p2_l15_seed101_20261015_skill01", "started_on": "2026-10-15"}`。

全20セルの採用完了前なので方向解釈と完成版一覧の生成は行わない。監視を継続し、終了時validate→record→6成果物確認→全セル再検証→独立HTML生成・確認・通知の後、監視を停止する。PAP・設定・実行器・run成果物の変更なし。操作の原ログはdriver_logs/operations.jsonlと各runのevent/SUMO/driverログに保存。

## 2026-10-15 全20セル完了・独立結果一覧作成

確認日時：2026-10-15T11:23:30+09:00。最終セル`core_v2_p2_l15_seed101_20261015_skill01`はCOMPLETED/valid、PID終了、最終event21600秒。独立validate PASS後にskill recordで正式採用。5文書とJSONL台帳の反映・実験記録を確認し、statusは全20セル完了/記録済み、実行中0・未記録0・次セルなし。

### 最終セルの実測とError分類

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 10 / 3,245 |
| Type4 / Type3避難完了 | 6 / 4 |
| 完了 / 立ち往生request | 5 / 1,435 |
| DRT総VKT | 59.043182 km |
| 空車VKT | 33.841274 km |
| 到着時刻P95 | 3,778 sec |
| event | 1,482 |
| Warning / Error | 1,158 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

設定SHA 1/1、入力SHA 8/8、出力SHA 9/9、event SHA、人物・request会計、VKT、ログ・観測回数を独立再計算して全PASS。Error5件はすべてcontroller捕捉済みの個別route拒否。未処理Error・teleport・collision・gridlockは0。採用条件を変更していない。

### 全件再検証と一覧の成果物

スキル`jdrt_results.py --project-root .`で登録済み全20セルを独立再検証し、全PASS後に`06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html`を生成した。HTML SHA-256：`51cdd203559d3fbdcb537331d8295fe59e1e25f91481b6b55fc41bc648f74434`。

HTMLの避難結果20行、技術検証20行、manifestリンク20件、方式/seed重複なし、全20件の検証PASS、生成根拠25ファイルのSHA一致を照合した。採用外runは別表1件で採用結果に混在しない。人数・明示母数の率・要求会計・P95・VKT・Error処理内訳・観測回数と全独立検証証跡を保存。P95は成功者のみ、DRT対象完了率は人口全体の完了率とは区別する。今回は実測値の記述一覧であり、対応seed差・感度・個人/mesh評価の完了を意味しない。

### 表示確認・記録・監視

保存済みHTMLをCodexで開く操作は非表示chatのためqueued。さらに127.0.0.1のみの一時HTTPサーバー経由でCodexブラウザに表示し、タイトル、20/20表示、全行とPASS、採用外run表、折畳み検証証跡を確認。狭い表示幅の本文折返しと表の横スクロール領域を実画面で確認した。一時サーバー/タブは確認後終了する。HTML自体はオフライン閲覧可能。

全体索引・研究結果README・タスク・context.mdへ成果物を登録。heartbeat `jdrt-v2`の依頼対象は完了したため停止手続きに進み、結果を追記する。REAL-R0の正式採用保留、凍結済み系列の保全を維持。後続runは開始しない。

停止設定取得時にWindows出力文字コードによるJSON解析エラーが1回発生した。設定は変更されておらず、ensure_ascii=TrueでASCIIエスケープして読み直し正常取得した。研究成果物への影響なし。操作/診断の原ログとError・改善履歴はdriver_logs/operations.jsonlと既存run/タスク/経過報告に保全。

完了処理確認（2026-10-15T11:24:05+09:00）：automation_updateは`jdrt-v2`のPAUSEDを返し、保存済みautomation.tomlもPAUSEDと一致。一時ブラウザタブと127.0.0.1表示確認サーバーを終了した。HTML取得はHTTP200、未設定favicon.icoのみ404で一覧表示や研究結果に影響なし。最終状態は全20セル記録済み・実行中0・未記録0。独立HTMLは保存済みであり、サーバーなしで閲覧できる。


## 2026-10-15 完了後の主比較・データ取得監査・文書同期

ユーザー依頼により、全20セル完了後の現状把握md/htmlと古い現在表示を監査し、指定Google Driveのデータ分析フォルダを読み取りのみで確認した。詳細の作業順・分担・受入条件は[JDRT-v2_完了後方針・タスク](JDRT-v2_完了後方針・タスク.md)、取得項目と不足・先行R0の扱いは[データ取得監査](../../06_研究結果/jdrt/JDRT-v2_データ取得監査.md)を正本とする。

### 実施と検証

- 文書担当、登録済み分析担当、R0/取得品質担当を分担し、統括がDrive照合・方針・記録・別実装検証を担当した。ユーザー選択のモデル/推論設定は変更していない。
- joso-jdrt-runnerのstatusでv2全20採用・記録済み、実行中0・未記録0を確認。新シミュレーションや正式セルrecordは不要だった。
- 新規分析器`04_プログラム/scripts/jdrt_v2_analysis.py`で全20を既存スキルのcollect/validateに通し、人物/要求の静的対応、凍結グループ割当、未完理由、時刻、P95、車両別輸送、VKT、主差/要約、分析前後の全runファイルSHAを照合した。
- 比較CSV8種53529行・報告md・比較HTML・manifestを`06_研究結果/jdrt/`へ作成。出典298SHA・出力10SHA。統括の`データ取得監査/verify_analysis_readback.py`で出典/出力SHA、全20人物CSVからの主差・成功者P95、保存要約を別計算しPASS。
- 主比較P2-L15−B3のType4率差は全5seedで負。値・母数・獲得/喪失・時間/負荷は生成報告へ集約する。仮説と反対の結果も採用し、条件やseedを変更しない。現実政策効果や既存Phase 3へ一般化しない。
- PAP副指標のGate候補別拒否数/理由と全車両の網羅的閉鎖後進入は未取得。DRTの観測済みCLOSED_EDGE_ENTRY理由は保存されている。主比較完了と全副指標完了を区別し、E1/E2を条件付き状態で管理する。
- 先行REAL-R0は独立CSV検査23項目PASS、読取元27SHAを新規JSONへ保存。人物/乗員/車両保存は成立する一方、v2とはType別分母・人物対応が異なり、道路出力は0台行のない部分観測。sumocfgのstep既定値依存とengine終了時刻21601秒も未解決として保存した。正式採用や後続runを行わない。

### 古い表示と不具合の処理

1. 現状把握md/htmlの14/20・残り6回・次P1 seed7、ルート/プログラムREADMEの7/20等を最新状態へ更新。output/index.html・jdrt.htmlの現在説明、正式中核名称、生成結果リンクを整合させた。既存dirty差分は戻していない。
2. 現実条件詳細方針の「実装・run未着手」と残り6セルを、先行R0正式保留とv2完了へ訂正。過去の日付付き記録・Phase 1〜3/Scenario Cは保全。
3. 初回collectはcontext.mdに最終採用run IDがないため同期ゲートで停止した。最終IDを現在地へ補足してから再実行しPASS。ゲート緩和、元run修正、手動セル採用はしていない。
4. jdrt.htmlの旧indexアンカー3件を現存IDへ修正。担当6ファイルのローカル参照/fragment欠落0、HTML3件の閉じタグ/未閉鎖/重複ID不整合0、古い進捗残存0。git diff --check PASS（既存の改行警告のみ）。
5. 現状把握・入口・比較HTMLを127.0.0.1の一時サーバーで実画面確認。Chrome既定幅1280pxで本文の横溢れなし、比較表はスクロール領域、主差グラフ表示、入口の「中核比較」から比較ページへの遷移、関連console error/warnなし。別画面幅は未検証。
6. 最初のin-appタブ作成はtimeout、一時サーバー終了後のChromeは接続拒否となった。127.0.0.1サーバーを非表示で再起動して復旧し、確認成功。研究出力への影響なし。確認後は作成タブ/サーバーを終了する。
7. 公開済みCloudflare URLは読取HTTP200で14/20表示を確認。今回はローカル版を更新した。公開版への再配信は未実施として別タスクに記録する。

### 次の1件

現実条件版REAL-P1の不足根拠と対象時点を埋め、REAL-P2に渡す判断入力を確定する。3条件の共通人物・交通手段対応、利用率/予約/fleet/乗降/施設/背景/道路観測を固定する前に新系列を開始しない。PAP変更・新値採用はユーザー判断と事前登録を要する。実行が必要になった時だけスキル1セル運用・15分監視を設定し、詳細経過を残す。今回runなしのため新監視は作成しない。


最終統合確認（2026-10-15T18:08:15+09:00）：対象11文書/HTMLのローカル参照114件・HTML IDを機械照合し欠落/重複0、PASS。証跡は`06_研究結果/jdrt/データ取得監査/統合検証_20261015.json`（対象ファイルSHA付き）。最後の分析readbackも298出典/10出力SHA・20人物CSVの主差/P95でPASS、スキルstatusは20記録済み・RUNNING/未記録0、git diff --check PASS。一時Chromeタブを閉じ、検証専用127.0.0.1:8766サーバーを終了した。公開版の再配信は未実施。次の1件と残判断は完了後詳細タスクに記録済み。

## 2026-10-15 再開後：現実条件版の根拠・具体設計

対象はユーザー選択の「現在の運用＋2015年型洪水」。続いてA（仮定設計と不足資料収集の並行）を選択した。原本照合3分野、人物/観測仕様、PAP判断入力、具体仮定案を作成。既存時間軸の圧縮を確認し、モデルの6時間/900秒を現実6時間/15分の効果として扱わない。具体値と時計の採否を確認中。

担当別成果、失敗担当からの回収、REAL-P1-B/T/S/O、P2-D/F、I1/I2/T1の依存・受入状態は[JDRT-v2_完了後方針・タスク](JDRT-v2_完了後方針・タスク.md)§7を正本とする。原本35SHA・9施設の2経路照合・人物差再計算PASS、保全対象18ファイル不変、現在文書12件98参照の欠落/重複0、既存20セルの主比較readback一致。詳細な経過・失敗/修正は経過報告の同日再開節へ記録した。新PAP未固定、旧入力/実行器/run変更なし、新run/監視なし、Drive書込なし、先行R0正式保留を維持する。


再開作業の最終検査：context追加2行の末尾空白を修正後、git diff --checkは終了0（既存LF/CRLF警告のみ）。新規監査節のローカルリンクも有効、保全18ファイル不変、文書検証の最終SHAを更新済み。SUMO/Python実行プロセスなし。具体仮定案・圧縮時計の採否質問は回答待ちで、数値を正式登録せず引継ぐ。

## 2026-10-15 実時間洪水入力の再構築先行をユーザー確定

圧縮第一案は不採用、実時間入力の再構築を先行する。H0判断記録/H1原本時刻・来歴監査は完了。H2の2015再現時系列水深格子は未取得。GSI原本ZIP一致、8時点/121線形状、公式BP030生応答52時点を保存・独立照合したが、数値水深/初期状態/道路対応が不足し入力採用可否false。元18依存不変、新run/監視/外部送信/Drive書込なし。

正本：[実時間洪水入力_再構築方針・取得監査](../../02_情報調査/氾濫・浸水/jdrt_realtime_20261015/実時間洪水入力_再構築方針・取得監査.md)。依存/担当/受入は同書H0〜H5と[完了後タスク](JDRT-v2_完了後方針・タスク.md)§8。次は原本数値格子の取得と提供条件の確認。詳細操作・取得失敗・修正・検査範囲は経過報告の同日実時間再構築節へ記録した。


## 実時間B（2026-10-16採用）

実時間Bをユーザー採用し、新PAP/Registry・入力・実行/観測・スキル対応を作成。入力15検査/3条件smoke/8テストPASS。[B開始準備/進行監査](JDRT-実時間B_開始準備監査.md)へ詳細タスクを登録。新15セルは1セルずつ開始し、15分監視、validate→6ファイルrecord→statusで進行。先行REAL-R0は別履歴を維持。


### 実時間B・本実験開始と監視（2026-10-16T07:13:07.119200+09:00）

実時間B R0 seed23423、run `rtb_core_r0_seed23423_20261016T071205` を2026-10-16 07:12:05 JST開始。15分監視 `jdrt-b-15` ACTIVE。開始後のcheckはstatus=RUNNING、PID alive=True、sim=2280.0/21600秒。終了後validate→6ファイルrecord→status、未記録のまま後続を開始しない。

初回の監視作成APIは宛先指定不足で作成されず、destination=threadを明示した再呼出で作成成功（ID=jdrt-b-15）。旧jdrt-v2監視はPAUSEDを維持。開始前リンク確認50件エラー0、git diff --checkはエラーなし（既存LF/CRLF警告のみ）。既存dirtyは復元せず、旧依存18SHA不変を確認。外部送信・Drive編集・公開更新なし。


### R0正式採用・R1開始（2026-10-16T07:32:45.490934+09:00）

実時間B 1/15セル正式採用。R0 seed23423（rtb_core_r0_seed23423_20261016T072257）は独立検証PASS・6ファイル同期・台帳1件を確認。現在R1 seed23423 `rtb_core_r1_seed23423_20261016T073200`（07:32:00 JST開始）、status=RUNNING、PID alive=True。15分監視jdrt-b-15 ACTIVE。次はこのR1のcheck→validate→record→status。

R0検証は19,197,258道路行、13,665閉鎖、267,996遷移、43,200step、人物11,965。Error/衝突/teleport/必須観測欠損/閉鎖進入/曖昧遷移0。Type4施設受入0/544、退出188は別アウトカムとして単一セルの事実記録に留める。Warning2件（うち歩行位置補正1件）は除外せず保全・適用限界に記録。初回INVALID runとsmokeを正式結果へ混ぜない。R1稼働中のscripts/入力編集禁止、全5seed前の方向解釈なし。


### R1正式採用・R2開始（2026-10-16T07:51:26.321971+09:00）

実時間B 2/15セル正式採用。R1 seed23423（rtb_core_r1_seed23423_20261016T073200）は独立検証PASS・6ファイル同期・台帳一意を確認。現在R2 seed23423 `rtb_core_r2_seed23423_20261016T075040`（07:50:40 JST開始）、status=RUNNING、PID alive=True。15分監視jdrt-b-15 ACTIVE。次はこのR2のcheck→validate→record→status。

R1一次再計算：人物11965、Type4施設受入1/544、Type4退出137（別アウトカム）。道路19197258行、候補315210行、遷移260942行、閉鎖進入0・曖昧遷移0。全検査PASS、終了後両ログError/Warning0。単一セルの事実のみ記録し、全5seed前の方式間方向解釈なし。R2開始後のcheckは下記JSONLへ保存。scripts/入力/PAP/Registry変更・外部送信・Drive編集なし。


### R2復旧ゲート完了・新ID再開（2026-10-16T08:14:53.635731+09:00）

実時間B 2/15採用。R2初回の過去route履歴権限エラーを技術修正し、12テスト・実SUMO再現・現行R0/R1/R2 smoke独立PASS、preflight READYを確認。R2 seed23423を08:14:00 JSTに新ID `rtb_core_r2_seed23423_20261016T081400`で再開、status=RUNNING、PID alive=True。新実行器jdrt_realtime_b_routehistoryfix.py、旧採用実装を保持。入力/PAP/Registry不変、15分監視jdrt-b-15 ACTIVE。次はこのR2のcheck→validate→6ファイルrecord→status。

現行smoke IDはR0=rtb_smoke_r0_seed23423_20261016T081033、R1=rtb_smoke_r1_seed23423_20261016T081132、R2=rtb_smoke_r2_seed23423_20261016T081236。すべてError/衝突/teleport/観測欠損/閉鎖進入/曖昧遷移0、実走行と施設受入あり。新実行器変更は残経路ID適用・現在edge前提・駐車解除順のみ（最終差分をexecutor_revision_final.diffへ保存）。定義・スコア・Gate・目的地・車両数・seedは変更しない。失敗runとtoy/smokeを研究台帳に混ぜない。旧18依存と採用済み2run参照実装SHA不変を確認。全5seed前に方向解釈しない。外部送信/Drive編集なし。


### seed23423全3採用・seed42 R0開始（2026-10-16T08:23:15.589372+09:00）

実時間B 3/15セル正式採用。seed23423のR0/R1/R2は全て独立検証PASS・6ファイル同期済み。現在R0 seed42 `rtb_core_r0_seed42_20261016T082231`（08:22:31 JST開始）、status=RUNNING、PID alive=True。15分監視jdrt-b-15 ACTIVE。次はこのR0のcheck→validate→6ファイルrecord→status。全5seed前の方式間方向解釈なし。

R2の人物11965、Type4受入1/544、Type4退出96は別アウトカム。道路19197258行、候補616569行、遷移255186行、閉鎖進入0・曖昧遷移0、全検査PASS。警告1件「Vehicle b_drt_0 aborts stop」はsim4200の現在閉鎖による明示的actor除去と一致し、warning_audit.jsonへ保全。乗客のstranded_drtも分母に保持。検証PASSのみスキルrecord、run IDの6ファイル存在と台帳1件を別途確認。初回R2失敗とsmoke/toyは研究結果へ不採用。scripts/入力/PAP/Registry変更・外部送信・Drive編集なし。


### 徒歩閉鎖処理の復旧ゲート・seed42 R0再開（2026-10-16T08:41:28.074141+09:00）

実時間B 3/15採用。seed42初回R0は徒歩閉鎖進入3件でINVALID保全。交差点内部保留の継続確認を修正した新実行器で15テスト・現行3条件smoke独立PASS、preflight READY後、同じR0 seed42を08:40:30 JSTに新ID `rtb_core_r0_seed42_20261016T084030`で再開。status=RUNNING、PID alive=True。次はこのrunの終了→validate→6ファイルrecord→status。入力/PAP/Registry/ゲート不変、旧採用実装保持、15分監視jdrt-b-15 ACTIVE。

現行smokeはR0=rtb_smoke_r0_seed23423_20261016T083636、R1=rtb_smoke_r1_seed23423_20261016T083749、R2=rtb_smoke_r2_seed23423_20261016T083914。全検査PASS。単体15件、3条件smoke、入力PASSの各SHAをpreflightで確認。今回の不合格runは正式台帳へ記録せず、出力を修正/再利用しない。新実行器はjdrt_realtime_b_pedclosurefix.py。閉鎖進入3件を再現する本実験条件そのものを新IDで再実行し、0になることと全ゲートを終了後に検証する。現時点では再実行の採用を先取りしない。全5seed前の方向解釈なし、比較前の実装版影響監査タスクも維持。外部送信・Drive編集なし。


### seed42 R0正式記録・seed42 R1開始（2026-10-16T11:40:34.136878+09:00）

実時間B 4/15セル正式採用。修正後R0 seed42 `rtb_core_r0_seed42_20261016T084030`は独立検証PASS・6ファイル同期・台帳1件を確認。R1 seed42 `rtb_core_r1_seed42_20261016T113921`を11:39:21 JSTに開始、status=RUNNING、PID alive=True。次は本runのcheck→終了後validate→6ファイルrecord→status。入力/PAP/Registry・検証条件不変、旧実装/失敗run保全。15分監視jdrt-b-15 ACTIVE。08:41–11:34の監視実行記録の空白は詳細監査に明記し、実施済みとは扱わない。全5seed前の方向解釈なし、全15セル比較前の実装版影響監査を維持。

R0 seed42は人物11965、Type4受入0/544、Type4退出188を別計上。道路観測19197258行・遷移268933行、閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損/Error0。旧進入該当人物のrerouteと交差点での進入前除去をpedestrian_regression_audit.jsonへ保全。SUMO警告6件（歩行stage位置補正3、急減速2、急停止1）はwarning_audit.jsonと原ログへ保持し、物理位置の再現上の制約を残す。スキルrecordが一次成果物から再検証したPASSのみ正式採用。run IDの6ファイル存在とJSONL1件を独立確認後だけ次を開始。scripts/入力/PAP/Registry変更・外部送信・Drive編集なし。


### seed42 R1正式記録・seed42 R2開始（2026-10-16T11:52:58.683963+09:00）

実時間B 5/15セル正式採用。R1 seed42 `rtb_core_r1_seed42_20261016T113921`は独立検証PASS・6ファイル同期・台帳1件を確認。R2 seed42 `rtb_core_r2_seed42_20261016T115201`を11:52:01 JSTに開始、status=RUNNING、PID alive=True。次は本runのcheck→終了後validate→6ファイルrecord→status。入力/PAP/Registry・検証条件不変、旧実装/失敗run保全。15分監視jdrt-b-15 ACTIVEを保存設定でも確認。過去08:41–11:34の監視実行記録の空白は監査に保持。全5seed前の方向解釈なし、全15セル比較前の実装版影響監査を維持。

R1 seed42は11965人全員の終端会計PASS。Type4受入1/544、Type4退出149は別アウトカム。道路観測19197258行、候補判定114780行、遷移264140行を独立再計算し全ゲートPASS。閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損/Error0。歩行stage位置補正の警告2件は原ログとdriver_logs/rtb_core_r1_seed42_20261016T113921.warning_audit.jsonへ保持し、物理位置の再現上の制約を残す。recordで一次成果物再検証→6ファイルへrun ID存在→台帳1件→statusの次セルR2 seed42確認後だけ新IDを開始。稼働中scripts/入力の編集、外部送信、Drive編集なし。


### seed42 R2正式記録・seed1 R0開始（2026-10-16T12:08:24.042671+09:00）

実時間B 6/15セル正式採用。seed23423/42のR0/R1/R2が独立PASS・正式記録済み。直前R2 seed42 `rtb_core_r2_seed42_20261016T115201`の6ファイル同期・台帳1件を確認後、R0 seed1 `rtb_core_r0_seed1_20261016T120726`を12:07:26 JSTに開始。status=RUNNING、PID alive=True。次は本runのcheck→終了後validate→6ファイルrecord→status。入力/PAP/Registry・検証条件不変、旧実装/失敗run保全。15分監視jdrt-b-15 ACTIVE。過去08:41–11:34の監視実行記録の空白は監査に保持。全5seed前の方向解釈なし、全15セル比較前の実装版影響監査を維持。

R2 seed42は11965人全員の終端会計PASS。Type4受入1/544、Type4退出101を別計上。道路観測19197258行、候補判定634626行、遷移256353行を一次成果物から再計算し全ゲートPASS。閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損/Error0。警告5件（歩行stage位置補正2、DRT停車中断1、急減速1、急停止1）を原ログとdriver_logs/rtb_core_r2_seed42_20261016T115201.warning_audit.jsonへ保持。停車中断はsim4200のb_drt_3のinitial_or_current_closed除去と一致し、stranded_drt人物も分母/終端に保持。警告を抑制せず物理位置再現の限界として残す。スキルrecordによる再検証PASS、6ファイルのrun ID存在・台帳一意・次セル順序を別途確認した後だけ開始。主run稼働中のscripts/入力編集、研究条件変更、外部送信、Drive編集なし。


### seed1 R0正式記録・seed1 R1開始（2026-10-16T12:22:31.101362+09:00）

実時間B 7/15セル正式採用。seed23423/42の全3条件とseed1 R0が独立PASS・正式記録済み。直前R0 seed1 `rtb_core_r0_seed1_20261016T120726`の6ファイル同期・台帳1件を確認後、R1 seed1 `rtb_core_r1_seed1_20261016T122135`を12:21:35 JSTに開始。status=RUNNING、PID alive=True。次は本runのcheck→終了後validate→6ファイルrecord→status。入力/PAP/Registry・検証条件不変、旧実装/失敗run保全。15分監視jdrt-b-15 ACTIVE。過去08:41–11:34の監視実行記録の空白は監査に保持。全5seed前の方向解釈なし、全15セル比較前の実装版影響監査を維持。

R0 seed1は11965人全員の終端会計PASS。Type4受入0/544、Type4退出188を別計上。道路観測19197258行、候補0行、遷移268261行を一次成果物から再計算し全ゲートPASS。閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損/Error0、SUMO警告0。空の原警告ログのSHAと監査をdriver_logs/rtb_core_r0_seed1_20261016T120726.warning_audit.jsonへ保存。スキルrecordで再検証PASS後に6ファイルのrun ID存在、台帳1件、statusの次セルR1 seed1を確認してから新IDで開始。主run稼働中のscripts/入力編集、研究条件変更、外部送信、Drive編集なし。


### seed1 R1正式記録・seed1 R2開始（2026-10-16T12:37:21.206840+09:00）

実時間B 8/15セル正式採用。seed23423/42の全3条件とseed1 R0/R1が独立PASS・正式記録済み。直前R1 seed1 `rtb_core_r1_seed1_20261016T122135`の6ファイル同期・台帳1件を確認後、R2 seed1 `rtb_core_r2_seed1_20261016T123627`を12:36:27 JSTに開始。status=RUNNING、PID alive=True。次は本runのcheck→終了後validate→6ファイルrecord→status。入力/PAP/Registry・検証条件不変、旧実装/失敗run保全。15分監視jdrt-b-15 ACTIVE。過去08:41–11:34の監視実行記録の空白は監査に保持。全5seed前の方向解釈なし、全15セル比較前の実装版影響監査を維持。

R1 seed1は11965人全員の終端会計PASS。Type4受入0/544、Type4退出131を別計上。道路観測19197258行、候補判定293919行、遷移259003行を一次成果物から再計算し全ゲートPASS。閉鎖後進入/曖昧遷移/衝突/teleport/観測欠損/Error0。急減速警告1件（sim2902、scen_c_origin_0089_0080）は原ログとdriver_logs/rtb_core_r1_seed1_20261016T122135.warning_audit.jsonへ保持。DRT b_drt_1はsim2400のroute_cutで除去され、stranded_drt人物も分母/終端に保持。スキルrecordによる再検証PASS後、6ファイルのrun ID存在・台帳1件・次セル順序を独立確認して新IDを開始。主run稼働中scripts/入力の編集、研究条件変更、外部送信、Drive編集なし。


### 車両交差点閉鎖の失敗保全・別版修正（2026-10-16T12:53:10.218838+09:00）

実時間B 8/15採用。R2 seed1 rtb_core_r2_seed1_20261016T123627は自家用車の閉鎖進入1件で独立FAIL、INVALID保全し後続停止。車両の交差点内保留後の再確認漏れを別実行器jdrt_realtime_b_junctionfix.pyで修正。18テスト・実SUMO交差点再現PASS、現行3条件smoke再検証中。PASSとpreflight READY後のみ同じR2 seed1を別IDで再開。入力/PAP/Registry/閉鎖進入0ゲート不変。旧8採用実装SHA一致、比較前の実装版影響監査を維持。

該当actor scen_c_origin_0228_0004は146#11→146#12をlower5999.5/upper6000.5、closure6000で進入。閉鎖時のinternal通過を時系列と実SUMO小型試験で再現。旧処理は閉鎖イベント時にだけ確認してinternalをskipし、既に進入決定した車両はlane permission変更だけでは停止しなかった。新処理は全stepで実route indexを用いて残経路だけ確認。次external閉鎖なら進入前にroute_cut除去し乗員を終端保持、次が開いて将来経路が閉鎖なら安全なexternalまで保留してreroute、走行済み閉鎖だけならclear。参照不一致を例外にし、路線再開/検査無効化/閾値緩和をしない。実SUMOではlegacyが21.0にinternal・21.5に閉鎖bへ進入、fixedは21.0に除去し進入0・両case Error0。試験初回のルートパス誤指定によるimport失敗はattempt00として保全。18テストの初回PASS後、ゲートに必要な実出力ログを保存するため再実行しPASS・SHA結合。新実行器/CLI/テスト差分・旧ソース/旧unit gate・8採用実装SHA照合はrecovery_vehicleclosure_20261016へ保存。既採用結果の版差の影響範囲を比較前に監査する。

新実行器SHA256：`f8215cee83cb6690a38bc59f62f412463e45add624b8b88aba67940982f3bcfe`。外部送信・Drive編集なし。


### 車両閉鎖修正ゲート・R2 seed1新ID再開（2026-10-16T12:57:18.639426+09:00）

実時間B 8/15採用。R2 seed1初回rtb_core_r2_seed1_20261016T123627は車両閉鎖進入1件で独立FAIL・INVALID保全。全stepで車両残経路を確認する別実行器jdrt_realtime_b_junctionfix.pyを作成し、18テスト・実SUMO交差点再現・現行3条件smoke独立PASS、preflight READYを確認。同じR2 seed1を12:56:11 JSTに新ID `rtb_core_r2_seed1_20261016T125611`で再開。status=RUNNING、PID alive=True。次はこのrunの終了→validate→6ファイルrecord→status。入力/PAP/Registry/閉鎖進入0ゲート不変、旧8採用実装SHA一致、失敗run不採用保全。15分監視jdrt-b-15 ACTIVE、全5seed前の方向解釈なし、比較前の実装版影響監査を維持。

新smokeはR0=rtb_smoke_r0_seed23423_20261016T125214、R1=rtb_smoke_r1_seed23423_20261016T125339、R2=rtb_smoke_r2_seed23423_20261016T125453。全検査PASS、Error/閉鎖進入/曖昧遷移/衝突/teleport/観測欠損0、実徒歩/DRT受入も確認。入力PASS・実装SHA・18単体テストSHAと3smokeをpreflightで結合。修正内容はvehicle_closure_actionによる実route indexの残経路確認と車両確認の全step化だけ。閉鎖次externalへ向かうinternal車両はroute_cut除去して人物保持、次が開いて将来閉鎖なら安全なexternalまで保留しreroute、過去だけの閉鎖は無視。実SUMOで旧版の閉鎖直後進入と修正後の進入前除去を再現・検証。再実行は本実験の同一条件そのものを新IDで行い、閉鎖進入0と全会計/観測/候補/SHAを終了後に独立検証する。現在runの採用を先取りしない。旧実装の8採用runとの版差影響は比較前に監査し、除外規則や追加runを無断変更しない。原失敗run/旧コード/テスト/ゲート/差分/試験初回import失敗を保全。外部送信・Drive編集なし、主run稼働中scripts/入力変更なし。


### 時刻境界の再FAIL保全・判断案・起動HOLD（2026-10-16T13:11:28.291613+09:00）

実時間Bは8/15セル記録済み、研究run0・未記録0。修正後R2 seed1 rtb_core_r2_seed1_20261016T125611も閉鎖時刻ちょうどの進入1件で独立FAIL・INVALID保全。前回交差点の障害は防止できたが、別車両の5399.5→5400.0/閉鎖5400の境界が残った。境界fixtureで現時刻適用は等号進入、移動前制御は進入0だが実呼出しが0.5秒先行することを確認。時刻境界・再開判断案_v1を保存し、共通15セル再実行か実時刻維持の調査継続かをユーザーへ明示質問中。preflightはHOLDで遮断確認。判断まで解除/再起動しない。既記録8セルの記録/PASS/SHAを保持し、新しい時刻定義での主比較採用を先取りしない。15分監視jdrt-b-15 ACTIVE、判断待ち・変化なしは静かに記録する。

記録8runの正の閉鎖イベントは各7493件ともevent時刻−予定時刻=0。旧検証PASS・進入0・参照実装SHA一致を一次ログから再確認したが、0.5秒先行へ変えた共通実装と同じ条件だったとは主張しない。提案1は予定時刻・実呼出し・観測時刻を分離登録し、別workspace/実行契約/PAP追補の下で同じ5seed×3条件を共通実装・新IDで15セルそろえ直し、旧8セルを新主比較に混ぜない案。未承認・未開始。提案2は実時刻の適用を保持し、step内時刻/境界区間の観測可能性を追加調査し本実験保留。いずれも今回FAILを手作業でPASSへ変えない。unit18/3条件smokeのPASS実績を退避し、フル条件FAILを受けた運用ゲートだけHOLDにした（テストFAILではない）。preflightの実ブロック・status・境界試験・旧8監査・根拠URLをrecovery_boundary_20261016へ記録。AGENTS §7/モデル運用基準§0の研究方法判断要件により、実効時計/比較からの分離/追加15runの採用はユーザーの明示判断待ち。外部送信・Drive編集なし。

判断案：`03_研究設計文書/jdrt/常総市JDRT_実時間B_時刻境界・再開判断案_v1.md`。


### 境界整合系列：開始前READY・検証詳細（2026-10-16T18:21:32.459239+09:00）

提案1採用の新境界整合系列realtime_b_boundary_v2、0/15正式記録・実行中0。入力17検査/23テスト/実SUMO9ケース/現行3条件smokeすべてPASS、preflight READY。予定T・呼出しmax(0,T−0.5)・観測上限Tを分離する新PAP/Registry/独立図解を作成済み。次は新CLIでR0 seed23423を1セル開始し15分監視→独立validate→6ファイルrecord。旧B8記録/全失敗/旧HOLDを保全し新主比較へ混ぜず、全15セルを同じ4実装SHAでそろえる。既存監視jdrt-b-15は新系列へ更新済み。外部送信・Drive編集なし。

物理入力11artifactのSHA一致、原本から35,366道路/手段行を再計算して17検査PASS。unit23件PASS（追加テストの仮ディレクトリmock漏れ1試行を保全後修正）、実SUMO9ケースPASS。新R0/R1/R2 smoke IDは{'R0': 'rtbb2_smoke_r0_seed23423_20261016T181244', 'R1': 'rtbb2_smoke_r1_seed23423_20261016T181432', 'R2': 'rtbb2_smoke_r2_seed23423_20261016T181624'}、全clock/会計/観測/遷移/Error等PASS。preview.state.jsonが専用CLIのrun-state globへ衝突したstatus失敗はoperationsに記録し、表示確認用metadataをpreview_server.jsonへ名前分離して解消、研究コード/入力変更なし。新図解を狭い表示幅で実見し、小さかった時計SVGを縦カードへ切り替えて可読性確認。新CLI/4実装SHA・単体ソースSHA・timing証拠SHAをpreflightで確認。監視jdrt-b-15を新系列のCLI/準備監査へ更新し、ACTIVE/15分・同じchatで重複作成なし。


### 新境界整合R0 seed23423開始（2026-10-16T18:23:44.103453+09:00）

新境界整合B realtime_b_boundary_v2：0/15正式記録。R0 seed23423 `rtbb2_core_r0_seed23423_20261016T182150`を18:21:50 JSTに開始、status=RUNNING・PID alive=True。入力17検査/23テスト/実SUMO9ケース/現行3条件smoke PASS、preflight READY後の新規開始。閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限Tを分離し、共通4実装SHAで新15セルをそろえる。旧B8記録/全失敗/旧HOLDは保全して新主比較へ混ぜない。次はこのrunのcheck→終了後validate→新6ファイルrecord・台帳一意確認→status。監視jdrt-b-15は新系列で15分ACTIVE、全5seed前に方向解釈しない。主run稼働中はscripts/入力を編集しない。外部送信・Drive編集なし。

実manifest PID=10428、4実装SHAは全てunit/timing/3smokeと一致。開始操作・実コマンド・時刻はoperations.jsonl/stateへ自動記録。今回のスコープのFact-Forcing Gateは新CLI/新runの1セル開始、固定入力を読み別IDへ3時計と全観測を保存、ユーザーの採用回答を根拠として実施。正式記録数0で本runの採用を先取りしない。新台帳に旧8/失敗/fixtureは混在なし。ローカルリンク77件検証・表示確認、metadata再結合済み。


### 境界整合R0正式記録・R1開始（2026-10-16T18:32:43.346279+09:00）

新境界整合B realtime_b_boundary_v2：1/15正式記録。R0 seed23423 `rtbb2_core_r0_seed23423_20261016T182150`は独立検証PASS・6ファイル同期・新台帳一意確認済み。R1 seed23423 `rtbb2_core_r1_seed23423_20261016T183134`を18:31:34 JSTに開始し、RUNNING・PID生存を確認。共通4実装SHA・入力17検査/23テスト/実SUMO9ケース/3smokeは維持。次はR1のcheck→終了後validate→record・6ファイル同期確認→status。旧8は分離保全、最大0.5秒先行を明示し、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0は2026-10-16T18:27:59.812533+09:00にsim21600.0秒・43200step・361snapshot。全人物終端11965人、Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行、遷移268049、候補0、閉鎖後進入/曖昧遷移/Error/teleport/衝突/観測欠損0。閉鎖13665件（初期6172・0.5秒先行7493・末尾73）の3時計/phase一致。急減速警告2件は原ログ保全。警告をErrorと混同せず、方式効果の解釈はしない。record内の再検証もPASS、新6ファイルの実run IDと台帳1件を確認後、statusの次セルR1・preflight READY・共通SHAを確認して1セルだけ開始。新R1 manifest PID=7700、今回check sim=2160.0秒、counts={"steps": 4320, "controller_ticks": 2161, "snapshots": 37, "teleports": 0, "collisions": 0, "transition_rows": 70595, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 4993, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T18:47:34.638258+09:00）

新境界整合B realtime_b_boundary_v2：2/15正式記録。R1 seed23423 `rtbb2_core_r1_seed23423_20261016T183134`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed23423 `rtbb2_core_r2_seed23423_20261016T184653`を2026-10-16T18:46:55.399168+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed23423：2026-10-16T18:37:30.852313+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出110は別計上。道路観測19197258行・遷移256318・候補722086。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 256318, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 722086, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=24184、check={"run_id": "rtbb2_core_r2_seed23423_20261016T184653", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T18:47:37.369008+09:00", "run_id": "rtbb2_core_r2_seed23423_20261016T184653", "time_sec": 960.0, "end_sec": 21600, "wall_sec": 25.79474189999746, "people_states": {"not_ready": 10398, "admitted": 241, "travelling": 246, "waiting": 109, "onboard": 3, "no_route": 67, "boundary_exit": 754, "assigned": 1, "walk_limit": 19, "no_origin_connection": 87, "initial_or_current_closed": 40}, "active_vehicles": 96, "counts": {"steps": 1920, "controller_ticks": 961, "snapshots": 17, "teleports": 0, "collisions": 0, "transition_rows": 29562, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 239, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:03:54.030563+09:00）

新境界整合B realtime_b_boundary_v2：3/15正式記録。R2 seed23423 `rtbb2_core_r2_seed23423_20261016T184653`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed42 `rtbb2_core_r0_seed42_20261016T190325`を2026-10-16T19:03:27.779577+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed23423：2026-10-16T18:52:43.597441+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出96は別計上。道路観測19197258行・遷移255175・候補617262。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255175, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 617262, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告1件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=27312、check={"run_id": "rtbb2_core_r0_seed42_20261016T190325", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:03:57.442381+09:00", "run_id": "rtbb2_core_r0_seed42_20261016T190325", "time_sec": 660.0, "end_sec": 21600, "wall_sec": 18.78571140000713, "people_states": {"not_ready": 10933, "no_origin_connection": 49, "admitted": 110, "travelling": 247, "no_route": 85, "boundary_exit": 480, "walk_limit": 41, "initial_or_current_closed": 20}, "active_vehicles": 83, "counts": {"steps": 1320, "controller_ticks": 661, "snapshots": 12, "teleports": 0, "collisions": 0, "transition_rows": 17765, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:16:13.176667+09:00）

新境界整合B realtime_b_boundary_v2：4/15正式記録。R0 seed42 `rtbb2_core_r0_seed42_20261016T190325`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed42 `rtbb2_core_r1_seed42_20261016T191543`を2026-10-16T19:15:46.646693+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed42：2026-10-16T19:09:24.244912+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移269019・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 269019, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告5件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23052、check={"run_id": "rtbb2_core_r1_seed42_20261016T191543", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:16:16.817988+09:00", "run_id": "rtbb2_core_r1_seed42_20261016T191543", "time_sec": 420.0, "end_sec": 21600, "wall_sec": 14.899428600008832, "people_states": {"not_ready": 11299, "admitted": 60, "travelling": 180, "waiting": 45, "no_route": 46, "assigned": 4, "boundary_exit": 285, "walk_limit": 9, "no_origin_connection": 28, "initial_or_current_closed": 9}, "active_vehicles": 76, "counts": {"steps": 840, "controller_ticks": 421, "snapshots": 8, "teleports": 0, "collisions": 0, "transition_rows": 10665, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 43, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:31:02.369206+09:00）

新境界整合B realtime_b_boundary_v2：5/15正式記録。R1 seed42 `rtbb2_core_r1_seed42_20261016T191543`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed42 `rtbb2_core_r2_seed42_20261016T193033`を2026-10-16T19:30:35.177397+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed42：2026-10-16T19:21:42.441230+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出137は別計上。道路観測19197258行・遷移261853・候補303860。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 261853, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 303860, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=24808、check={"run_id": "rtbb2_core_r2_seed42_20261016T193033", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:31:05.381143+09:00", "run_id": "rtbb2_core_r2_seed42_20261016T193033", "time_sec": 300.0, "end_sec": 21600, "wall_sec": 14.903746399999363, "people_states": {"not_ready": 11488, "admitted": 28, "travelling": 194, "waiting": 31, "no_route": 37, "assigned": 4, "boundary_exit": 158, "walk_limit": 6, "no_origin_connection": 16, "initial_or_current_closed": 3}, "active_vehicles": 85, "counts": {"steps": 600, "controller_ticks": 301, "snapshots": 6, "teleports": 0, "collisions": 0, "transition_rows": 7245, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 43, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T19:46:32.904715+09:00）

新境界整合B realtime_b_boundary_v2：6/15正式記録。R2 seed42 `rtbb2_core_r2_seed42_20261016T193033`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed1 `rtbb2_core_r0_seed1_20261016T194541`を2026-10-16T19:45:43.695126+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed42：2026-10-16T19:36:45.706704+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入1/544、Type4退出101は別計上。道路観測19197258行・遷移256052・候補637681。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 256052, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 637681, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告3件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=15632、check={"run_id": "rtbb2_core_r0_seed1_20261016T194541", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T19:46:35.602416+09:00", "run_id": "rtbb2_core_r0_seed1_20261016T194541", "time_sec": 960.0, "end_sec": 21600, "wall_sec": 32.39618250000058, "people_states": {"not_ready": 10319, "admitted": 263, "no_origin_connection": 78, "travelling": 335, "no_route": 81, "boundary_exit": 793, "walk_limit": 63, "initial_or_current_closed": 33}, "active_vehicles": 101, "counts": {"steps": 1920, "controller_ticks": 961, "snapshots": 17, "teleports": 0, "collisions": 0, "transition_rows": 30492, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:01:09.321578+09:00）

新境界整合B realtime_b_boundary_v2：7/15正式記録。R0 seed1 `rtbb2_core_r0_seed1_20261016T194541`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed1 `rtbb2_core_r1_seed1_20261016T200038`を2026-10-16T20:00:41.182660+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed1：2026-10-16T19:51:53.720398+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268419・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268419, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23688、check={"run_id": "rtbb2_core_r1_seed1_20261016T200038", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:01:16.814214+09:00", "run_id": "rtbb2_core_r1_seed1_20261016T200038", "time_sec": 480.0, "end_sec": 21600, "wall_sec": 21.82809749999433, "people_states": {"not_ready": 11168, "travelling": 242, "no_origin_connection": 39, "admitted": 123, "assigned": 4, "no_route": 38, "waiting": 48, "boundary_exit": 269, "walk_limit": 14, "initial_or_current_closed": 20}, "active_vehicles": 103, "counts": {"steps": 960, "controller_ticks": 481, "snapshots": 9, "teleports": 0, "collisions": 0, "transition_rows": 13036, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 163, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:16:12.692985+09:00）

新境界整合B realtime_b_boundary_v2：8/15正式記録。R1 seed1 `rtbb2_core_r1_seed1_20261016T200038`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed1 `rtbb2_core_r2_seed1_20261016T201545`を2026-10-16T20:15:48.184318+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed1：2026-10-16T20:06:30.644742+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出131は別計上。道路観測19197258行・遷移259227・候補293919。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 259227, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 293919, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=12704、check={"run_id": "rtbb2_core_r2_seed1_20261016T201545", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:16:15.605715+09:00", "run_id": "rtbb2_core_r2_seed1_20261016T201545", "time_sec": 240.0, "end_sec": 21600, "wall_sec": 11.385691999996197, "people_states": {"not_ready": 11590, "no_origin_connection": 19, "admitted": 34, "assigned": 4, "travelling": 184, "no_route": 23, "boundary_exit": 75, "waiting": 17, "walk_limit": 6, "initial_or_current_closed": 13}, "active_vehicles": 81, "counts": {"steps": 480, "controller_ticks": 241, "snapshots": 5, "teleports": 0, "collisions": 0, "transition_rows": 4253, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 163, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:31:22.012428+09:00）

新境界整合B realtime_b_boundary_v2：9/15正式記録。R2 seed1 `rtbb2_core_r2_seed1_20261016T201545`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed7 `rtbb2_core_r0_seed7_20261016T203031`を2026-10-16T20:30:33.429765+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed1：2026-10-16T20:21:51.034447+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出102は別計上。道路観測19197258行・遷移255415・候補450390。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255415, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 450390, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=7988、check={"run_id": "rtbb2_core_r0_seed7_20261016T203031", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:31:23.993266+09:00", "run_id": "rtbb2_core_r0_seed7_20261016T203031", "time_sec": 900.0, "end_sec": 21600, "wall_sec": 34.814884100007475, "people_states": {"not_ready": 10559, "no_route": 79, "no_origin_connection": 48, "travelling": 293, "admitted": 183, "boundary_exit": 724, "walk_limit": 46, "initial_or_current_closed": 33}, "active_vehicles": 94, "counts": {"steps": 1800, "controller_ticks": 901, "snapshots": 16, "teleports": 0, "collisions": 0, "transition_rows": 26996, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T20:46:05.952610+09:00）

新境界整合B realtime_b_boundary_v2：10/15正式記録。R0 seed7 `rtbb2_core_r0_seed7_20261016T203031`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed7 `rtbb2_core_r1_seed7_20261016T204541`を2026-10-16T20:45:43.693994+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed7：2026-10-16T20:37:11.685513+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268506・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268506, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=19504、check={"run_id": "rtbb2_core_r1_seed7_20261016T204541", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T20:46:09.902841+09:00", "run_id": "rtbb2_core_r1_seed7_20261016T204541", "time_sec": 480.0, "end_sec": 21600, "wall_sec": 14.737934500008123, "people_states": {"not_ready": 11193, "no_route": 22, "no_origin_connection": 35, "travelling": 231, "admitted": 94, "waiting": 49, "boundary_exit": 313, "onboard": 2, "walk_limit": 13, "assigned": 2, "initial_or_current_closed": 11}, "active_vehicles": 93, "counts": {"steps": 960, "controller_ticks": 481, "snapshots": 9, "teleports": 0, "collisions": 0, "transition_rows": 13639, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 50, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T21:01:30.618515+09:00）

新境界整合B realtime_b_boundary_v2：11/15正式記録。R1 seed7 `rtbb2_core_r1_seed7_20261016T204541`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed7 `rtbb2_core_r2_seed7_20261016T210045`を2026-10-16T21:00:48.558798+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed7：2026-10-16T20:51:30.985740+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出135は別計上。道路観測19197258行・遷移262110・候補305015。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 262110, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 305015, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=17144、check={"run_id": "rtbb2_core_r2_seed7_20261016T210045", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T21:01:33.205953+09:00", "run_id": "rtbb2_core_r2_seed7_20261016T210045", "time_sec": 840.0, "end_sec": 21600, "wall_sec": 29.70029059999797, "people_states": {"not_ready": 10653, "no_route": 53, "no_origin_connection": 48, "travelling": 240, "admitted": 168, "waiting": 78, "boundary_exit": 669, "walk_limit": 25, "assigned": 2, "onboard": 2, "initial_or_current_closed": 27}, "active_vehicles": 93, "counts": {"steps": 1680, "controller_ticks": 841, "snapshots": 15, "teleports": 0, "collisions": 0, "transition_rows": 24985, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 283, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T21:16:11.026302+09:00）

新境界整合B realtime_b_boundary_v2：12/15正式記録。R2 seed7 `rtbb2_core_r2_seed7_20261016T210045`は独立PASS・6ファイル同期・台帳一意確認済み。R0 seed101 `rtbb2_core_r0_seed101_20261016T211544`を2026-10-16T21:15:47.193948+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R2 seed7：2026-10-16T21:07:01.897357+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出99は別計上。道路観測19197258行・遷移255986・候補828313。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 255986, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 828313, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=23544、check={"run_id": "rtbb2_core_r0_seed101_20261016T211544", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T21:16:14.915336+09:00", "run_id": "rtbb2_core_r0_seed101_20261016T211544", "time_sec": 420.0, "end_sec": 21600, "wall_sec": 14.582149900001241, "people_states": {"not_ready": 11235, "travelling": 261, "no_origin_connection": 32, "admitted": 88, "no_route": 48, "boundary_exit": 264, "walk_limit": 24, "initial_or_current_closed": 13}, "active_vehicles": 94, "counts": {"steps": 840, "controller_ticks": 421, "snapshots": 8, "teleports": 0, "collisions": 0, "transition_rows": 11414, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T23:16:22.383356+09:00）

新境界整合B realtime_b_boundary_v2：13/15正式記録。R0 seed101 `rtbb2_core_r0_seed101_20261016T211544`は独立PASS・6ファイル同期・台帳一意確認済み。R1 seed101 `rtbb2_core_r1_seed101_20261016T231553`を2026-10-16T23:15:55.867923+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R0 seed101：2026-10-16T21:21:52.313481+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出188は別計上。道路観測19197258行・遷移268186・候補0。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 268186, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 0, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告2件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=27156、check={"run_id": "rtbb2_core_r1_seed101_20261016T231553", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T23:16:23.720175+09:00", "run_id": "rtbb2_core_r1_seed101_20261016T231553", "time_sec": 600.0, "end_sec": 21600, "wall_sec": 14.825555500006885, "people_states": {"not_ready": 10946, "admitted": 140, "no_origin_connection": 42, "travelling": 231, "waiting": 57, "no_route": 50, "boundary_exit": 452, "onboard": 3, "walk_limit": 19, "initial_or_current_closed": 24, "assigned": 1}, "active_vehicles": 91, "counts": {"steps": 1200, "controller_ticks": 601, "snapshots": 11, "teleports": 0, "collisions": 0, "transition_rows": 17691, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 80, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合監視・正式記録と次セル開始（2026-10-16T23:31:07.386664+09:00）

新境界整合B realtime_b_boundary_v2：14/15正式記録。R1 seed101 `rtbb2_core_r1_seed101_20261016T231553`は独立PASS・6ファイル同期・台帳一意確認済み。R2 seed101 `rtbb2_core_r2_seed101_20261016T233034`を2026-10-16T23:30:36.636762+09:00に開始、RUNNING・PID生存を確認。入力/unit/実SUMO timing/3smoke・共通4実装SHAのpreflight READY後に1セルだけ開始。次は現runのcheck→終了後validate→record・6ファイル実在と台帳一意確認→status。旧8は分離保全、最大0.5秒先行を明示、全5seed前の方向解釈は行わない。15分監視jdrt-b-15 ACTIVE。主run中はscripts/入力を編集しない。外部送信・Drive編集なし。

終了R1 seed101：2026-10-16T23:21:32.197044+09:00、sim21600.0秒、全人物終端11965人。Type4施設受入0/544、Type4退出139は別計上。道路観測19197258行・遷移260095・候補325962。閉鎖後進入0・曖昧遷移0。終了counts={"steps": 43200, "controller_ticks": 21601, "snapshots": 361, "teleports": 0, "collisions": 0, "transition_rows": 260095, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 325962, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}。閉鎖3時計/phaseを全件照合：{"closures": 13665, "initial": 6172, "positive": 7493, "last_window": 73, "lead_counts": {"0": 6172, "0.5": 7493}, "phase_counts": {"initial_before_observation": 6172, "before_step_ending_at_closure": 7493}}。SUMO警告0件は原ログとmonitoringへ保持（警告0は採用ゲートではない）。現run manifest PID=10384、check={"run_id": "rtbb2_core_r2_seed101_20261016T233034", "status": "RUNNING", "pid_alive": true, "progress": {"at_jst": "2026-10-16T23:31:08.908772+09:00", "run_id": "rtbb2_core_r2_seed101_20261016T233034", "time_sec": 900.0, "end_sec": 21600, "wall_sec": 20.706949500003248, "people_states": {"not_ready": 10451, "admitted": 229, "no_origin_connection": 71, "waiting": 91, "travelling": 219, "no_route": 86, "assigned": 3, "boundary_exit": 748, "walk_limit": 34, "initial_or_current_closed": 32, "onboard": 1}, "active_vehicles": 83, "counts": {"steps": 1800, "controller_ticks": 901, "snapshots": 16, "teleports": 0, "collisions": 0, "transition_rows": 27184, "closed_entry_rows": 0, "ambiguous_transitions": 0, "candidate_rows": 331, "missing_vehicle_subscriptions": 0, "missing_person_subscriptions": 0}}, "error": null}。


### 境界整合全15セル完了・次の方針（2026-10-16T23:51:46.375409+09:00）

新境界整合B realtime_b_boundary_v2：15/15正式記録完了。実行中0・未記録0・次セルなし。全15セル独立PASS・6ファイル実在・新台帳一意・共通4実装SHAを確認。一次人物CSVから独立一覧/seed内主指標記述表を生成、全成果物SHAを再照合。旧B8/失敗/fixtureは分離保全。閉鎖予定T・実呼出しmax(0,T−0.5)・観測上限Tの区別と最大0.5秒先行は維持。次は完了後分析タスクBA-02の副指標集計→時間/候補/道路監査→資料取得監査。追加run/方法変更は行わない。監視PAUSED（停止確認済み）。外部送信・Drive編集なし。

独立一覧：`06_研究結果/jdrt/realtime_b_boundary_v2/全セル結果一覧.html`。一次人物CSVから主指標/終了会計、車両CSVとtripinfoから距離を再計数し、正式validation/台帳と一致。全出力SHA再照合、根拠249ファイル。全道路CSVの全行検証を一覧生成時に再反復したとは記載しない。主指標のseed内記述比較までで、副指標/取得監査の完了を先取りしない。次の方針とBA-01〜06の担当役割・入力・成果物・依存/完了条件は`05_タスク管理/jdrt/JDRT-実時間B境界整合_完了後分析タスク.md`。追加runせず既登録集計と不足資料棚卸しを進める。

最終R2 seed101は23:36:24頃に終了、閉鎖後進入/曖昧遷移/Error/衝突/teleport/観測欠損0。Type3人物の開始位置補正警告1件を原ログ/monitoringへ保持。time_limit765は未受入/未退出のまま分母保持。全15件で共通実装と退出別計上を維持。一覧生成初回は空欄車両距離の数値変換で出力前に停止し、旧試行ソースを保全。空欄はtripinfo欠落かつ観測距離0を照合し、修正後は一次CSV/tripinfo/validationの全15距離一致。21:29頃〜23:13等の監視ログ空白とcontext同期補修も消さず監査へ残した。


### 2026-10-17T00:25:44.596567+09:00 境界整合B 完了後監査・次段方針

新境界整合Bは15/15正式記録済み。BA-02〜06の副指標・時間・候補・道路・取得監査と方針整理を完了。道路287,958,870行・候補5,270,448行を全読取し、全人物会計・時刻・選択候補/配車event・3時計・遷移を照合。Type4の固定終点・施設空き・拠点接続を診断。次はNP-02/03の災害時供給/需要・路面高/施設条件の不足資料整理。追加run・方法変更は未採用、監視PAUSED。Driveは5文書読取のみ、外部送信なし。

Type4施設受入の対応seed人数差：{"R1−R0": [1, 1, 0, 0, 0], "R2−R1": [0, 0, 0, 0, 0]}。退出・時間切れ・配車結果を別表示し、一般的有効性/無効性へ一般化しない。待ち/所要は観測件数と未完了状態を併記。初期拠点診断は登録入力の技術診断。単純な増車/再割当やGate変更を採用せず、供給/需要・路面高/施設条件の根拠整理を優先する。

新成果物：`06_研究結果/jdrt/realtime_b_boundary_v2/postanalysis_20261017/`。道路全キー一意、0台速度空欄、人物/施設/event会計、選択候補と配車集合、3時計・遷移を独立照合。初回分類名の誤指定と非有限値の扱いで後処理が2回停止、ログと当時コード/途中出力を保全して修正。研究run失敗ではない。Drive2フォルダ5本文を読取、市通常運行案内をHTTP200再取得。災害時実測不足は未解消。外部送信/Drive編集/新runなし。詳細コマンド・時刻・チェックポイントはoperations.jsonl、コードとSHAは生成根拠。


### 2026-10-17T08:34:38.515000+09:00 最終goal：G1取得・G2数理診断と次の設計

最終goal ACTIVE。ユーザー判断軸「より現実的なシミュレーション・数式による考察」に基づき自律継続中。G2数理構造診断完了：固定終点のType4受入上限112/544、固定割当下の総受入上限488/1007、4台・乗降各300秒の輸送上限144/900、仕事量比6.25を一次成果物から算出。G1は公開根拠・施設50候補・水害対応12候補の位置/容量を整理し継続中。代表点の水理域内は旧4施設と同じ。次はG3の予約意思/受付/配車受理/未配車代替と需要/供給の具体設計・別系列事前登録。旧15セル・凍結系列は保全、現在新runなし、旧監視PAUSED、Drive読取のみ、外部送信なし。

判断根拠はユーザーの最新委任、数理診断JSON/生成根拠、公式資料の取得監査。公開協定の対象時点不整合、橋梁PDFのCMap/OCR/フォント警告、キー/トークンの除去、GSI提供画面の同意未実施、施設代表点/入口の精度差も記録。G1の取得成功を実運用値の取得成功と混同しない。G2の上限と実現値を区別。改善順序は独立設計判断記録v1へ保存し、新PAPはまだ未作成。詳細取得/SHA/作業は `06_研究結果/jdrt/goal_20261017/operations.jsonl`。

## 受付・代替行動系列の登録とpolicy検証（2026-10-17T08:49:53.004249+09:00）

最終goal ACTIVE。G2数理診断とG1公開根拠/施設候補の照合を受け、受付・代替行動の別系列 realtime_choice_v1 を新PAP/Registry/状態仕様へ事前登録。D0旧終点/D1初期施設優先、需要5%/50%、R0/R1/R2P900/R2P0、同D/seedのR0共用で全70セルを固定。未乗車期限900秒は実測でない新仮定。G4の純粋policy関数13テストPASS、技術未READY・新core 0。次は排他的な新入力コピー、初期終点/共通実現表の独立検証、実SUMOの迎車取消/徒歩代替。旧15セル・凍結系列は保全、旧監視PAUSED。Drive読取のみ、外部送信なし。

新PAP/Registry/状態仕様/全70セルCSV/独立HTML・SVG・md図/詳細タスクを作成。新policyは意思マスク、初期施設優先、期限、候補判定、要求状態を実装。13反例テストPASS。最初の12件PASSの後、同距離経路で二進丸めがID順位を壊さないようDecimalによる初期距離/tieを明記。追加テストの初回は0.30と0.3の文字列表現差で1件FAILだったため、数値同値の検証へ訂正し全13件PASS。避難人数の期待値をテストへ固定していない。

checkpointは旧249/診断84参照SHA不変、全15runの6ファイル同期、154リンク、候補50/12行、公開地図キーの残存なし、scoped git diff --check PASS。初回checkpointはencoding別名utf8-sigで失敗し、utf-8-sigへ修正して再実施。旧CLI statusは15/15、実行中/未記録0。旧run最大保存量を70倍した参考値は約6.5GB、現在空き約265GB。新観測量増加を考慮し開始前にも再確認する。

コマンド：project venv python -X utf8 -m pytest tests/test_jdrt_choice_policy.py -q（04_プログラムで実行）。詳細時刻/ハッシュはgoal_20261017/operations.jsonl。旧入力/実装/runの変更なし。新coreなし。次はCH-P1/P2と実SUMO取消の技術確認。

## 新入力の排他作成と独立再計算（2026-10-17T08:57:25.796093+09:00）

registered01へ旧物理artifactをコピーし、D0/D1の終点表、5seedの準備時刻/意思5%・50%の共通実現表、70セル表を作成。生成と別のforward Fraction距離でD1を照合し、全167originの終点/経路・需要マスク/セル一意がPASS。原HDF/地形から35,366edge/modeの水深・初期/最大水深・閾値・閉鎖上下区間を再計算し不一致0。人口/Type/域内外、構造物除外、施設容量/モデル上乾燥接続/退出分離を再照合。統合input_validationの23検査PASS、technical_ready=false。準備manifestは不変の生成来歴として保持し、検証結果は別reportへ保存。

最初の原本再計算は容量CSVのBOM付き先頭列をutf-8で読んだためKeyErrorで終了。元CSVは変更せず、検証器の読込をutf-8-sigへ修正した。原本再計算再実施PASS、さらに現行検証器で派生表/原本の統合検証をPASS。旧原本/旧run変更なし。新core/実SUMO試験はまだ開始していない。

入力準備コマンド：04_プログラムでproject venv python -X utf8 -m scripts.jdrt_realtime_choice_inputs。検証：同 -m scripts.jdrt_realtime_choice_validate --all。準備は再実行時に同ディレクトリを拒否し、上書きしない。技術修正で入力依存SHAが変われば新入力版を作成して来歴を残す。

次は新実行器とrun検証器、実SUMOの期限/取消/internal/元位置の徒歩切替、全14設定smoke、専用CLIとスキル。現在のSUMO公式Change Vehicle StateをFirecrawl検索/本文で取得した。replaceStop等の仕様を参考候補として保存し、実機で確認するまでは実装可能と断定しない。検索初回不発を不存在とせず再検索した。外部評価送信なし。

## G4実装・実SUMOと開始前位置監査（2026-10-17T09:24:55.207879+09:00）

最終goal ACTIVE。受付・代替行動系列70セルは事前登録済み・研究core 0。新実行器の主要処理を実装し18unit PASS、現行実SUMO4case PASS、D0/u05/R1/seed23423の1800秒smoke完走・一次会計17検査PASS（全道路1,648,518行等）。技術未READY。徒歩出発pos0とDRT迎車の道路末端が不一致で、接続道路長15.25〜489.77mを確認。次はCH-POSの座標/共有起点位置を検証して実行前の規則・別入力版を確定し、正式run検証器・反例/14設定smoke・record/preflightへ進む。旧15セル・凍結系列は保全。旧監視PAUSED、Drive読取のみ、外部送信なし。

詳細：[実SUMO・位置整合監査](../../05_タスク管理/jdrt/JDRT-受付代替行動_実SUMO・位置整合監査.md)。probe01/02とsmoke01/02の失敗を保全。SUMO停止解除直後の無効座標、過去経路prefix保持、getEdges既定internal包含を実測/実APIで確認し、検証を緩めず制御/監査を修正した。current probe05は全4case PASS、smoke04は1800秒完走・一次会計17項目PASS、現行実装SHA一致。コード原本の保存も追加した。

一次監査では23人・6要求の全状態、道路1,648,518行、閉鎖6,783件、遷移1,025行、3時計、期限/乗降・容量/SHAを照合。core効果の方向は解釈しない。候補score/経路/現在速度、毎step二重移動、VKT、全core共通性、故意改変、閉鎖/失敗/満員/窓末反例、全14設定、正式recordとpreflightは未完。

コード点検で共通originの物理位置がmode間で一致しないことを確認。入力の接続道路長15.25〜489.77m、位置欄なし、歩行pos0/DRTの車道末端stop/私有車既定位置。原座標の投影と車道/歩道・車体制約を調べ、規則・影響・代替案を実行前登録して別入力版へ進める。現在の位置規則を新たに採用したわけではない。最終goalはACTIVE、次はCH-POS。全試験は15分未満で同じ実行handleを完了まで確認し、古い監視の再開や重複automationはなし。Drive編集・外部送信なし。


### 2026-10-18 — 徒歩fixture診断・G6準備検証（定型共有記録）

最新HOLD（2026-10-18、徒歩診断・G6準備確認後）： goal ACTIVE。realtime_choice_v1正式記録0/70、研究core 0。旧67 unit PASSは履歴であり現行READYの根拠ではない。cf26101804/cs261018dはcase25 evaluator failureでFAILED（case1–24 PASS）。case25 native runはCOMPLETED・2/2 admitted・teleport/collision 0だが、Type3/Type4のd0同時在辺フレームは0。初回reroute直後のType4 next-step前進条件もfalse。初期位置重複による干渉は有力仮説だが因果未実証。診断完了、人工位置案を試験中・成功未証明。失敗原本は保全し、別担当のwalk_short人工位置のみ修正と新診断pairを待つ。case26・現行全26suite/反例監査/14 smoke/preflight未完、技術READY=false、core開始禁止。研究入力/PAP/受入条件不変。G6は副指標7・主6・人工70統合5の契約試験PASS、登録source SHA 29/29一致、人工準備のみ。実core集計なし、実70性能・全限界・最終報告未完。方式方向の解釈なし。理論値詳細は一次報告 [G6準備検証](06_研究結果/jdrt/goal_20261017/G6_副指標上限_統合準備検証_20261018.md) と [登録入力確認JSON](06_研究結果/jdrt/goal_20261017/G6_登録入力_理論値確認_20261018T204212013676.json) を参照。要求記録gpt-6-luna/low、分析要求gpt-6.1-sol/high、実backend未確認。

診断一次記録：[CH002徒歩校正診断](../../06_研究結果/jdrt/goal_20261017/CH002_徒歩校正診断_20261018.md)。G6一次記録：[副指標上限統合準備検証](../../06_研究結果/jdrt/goal_20261017/G6_副指標上限_統合準備検証_20261018.md)、[source SHA監査](../../06_研究結果/jdrt/goal_20261017/G6_登録入力sourceSHA監査_20261018.json)、[登録入力理論値確認](../../06_研究結果/jdrt/goal_20261017/G6_登録入力_理論値確認_20261018T204212013676.json)。


## 2026-10-20 — 独立監視の導入

ユーザーの明示依頼により、定型の15分AI確認をイベント時だけの診断へ置き換える独立監視を導入した。[導入タスク](独立監視システム_導入タスク.md)を実装・検証記録の正本とする。19試験、人工通知/診断、監視自身の異常終了からの自動復帰を確認。旧監視は既にPAUSEDで、重複起動しない。監視の正常表示・完了イベントを研究validate PASS/採用と読み替えず、READY・1セル実行・独立検証・正式記録ゲートを維持する。研究実行器/入力・PAPの変更、研究run開始は本作業では行っていない。


## 2026-10-22 — 現状把握資料の文章・記録ルールと表示の改訂

- 完了：非専門者向けに目的・現在地・調べ方・課題・経過を整理。文章と記録の正本は[文章・記録ルール](../../00_全体整理/現状把握_文章・記録ルール.md)。以前の技術記録は同じ全体整理フォルダに保全。
- 自動表示：状況同期の補助処理に平易な説明と技術詳細の分離を追加。固定された正式record処理には触れず、定型の照合行だけを表示同期時に整形。研究実装5件と設定1件は開始時SHAと一致。
- 検証：新規6試験と既存正式記録26試験PASS、状況同期13/14 PASS。残る1件は変更前でも再現する補助checkpointの再更新で、今回未修正。MD/HTML経過一致、正式marker2件、ローカルリンク10件を確認。PC1440×1000/スマートフォン390×844で開閉・キーボード・横はみ出しなし・コンソールエラーなし。
- 詳細：[変更前・検証・レビュー](../../.agents/skills/joso-jdrt-runner/references/history/20261022_readability/README.md)。人による理解度評価と公開版の更新は未実施。研究のstart/validate/record・条件変更なし。


### 2026-10-22 — 別チャットでのデザイン維持（完了）

ユーザー「別チャットであっても、現在のデザインを維持したまま今後の更新ができればよい」により、[更新ガイド](../../00_全体整理/現状把握_デザイン維持・更新ガイド.md)を作成。HTML/CSSを実装の正本とし、通常は内容だけを更新する。AGENTS・文章ルール・索引から参照を追加。今回の画面のCSSと操作用JavaScriptは変更しない。引継ぎ確認時に前回のcontext追記が説明文中のmarkerへ入っているミスを検出し、単独行markerの直前へ移した。正式record markerは保持。


## 2026-10-23 — 現状把握HTMLの公開更新（完了）

ユーザー「クラウドフレアにデプロイして」により、research-status-publisherで既存joso-research-statusへHTML1件を公開。旧配信・旧staged/module/configは[配信履歴](../../00_全体整理/公開用_cloudflare/deployment_history/20261023T172045508346/)へ保全。CLI認証期限切れのため接続済みAPIを利用し、Wrangler 4.152.0 dry-run PASS後に配信。公開成功の経過記録も反映するため、同じ依頼内で最終版を再配信した。最終deployment 73306013f5654c559312a7149c7b5dd1、HTTP200・原本/staged/remote SHA一致。PC1440×1000/スマートフォン390×844、開閉とキーボード、ローカルリンク10件無効、横はみ出し/console errorなしを確認。研究実装・入力・採用条件・公開先は変更なし。
