# context.md — 現在地

> **性格：** 変更頻度が高い「今どこにいるか」を先頭へ置く。恒久ルールは`AGENTS.md`・`CLAUDE.md`、過去の経緯は`00_全体整理/決定ログ.md`。
> **更新のしかた：** 状態が変わったらこのファイルを上書きする。経緯は消さず `00_全体整理/決定ログ.md` へ追記する。
> **エージェント読込範囲：** 通常は`<!-- AGENT_CURRENT_END -->`までで十分。以降は過去結果を確認するときだけ読む。

**最終更新：** 2026-10-28（短道路・到着観測の技術訂正、新登録v3の全実SUMO再検証）

---

**経過報告の運用変更（2026-10-20）：** 経過報告は`00_全体整理/現状把握_静的・動的シミュレーション整理.md`へ更新日ごとに短く先に記録してから、日付別に開閉できるHTMLへ反映し、詳細はGitHubへプッシュする際のコミットメッセージ本文へ残す。`01_経過報告/`はPPTX形式の発表資料を作成するときだけ使用し、既存Markdownは履歴として保存する。

**後続実験の方針（2026-10-24）：** ユーザー指定により、現小型車系列の全登録セルの検証・正式記録・分析と結果整理の後、大型バスが一定区画を巡回して集団輸送する別系列を検証する。[後続実験計画](05_タスク管理/jdrt/大型バス巡回輸送_後続実験計画.md)へ作業順・設計事項・開始条件を登録。台数・定員・停留所・経路・比較条件等は未確定、本実験未開始。現系列・凍結系列の条件変更なし。

## 一行で言うと

**現状把握・GitHub入口の整理（2026-10-28）：** 現状把握MD/HTMLへ各実験の固定条件・変更条件・進行度・結果と、現行v3の正式9回の個別人数表を追加。READMEに確認先を集約。10:43 JST観測の本実験稼働0・正式9/70・技術停止を区別し、人物CSVの分母・受入・退出と台帳/SHAを照合。[更新検証](00_全体整理/現状把握_更新検証_20261028.md)参照。開始・採用条件は変更していない。

**モデル運用更新（2026-10-21）：** ユーザー承認済みの作業別分担・切替基準・短い引継ぎ・検証証跡再利用条件を[運用正本§0](05_タスク管理/スキル・エージェント運用.md)へ反映し、通常開発用role定義を追加。研究の次の1件・開始/採用ゲートは維持。初回の明示委任による起動確認と代表課題での節約効果比較は未実施。

<!-- CHOICE_CURRENT_CONTEXT_BEGIN -->
最新HOLD（表示根拠 2026-10-28T10:43:01.498851+09:00）：正式記録9/70。技術READY=false。旧READY/技術PASSはSTALE/historical。後続開始禁止。元summaryと旧証拠はcheckpoint履歴に保全。
<!-- CHOICE_CURRENT_CONTEXT_END -->

**受付・代替行動の次の1件：** 採用数・実行中run・登録上の次セルは上の現行表示と専用CLI status/check、新系列台帳を正本とする。元session/実PID/作成時刻・次の具体操作はG4実装・実SUMO_継続チェックポイント.jsonとoperations.jsonlを参照する。未記録run・未完操作がある間は次セルを開始しない。

> 履歴：**受付・代替行動の次の1件（2026-10-27T11:12:19.817853+09:00）：** 新v3正式1/70。低需要R1 nv26102702は11:10:58に21600秒COMPLETED、元wait83231 exit0・実4748不在・親check異常なしを確認。まだ採用せず、独立validate/専用record7と元終端7ファイル読戻し後だけ次へ。次のfinishを1担当で開始し、進行中は別validate/record/表示writerを作らない。全70/分析・後続大型バス・最終報告は未完。

> **受付・代替行動の次の1件（2026-10-27T10:13:29.678939+09:00）：** nv26102701（新登録v3、fixed_reference_r0_seed23423）を開始済み。実PID13636/作成10:08:46.0913759、launcher23204、元start99879 exit0。親check正常。07のCIM照会失敗を保全し監視だけ26988へ再起動、同じ本run13636の作成時刻/コマンド/進捗と監視の鮮度を確認済み。本runは再起動しない。完了後に専用validate/record7/readback/statusを終えるまで次セル禁止。全70/分析・報告は未完。

