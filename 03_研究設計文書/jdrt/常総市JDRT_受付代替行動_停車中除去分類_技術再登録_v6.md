# 受付・代替行動：停車中の除去による `aborts stop` の分類 技術再登録v6

状態：**承認済み（ユーザー 2026-11-21「承認する」）・登録済み。技術READY=false。** 本実験開始不可。登録時点：2026-11-21T15:12:52.149286+09:00。config の7項目を書き換え、新しい記録2ファイルを作成した（取引の受領：`06_研究結果/jdrt/goal_20261017/C2_v6_registration_20261121/application01/registration_receipt.json`）。新系列の全開始前検証（入力・READY・U4・監視・1セル目）は未完。
作成：2026-11-21、開発PC、Opus 5.5（実装担当）。手順の正本：`05_タスク管理/jdrt/C2_流し直し手順設計_20261121.md`。判断の記録：台帳 JD-20261121-seq25-*、JD-20261121-c2-*。
登録：registration_id `choice_parked_abort_v6_20261121`、workspace `04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_parkedabort_v6`。

## 1. 根拠

v5（`choice_shared_stopindex_v5_20261029`）の25番目 ss261119a25 は、独立検証の native_logs だけが INVALID になった。未分類の警告は `Warning: Vehicle 'choice_drt_1' aborts stop.` の1行だけ。学校PCの照合では、取消（timeout）のあとに待機（idle）で 3274#0 に停車（parked、stop_state 3）していた DRT が、閉鎖 T=15000 の制御周回 14999.5 で、理由 `initial_or_current_closed` で除去され、同じ時刻・同じ道路に `closure_applied` があった。v5 の分類器は、`aborts stop` を status が boarding・alighting のときだけ許容していた（validate.py の v5 版 2147行）。制御の不具合（H4）や観測の不一致（H3）の証拠はない（H1）。

ss261119a25 は reject 済み（INVALID_PRESERVED）。PAP §8 に従い、共通実装（検証器）を変えるので、新版で全70セルをそろえる（C2）。

**規則の根拠は、観測した1件の数値ではなく、制御器のコードの経路に置く。** `jdrt_realtime_choice.py` の制御周回は、その時刻までに予定された閉鎖を適用して `closure_applied` を記録し（924–937行）、同じ周回で、今いる通常道路が閉じた車両を `initial_or_current_closed` で除去する（940–953行の `remove_current`）。SUMO は、車両が保持していた停車を終えないまま道路網から外れたので、その停車を `aborts stop` と報告する。

**実 SUMO での再現（開発PC、採用しない技術証拠）：** 新しい人工ケース `drt_parked_current_closure`（§3.2）を SUMO 1.26.0 で実行し、`Warning: Vehicle 'choice_drt_0' aborts stop.` が1行だけ出ることを確かめた（suite `pk261121dev`、子 c19・c20・c31。v5 workspace の `technical/` に新しく作成）。c31 では、閉鎖 T=103 の制御周回 102.5 に、`closure_applied`（d0、passenger）と `actor_removed`（initial_or_current_closed）が同時にあり、除去時刻の観測行は parked、stop_state 3、status idle、road d0。規則を足す前の v5 の分類器では、この出力は native_logs INVALID、v6 の分類器では PASS（分類 `parked_stop_current_closure_abort`）。

## 2. 維持する契約

- 全70セル、登録順、5seed、D0/D1、需要・供給・人物・施設・退出・受付・配車・取消・乗降、徒歩能力、主副指標・分母・比較式・除外規則は、既存の PAP・Registry と同じ。
- 予定閉鎖 T、実呼出し max(0, T−0.5)、観測上限 T、phase、0.5秒 step を維持する。制御器 `jdrt_realtime_choice.py`、`jdrt_realtime_choice_inputs.py`、`jdrt_choice_policy.py`、`realtime_choice_cell.py`、native binary・patch・TraCI の呼び出しは変えない。
- 変えるのは、検証器の native 警告の分類の1分岐と、その受領の1キーだけ。受入の他の閾値、他の警告の分類、歩行予算は変えない。
- 既存の boarding・alighting の `aborts stop` の分岐と、`skips stop` の分岐は、文面も判定も変えない。

## 3. 観測・検証の改訂

### 3.1 分類規則（`audit_native_logs` の `aborts stop` の分岐に、許容の分岐を1つ足す）

既存の共通条件（DRT の除去イベントと除去時刻の観測行があること、時刻の一致、`max(0, T − step) ≤ 除去時刻`、除去理由が3種類のどれか）は変えない。status が boarding・alighting でない `aborts stop` は、次の (a)〜(g) を**すべて**満たすときに限り許容する。

