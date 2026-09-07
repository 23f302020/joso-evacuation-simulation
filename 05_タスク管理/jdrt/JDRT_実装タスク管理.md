# 常総市JDRT 実装タスク管理

> 作成日：2026-08-11  
> 対象：常総市（08211）  
> 実装仕様：`03_研究設計文書/jdrt/常総市JDRT_実装方針.md`  
> 状態：v1は技術停止して保全。常総市限定v2中核7/20、seed 42は3/4完了

## 1. 目的と範囲

既存Phase 1〜3と車＋徒歩Scenario Cを凍結したまま、常総市限定のJDRTを独立実装する。本表は、方針確立、研究判断、基盤実装、SUMO統合、実験、評価を順序付きで管理する。

PAP・Parameter Registry、常総市入力、TraCI統合、smoke、full実験器まで完了した。v1の強Baseline B2はpaired 5seedを完了したが、B3 seed 23423は自家用車の衝突teleport 4件によりPAPゲート不合格となった。v1の採用条件を緩和せず旧runを保全する。ユーザーの新version開始指示を受け、常総市08211だけを対象に、SUMO step length 0.5秒、controller 1秒、各step技術観測、衝突teleport 0を固定したv2 PAP・Parameter Registryを実験前に作成した。v2はB2を含む4方式×5seedを全て再実行し、v1結果を混在させない。v2実行器はParameter SHA分離、0.5秒観測、整数秒controller、衝突件数記録を実装し、unit全171件とpreflightを通過した。最初のB3 seed 23423技術ゲートは合格し、現在はv2中核7/20、seed 42は3/4完了である。

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
| JDRT-WEB3 | HTML第3段階：full実験結果 | ⬜ | JDRT-E2 | `output/jdrt.html` | CSV・manifestから実測値を表示し、値をHTMLへ手入力しない |
| JDRT-WEBQA | HTML構文・リンク・表示検証 | ⚠️ | 各WEB段階 | 検査記録 | B2第1セル反映後、6ページ・ローカルリンク176件欠落0、全178件PASS。BrowserのローカルURL制約により実画面QAは未完 |
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
| JDRT-V2-R | v2中核4方式×5seed | 🔄 7/20 | JDRT-V2-G1 | v2 validated runs、`JDRT-v2_full実験記録.md` | seed23423完了、B3/B2/P1 seed42 PASS。次はP2-L15 seed42 |
| JDRT-E1 | 中核比較・Ablation | ⬜ | JDRT-R2 | 比較CSV・manifest | Type4、全体、stranded、P95、waiting、empty VKTを算出 |
| JDRT-S1 | 段階的Robustness | ⬜ | JDRT-E1 | 感度結果 | 全因子直積を避け、停止規則を満たす |
| JDRT-E2 | 個人・mesh・政策単位分析 | ⬜ | JDRT-E1 | counterfactual・mesh結果 | 誰にどの条件で便益があるか説明可能 |
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
```

テスト不合格の場合は後続へ進まず、原因を当該タスク内で修正する。

## 4. 研究判断が必要な項目

以下は技術実装で決めず、`05_タスク管理/モデル運用基準.md`の「論点整理→Fable 5判断→記録」で確定する。

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