> **受付・代替行動の次の1件（2026-10-24T23:39:54.926219+09:00）：** 全14と同一commonsourceの読戻し済み。表示同期の後に専用preflight --suite-id nt261024d --counterexamples 06_研究結果/jdrt/goal_20261017/正式検証器_表会計候補_20261024T231243.jsonを1回だけ起動。同じhandle/PID/attemptの入力・unit・43独立再検証・容量・新READYを追跡し、タイムアウトで再実行しない。preflight生存中は表示writerを保留。新READY全binding/status/容量/G6/監視の最終確認前にcore禁止。

> 履歴：**受付・代替行動の次の1件（2026-10-24T18:03:44.851009+09:00）：** 技術HOLD・正式8/70保全。nc26102402は専用validate元session13369/実PID19672がexit1/INVALIDで終端、recordなし。専用rejectでINVALID_PRESERVEDとし、元COMPLETED manifestをSHA付き保存。元計算終了17:40:16.885273と管理reject時刻を区別する。主因は短道路を3299.0までに通過済みなのに次external3300.5を上限に付ける生成/検証の共有時刻誤り。native_logs側はmovement全体INVALIDにより歩行Warning照合辞書を空にする二次判定で、6warningと3組のnative stage receiptは一致し、version supportも確認。分類器の条件は緩めない。候補はgoal/transition_time_candidate_20261024へ隔離し、元凍結RED・13人工契約・1個体の読取replay PASS、未組込/非採用。次は観測のみのproducerと独立validator修正、初期/到着/再経路/short/internalの実SUMO反例と全技術再検証、全70共通版の別技術登録/新workspace/READY。旧8採用/旧9原本を新比較へ混ぜず、gate迂回/旧run修正・再利用なし。原検証担当は不在を確認、現common5/config/入力はまだ不変。

**独立監視導入（2026-10-20）：** ユーザー依頼の別goalとして`07_監視システム/`を導入。Windowsタスク`JDRT-SimulationWatch`でチャット外に常駐し、PID終了1秒・状態/ログ10秒・時刻停滞10分でイベント検出、イベント時だけ読取専用Codex短報とWindows通知。履歴349件を基準登録、研究core稼働0・READY=falseは専用statusで観測。人工通知/診断・19試験・監視異常終了からの別PID自動復帰を確認。runtimeはOneDrive外の`~/.jdrt-monitor/10afa40fb646/`、受信箱は同所`status.html`。このchatへの自動投稿・研究の自動start/recordは行わず、既存研究ゲートを維持。経過報告は現状把握Markdown先行→HTML反映。[導入タスク](05_タスク管理/jdrt/独立監視システム_導入タスク.md)。監視生存の最新状態は専用`watch.py status`を確認する。


<!-- choice_record:ch261021_001 -->
### ch261021_001（2026-10-21T16:24:23.209096+09:00正式記録）

protocol=realtime_choice_v1、cell=fixed_reference_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=0/544、退出182は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_v1/validation_reports/validate_ch261021_001_20261021T162423107374.json`。次の1件は専用CLI statusを参照。



**判断学習の統一運用（2026-10-22）：** 入口は[運用正本§0.4](05_タスク管理/スキル・エージェント運用.md)のみ。「ACEで基準確認→台帳へ判断/結果記録→本chatが教訓を整理してACE更新」の一つの流れに統合。各実行chatは重要判断前のACE参照と台帳記録、本chatは判断基準の更新を担当。ユーザー指示で実行中chatへ参照手順を送信し、受領応答とace.ps1 showを含むコマンド完了を確認。適用理由/結果の記録は今後確認する。過去の手作業まとめは履歴であり並行更新しない。API自動LLM未接続・改善効果未測定。導入/監査/技術制約は[技術説明](.agents/tools/ace/README.md)参照。


<!-- choice_record:nc26102201 -->
### nc26102201（2026-10-22T21:34:37.888584+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=0/544、退出182は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102201_20261022T213437797252.json`。次の1件は専用CLI statusを参照。

**現状把握資料の改訂（2026-10-22）：** 非専門者向けの文章・記録ルールを制定し、現状把握MD/HTMLと表示用補助へ反映。研究実装・入力・採用条件は維持。改訂前の技術記録は別ファイルで保全。PC/スマートフォン表示、開閉・キーボード、経過同期・リンク・marker・固定SHAを確認。状況同期の既存試験1件は変更前にも失敗する問題として履歴に記録。公開更新なし。[文章・記録ルール](00_全体整理/現状把握_文章・記録ルール.md)。