- (a) 警告の行が `Warning: Vehicle '<id>' aborts stop.` と完全に一致する。同じ車両の行は1回だけ使える（既存の `used`）。2回目は未分類。
- (b) その車両の `actor_removed` が、すべての mode を数えてちょうど1件で、mode は passenger。除去理由は `initial_or_current_closed` だけ（`route_cut`・`stranded_drt` は新しい分岐では認めない）。
- (c) 除去時刻の観測行（`removal_observations`）があり、時刻が除去と一致し、`observation_kind == 'parked'`、かつ `stop_state` が整数の文字列で `int(stop_state) & 1 == 1`。このために、受領に `stop_state` を足す（キーを1つ追加）。
- (d) 観測行の `road_id` は空でなく、`:` で始まらない（通常道路）。hazard に、その道路の passenger の閉鎖時刻 T がある（有限）。
- (e) `max(0, T − step) ≤ 除去時刻`（既存の条件と同じ。新しい時刻の幅は足さない）。
- (f) 除去と**同じ時刻**に、**同じ道路**の `closure_applied`（mode=passenger）がある。
- (g) status は条件にしない（ユーザー判断「1案c」）。

分類の証拠には `classification: parked_stop_current_closure_abort` を付け、`evidence` に観測行（stop_state を含む）を残す。v6 の25番目の検査点で、この証拠を読む。

**緩めない点：** 走行中（onroad）の除去、停車の bit が0の除去、時刻の不一致、閉鎖と同時でない除去、閉鎖のない道路、内部レーン、歩行者の除去、除去イベントや観測行がない場合、除去が2件以上、同じ警告の2回目は、すべて未分類のまま INVALID。

### 3.2 fixture（人工の試験。研究入力ではない）

- **実 SUMO の新ケース `drt_parked_current_closure`**（`jdrt_choice_fixtures.py` の `CASES` の**末尾**。子 ID は `_c31`。既存の c01〜c30 の番号は動かない）。入力は `pickup_internal_timeout` と同じ（同じ網・同じ人工の過小予測・同じ締切）にして、閉鎖を1つだけ足す。閉鎖の時刻は、`pickup_internal_timeout` の native 出力（SHA で結び付ける）から導く：timeout の取消のあとの `cancel_wait_route` の道路で、車両が parked・idle・stop の bit 1 で停車した最初の時刻 t₀ をとり、T = floor(t₀) + 1。t₀ から T まで、車両がその状態のままであることを参照の出力で確かめる（そうでなければ fixture の準備で止まる）。選んで実行するときは、`pickup_internal_calibration` → `pickup_internal_timeout` → 新ケースの順に、同じ suite で走る。
- 検査（factory の評価）：参照と同じ取消・待機、同じ時刻の `closure_applied` と `actor_removed`（initial_or_current_closed）がちょうど1組、除去時刻の観測行が parked・stop の bit 1・閉鎖の道路、`aborts stop` がその車両について1行だけ、人物の結果が参照と同じ。
- 独立の確認：`G4_統合fixture独立監査.py` に、このケースの警告の許容と、生の出力から計算し直す分岐の検査を足した。
- `REQUIRED_FIXTURE_CASES`（validate.py）の末尾にも足した。READY の suite は31ケースを要する。

### 3.3 反例

- 単体試験（`04_プログラム/tests/test_jdrt_choice_validate.py` の `ParkedAbortStopContracts`、16件。合成の値だけ）：許容する P1 idle、P2 pending_idle、P3 cancel_wait、P4 既存の boarding・alighting（理由3種類。新しい分類の印が付かないこと）。許容しない N1 onroad、N2 stop_state が '2'・'0'・空、N3 理由 route_cut・stranded_drt、N4 除去イベントなし・観測行なし、N5 観測時刻の不一致、N6 除去が T−step より前、N7 `closure_applied` がない・時刻がずれる・別の道路・mode が pedestrian、N8 閉鎖のない道路（closure_sec が空、または mode 違い）、N9 同じ行が2回、N10 内部レーン、N11 歩行者の除去、除去が2件、`CASES` と `REQUIRED_FIXTURE_CASES` が一致して新ケースが末尾。
- 実 fixture に対するメモリ上の改変反例（`G4_正式検証器_表会計候補試験.py` の `parked_abort_counterexamples`、12件と存在の確認1件）：onroad、stop の bit 0、route_cut、stranded_drt、除去イベントなし、観測行なし、観測時刻のずれ、閉鎖の窓より前の除去、`closure_applied` なし、`closure_applied` の時刻のずれ、閉鎖のない道路、同じ行が2回。開発PCで c31 に当てて、対照は PASS、12件すべてが `all_warnings_evidence_classified=false` で INVALID になった。

### 3.4 遡及の確認（読み取りのみ。`06_研究結果/jdrt/goal_20261017/C2_v6_遡及確認_停車中除去分類.py`）

v5 の分類器（git HEAD の validate.py。CRLF での SHA は v5 の READY と同じ d7d920c4…）と v6 の候補を、開発PCにある choice 系列の全出力に当てた（結果：`C2_v6_遡及確認_結果_20261121.json`）。