**デザイン維持の引継ぎ（2026-10-22）：** 別チャットでも現在のHTMLを使って内容を更新する。[更新ガイド](00_全体整理/現状把握_デザイン維持・更新ガイド.md)に、配色・文字組・余白・開閉と更新箇所を整理。通常の内容更新ではCSS・操作用JavaScript・節の識別名を維持する。文章ルールとAGENTSから参照できる。


<!-- choice_record:nc26102202 -->
### nc26102202（2026-10-22T22:43:22.004413+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u05_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102202_20261022T224321901062.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nc26102203 -->
### nc26102203（2026-10-23T09:46:46.812523+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u05_r2p900_seed23423、R2P900、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102203_20261023T094646729135.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nc26102301 -->
### nc26102301（2026-10-23T10:45:59.599303+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u05_r2p0_seed23423、R2P0、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102301_20261023T104559490974.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nc26102302 -->
### nc26102302（2026-10-23T11:42:07.707939+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u50_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102302_20261023T114207604398.json`。次の1件は専用CLI statusを参照。

**現状把握の公開更新（2026-10-23）：** ユーザーの明示依頼で改訂HTML1件を既存Cloudflareへ配信。原本/staged/配信SHA一致、HTTP200、PC・スマートフォン表示と開閉を確認。最終配信ID73306013f5654c559312a7149c7b5dd1。[公開先](https://joso-research-status.30k-012rei.workers.dev/)、[配信証跡](00_全体整理/公開用_cloudflare/deployment_history/20261023T172045508346/verification.final.json)。研究実装・入力・採用条件不変。


<!-- choice_record:nc26102303 -->
### nc26102303（2026-10-23T17:58:09.033066+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u50_r2p900_seed23423、R2P900、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102303_20261023T175808936607.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nc26102304 -->
### nc26102304（2026-10-23T18:54:04.292700+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=fixed_reference_u50_r2p0_seed23423、R2P0、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102304_20261023T185404222375.json`。次の1件は専用CLI statusを参照。

**監視の所要時間記録（2026-10-24）：** 新規イベントと監視stateへmanifestの開始・終了・実所要秒数/出典を追加し、受信箱へJSTで表示。34試験PASS、新実監視16536/現source一致・旧167イベント不変を確認。旧イベントは書換えず時刻不明。研究の次セル/正式記録には作用しない。[反映証跡](07_監視システム/verification/execution_timing_20261024/deployment.json)。


<!-- choice_record:nc26102401 -->
### nc26102401（2026-10-24T17:21:48.069182+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v2_20261021、cell=facility_first_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=1/544、退出12は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2/validation_reports/validate_nc26102401_20261024T172147959246.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102701 -->
### nv26102701（2026-10-27T10:54:15.691248+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=0/544、退出182は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102701_20261027T105415588821.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102702 -->
### nv26102702（2026-10-27T11:42:36.677532+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u05_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102702_20261027T114236594092.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102703 -->
### nv26102703（2026-10-27T19:17:08.842651+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u05_r2p900_seed23423、R2P900、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102703_20261027T191708762630.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102704 -->
### nv26102704（2026-10-27T23:16:03.906995+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u05_r2p0_seed23423、R2P0、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102704_20261027T231603812315.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102705 -->
### nv26102705（2026-10-28T00:05:09.957506+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u50_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102705_20261028T000509870415.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102806 -->
### nv26102806（2026-10-28T01:00:29.242226+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u50_r2p900_seed23423、R2P900、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102806_20261028T010029136672.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102807 -->
### nv26102807（2026-10-28T01:48:13.117875+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=fixed_reference_u50_r2p0_seed23423、R2P0、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102807_20261028T014813025726.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102808 -->
### nv26102808（2026-10-28T02:31:22.117948+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=facility_first_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=1/544、退出12は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102808_20261028T023122042209.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:nv26102809 -->
### nv26102809（2026-10-28T08:29:47.360404+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_native_observation_v3_20261024、cell=facility_first_u05_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=1/544、退出12は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3/validation_reports/validate_nv26102809_20261028T082947279559.json`。次の1件は専用CLI statusを参照。

<!-- AGENT_CURRENT_END -->

---

## 参考・履歴（通常のセッション開始時は読まない）

### タスク状態（Phase 3 実装・評価）

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
| 2026-10-09 | JDRT v2 JDRT-B3 seed101 `core_v2_b3_seed101_20260912_skill01`完了。COMPLETED/valid、人物47避難＋3,208立ち往生＝3,255、request16完了＋1,424立ち往生＝1,440、Type4 42・Type3 5、DRT 129.757827km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,547行/SHA全PASS。中核17/20、次はB2 seed101 |
| 2026-09-12 | JDRT v2 JDRT-P2-L15 seed7 `core_v2_p2_l15_seed7_20260912_skill01`完了。COMPLETED/valid、人物16避難＋3,239立ち往生＝3,255、request8完了＋1,432立ち往生＝1,440、Type4 11・Type3 5、DRT 71.612915km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,498行/SHA全PASS。中核16/20、次はB3 seed101 |
| 2026-09-12 | JDRT v2 JDRT-P1 seed7 `core_v2_p1_seed7_20260912_skill01`完了。COMPLETED/valid、人物9避難＋3,246立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、Type4 5・Type3 4、DRT 53.226622km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,485行/SHA全PASS。中核15/20、次はP2-L15 seed7 |
| 2026-09-11 | OpenAI公式AGENTS.md仕様に基づき、`AGENTS.md`を現行ルールへ短縮し、`context.md`に通常読了境界を追加。`CLAUDE.md`、モデル運用基準、INDEX、フォルダ別ガイドを常総市JDRT v2と`joso-jdrt-runner`へ同期。runは開始せず14/20・次P1 seed7を維持 |
| 2026-09-11 | 常総市JDRT v2の1セル実行・独立検証・記録を`.agents/skills/joso-jdrt-runner/`へスキル化。完了セルを検出し、検証PASS後だけ実験記録・タスク管理・本ファイル・決定ログ・経過報告・JSONL台帳を同期する。Python構文、スキル構造、B2 seed7のvalidate、record冪等性を確認。新規runは開始せず、14/20・次はP1 seed7のまま |
| 2026-09-11 | JDRT v2 JDRT-B2 seed7 `core_v2_b2_seed7_20260908_codex01`完了。COMPLETED/valid、人物26避難＋3,229立ち往生＝3,255、request9完了＋1,431立ち往生＝1,440、Type4 11・Type3 15、DRT 36.908887km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,509行/SHA全PASS。中核14/20、次はP1 seed7 |
| 2026-09-08 | JDRT v2 B3 seed7 `core_v2_b3_seed7_20260908_codex01`完了。COMPLETED/valid、人物52避難＋3,203立ち往生＝3,255、request18完了＋1,422立ち往生＝1,440、Type4 45・Type3 7、DRT 127.955678km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,549行/SHA全PASS。中核13/20、次はB2 seed7 |
| 2026-09-08 | JDRT v2 P2-L15 seed1は`core_v2_p2_l15_seed1_20260908_codex01`を外部中断FAILEDとして保全し、`core_v2_p2_l15_seed1_20260908_codex02`を再実行して完了。COMPLETED/valid、人物8避難＋3,247立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、Type4 4・Type3 4、DRT 56.722154km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,480行/SHA全PASS。seed1の4方式完了・中核12/20、次はB3 seed7 |
| 2026-09-08 | JDRT v2 P1 seed1 `core_v2_p1_seed1_20260908_codex01`完了。COMPLETED/valid、人物9避難＋3,246立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、Type4 4・Type3 5、DRT 48.964886km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,486行/SHA全PASS。中核11/20、次はP2-L15 seed1 |
| 2026-09-08 | JDRT v2 B2 seed1 `core_v2_b2_seed1_20260908_codex01`完了。COMPLETED/valid、人物20避難＋3,235立ち往生＝3,255、request7完了＋1,433立ち往生＝1,440、Type4 8・Type3 12、DRT 34.171033km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,500行/SHA全PASS。中核10/20、次はP1 seed1 |
| 2026-09-07 | JDRT v2 B3 seed1 `core_v2_b3_seed1_20260907_codex01`完了。COMPLETED/valid、人物36避難＋3,219立ち往生＝3,255、request12完了＋1,428立ち往生＝1,440、Type4 33・Type3 3、DRT 106.562820km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,526行/SHA全PASS。中核9/20。途中比較なし、次はB2 seed1 |
| 2026-09-07 | JDRT v2 P2-L15 seed42 `core_v2_p2_l15_seed42_20260907_codex01`完了。COMPLETED/valid、人物8避難＋3,247立ち往生＝3,255、request4完了＋1,436立ち往生＝1,440、Type4 5・Type3 3、DRT 57.150706km、controller21,600・観測43,200、teleport/collision/gridlock teleport/未処理Error全0。Parameter1/1・入力8/8・出力9/9・event1,480行/SHA全PASS。seed42の4方式完了・中核8/20。途中比較なし、次はB3 seed1 |
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