| 区分 | 件数 | v5→v6 |
|---|---|---|
| `aborts stop` も `skips stop` もない出力（ログの走査だけ。変更が `aborts stop` の分岐に限られるので、構造上変わらない） | 594 | 不変 |
| 全部を監査し直した出力（`aborts`/`skips` を含む fixture と、v5 の全 technical） | 132 | 131件が不変、1件が変化 |
| 変化した1件 | `pk261121dev_c31`（今回作った新ケース） | INVALID → PASS（想定どおり） |
| 両版とも評価できない出力（旧形式の列がない、parameter_path がない） | 25 | 両版とも同じ例外。うち18件は v1 の古い fixture の c05〜c07 |
| ss261119a25、v5 の記録済み24セル | 開発PCに出力がない | **未確認**（学校PCで行う） |

既存の boarding・alighting の fixture（v2・v3・v4・v5 の c05〜c07、v1 の後期の c05〜c07）は、すべて PASS のまま。**限界：** 24セルには DRT の除去が0件なので、新しい分岐はそこには届かない。この確認は「変わらない」ことの確認で、識別力の証拠は §3.2・§3.3 が担う。

## 4. 版の分離と開始条件

- **共通5の SHA が変わる。** `execution.implementation_files` のうち validate.py だけが変わる（LF 正規化した SHA-256：v6 候補 `c300deb6…`。commit 後の学校PCの値で確定する）。他の4件は v5 と同じ。
- その結果：(1) v5 の記録済み24セルは、現在の共通版の照合（`audit_run_tables` の `require_current`、`realtime_choice_cell.py` の `record_identity_mismatch`）を通らない。v5 の workspace に元のまま保全し、v6 の台帳へ転記しない。(2) v5 の READY（2026-11-08）は使えない。`verify_preflight_receipt` が、unit の実装 SHA、fixture factory の SHA（`jdrt_choice_fixtures.py` も変わる）、`REQUIRED_FIXTURE_CASES` との一致（31ケース）、反例スクリプトの SHA（`G4_正式検証器_表会計候補試験.py` も変わる）、検証器の SHA を照合するため。`choice_revalidate.py` で READY を取り直す（fixture の段は `CASES` を全件たどるので、新ケースを自動で含む。独立の段は `G4_正式検証器_表会計候補試験.py` を走らせる）。(3) v6 は新しい workspace・入力・記録2ファイル・親ループの状態で始まる。
- 開始条件：関連の unit と反例、31ケースの実 SUMO fixture と独立の監査、全14設定の smoke、現行の入力・依存の SHA、新しい preflight READY、容量、07監視の新しい対象（v6 の4パターン）がそろうまで、core を始めない。1セル目は専用 CLI で手で行い、2セル目から親ループ（検査点案 `[8,18,25,28,38,48,58,68]`）。
- v6 のセル1〜24について、出力の SHA（manifest を除く）を v5 の同じセルと比べる（運用の停止条件。不一致なら止めて調べる）。v6 で新しい未分類の警告が出たら、再び reject と再登録の判断へ戻る。自動の再実行はしない。
- ss261119a25 の v5 の出力は、新しい規則でも採用しない（INVALID_PRESERVED のまま）。

## 5. 承認を求める点（ユーザー）

1. §3.1 の規則の文面 (a)〜(g)。
2. `native_diagnostic_observation_contract` にキーを1つ足すこと（差分案の7）。
3. 「この1件を見てから基準を変える」危険の受容（設計書 §3.5）。危険を減らす設計：根拠を制御器の経路に置く、時刻の幅を足さない、(c)(f) で条件を締める、実 SUMO の再現、許容しない反例、遡及の不変確認、検査点25。


**承認の記録（2026-11-21）：** 開発PCのチャットで、ユーザーが上の1〜3を「承認する」と直接回答した（台帳 `00_全体整理/判断と結果の台帳.md` の JD-20261121-v6-rule-approved）。status の範囲は、それ以前の「1案c」（JD-20261121-c2-user-decisions）による。25番目 ss261119a25 の棄却は「aで行う」（JD-20261121-reject-approved）で、学校PCが実行した。この承認に基づいて、2026-11-21T15:12:52（JST）に登録の取引を行った（registration_id `choice_parked_abort_v6_20261121`、受領 `06_研究結果/jdrt/goal_20261017/C2_v6_registration_20261121/application01/registration_receipt.json`）。

## 6. 設計書との差分（実装で決めた点）

- (b) の「ちょうど1件」は、passenger だけでなく**すべての mode** の `actor_removed` を数える（厳しくする向き）。
- (c) の `stop_state` が空・整数でない場合は、例外にせず未分類にする（歩行者の行など）。
- fixture の閉鎖時刻は「最初の parked・idle の時刻より後の最初の整数」とし、その時刻まで状態が続くことを参照の出力で必須にした（設計書は「より後の整数」）。
- `audit_fixture_timing` には新ケースの役を足していない（not applicable で PASS）。閉鎖時刻の導出は、factory の評価と `G4_統合fixture独立監査.py` の生の出力からの計算し直しで確かめる。
- `G4_統合fixture独立監査.py` の `REQUIRED`（16ケースの旧い集合）は変えていない。READY の依存ではない（`choice_revalidate.py` が走らせるのは `G4_正式検証器_表会計候補試験.py`）。
- 反例は、設計書の N1〜N9 に、除去イベントと観測行の欠落を分け、`closure_applied` の欠落とずれを分けて、12件にした。
