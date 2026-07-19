# Phase 3 実装タスク詳細（フェーズA：常総市先行）— 再開可能タスクカード集

> 作成日：2026-07-03／作成：Claude Code（opus）
> 目的：Phase 3 実装を**1タスク=1カード**に分割し、新規セッションでもカード単独で着手・再開できるようにする。
> 上位：`Phase3実装前仕様_P3-IMPL-0.md`（仕様正本）／`Phase3実装指示書_常総先行_Codex向け.md`（手順）／`Phase3_実装タスク管理.md`（ID登録の正本）

## 新規セッションでの再開手順（最初に読む）
1. 本ファイルの「進捗ボード」で `▶次にやる` のカードを見つける。
2. そのカードの「読む正本」を開く（判断の背景はここで復元できる）。
3. カードの「作業内容→完了条件」を実行。完了したら**状態を✅にし、`開発メモ/方針判断_fable5/00_総合監査/fableチェック_修正タスク.md` の該当タスク（T-D-H1/C2/M2）と `Phase3_実装タスク管理.md` を更新**。

## 確定事実（全カード共通の前提）
- 対象＝常総市 **08211**／full解像度。避難対象＝**A31a想定最大＝21,539人・高齢6,191人・405メッシュ・世帯換算9,569台**（`Phase3_規模整合メモ.md`）。
- 会計：削減式 `救出走行台数 = 非保有世帯数 × r − (バス実輸送人数 ÷ k)`、**r=1.0（感度0.5/0.75/1.0）・k=2.3・自家用車1台/世帯・非保有率15%（感度10/20）**（`車両会計_方針判断_fable5.md`）。
- 定義：逃げ遅れ＝**人単位**（世帯車1台=2.3人／救出走行1台=k人／バス=実乗車）。避難完了＝避難所到着（`用語定義集.md`）。
- 時間軸：加速浸水シナリオ・**逃げ遅れ絶対数は主張せずA/B相対・Type別**（`時間軸_方針判断_fable5.md`）。
- 関連config：`CAR_OWNERSHIP_RATE=0.85`（非保有0.15）・`ELDERLY_RATE=0.27`・`BUS_COUNT_BASE=5`・`BUS_CAPACITY_STD=8`・`BUS_CAPACITY_WELFARE=4`・`BUS_SENSITIVITY=[3,5,10]`。`HOUSEHOLD_SIZE=2.3`（p2_region_pipeline内）。

---

## ⚠️ 2026-07-09 差し戻し（[[シナリオB再実行_方針判断_fable5]]）

**B側成果物は「計測run（14:48台）」と「未完走run（15:24台）」の混合物であり、完走した『車＋バス』のシナリオB runは一度も存在しない。** 既報の「バス到着67人」「救出走行29台削減」「B側9,540台」「充足率0.271／0.0206」はすべて**撤回**。あわせて、シナリオAは `time-to-teleport` がSUMO既定300秒のままで、**「9,569台全到着」がテレポート非依存であることが未証明**のため、R4も再実行（A'）対象とする。

先に F系（実行系是正）を完了させること。F系の完了前に B3〜B5・E系・S系・V系を進めてはならない。

## 進捗ボード（状態一覧）
| ID | タスク | 担当 | 依存 | 状態 |
|----|--------|------|------|------|
| **A0** | 対象規模是正・常総full origins再生成 | Codex | — | ✅ |
| **R1** | 救出走行パラメータのconfig化 | Claude | — | ✅ |
| **R2** | メッシュ別 非保有世帯数・救出走行OD算出 | Claude | A0,R1 | ✅ |
| **R3** | 救出走行2レグtrip生成→scenario_a.rou.xml注入 | Claude | R2 | ✅ |
| **F1** | 共通モジュール抽出（閉鎖適用＋リルート＋出発前ブロック／終了条件述語／vehicle_log・summary書き出し） | Claude | — | ✅ コード実装済み（A'回帰ゲート未完走） |
| **F2** | `p2_traci_bus.py:616` の過剰break削除 | Claude | F1 | ✅ |
| **F3** | `time-to-teleport=-1` をA・B両sumocfg生成コードで統一 | Claude | F1 | ✅ |
| **F4** | route_file既定値廃止＋`--phase {measure\|final}`＋台数アサーション＋出所マニフェスト（run_id/SHA256） | Claude | F1 | ✅ |
| **R4'** | シナリオA再実行（teleport=-1・共通モジュール経由）・基準再固定 | Codex | F1〜F4 | ✅（A'再固定・床効果は不成立） |
| **B1** | バス拠点・停・乗降地点の設定（SUMO edgeスナップ） | Claude | A0 | ✅ |
| **B2** | バスroute生成（固定ルート・9往復上限） | Claude | B1 | ✅ |
| **G1.5** | 段1.5バッチ：E1本体（A側先行）＋B計測runゲート改修（決定39）＋分解summary拡張 | Claude | R4' | ✅（コミット 666a25e） |
| **G1.6** | 段1.6バッチ：E1指標定義の確定（固定分母3,231.5・バス到着取込）＋A側解釈診断4件 | Claude | G1.5 | ✅（コミット b1df574） |
| **G1.7** | churn是正：`.gitattributes`（`*.py text eol=lf`）＋scripts/tests限定renormalize（単一コミット・run無し） | Claude | G1.6 | ✅（コミット d11df9e・git_dirty_scripts=false を確認） |
| **B3** | 救出走行削減の会計連動（バス実輸送÷k） | Claude | R4',B2 | ✅（段2 B計測run完走・run_id measure_20260711T000129_79ef4dc8・gates_ok=true・バス到着141人）／⚠️バス到着は141ではなく**125人**（terminated 2便の車内16人は乗車中孤立=not_arrived・決定59-60） |
| **B4** | シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス） | Claude | B3 | ✅（段2'完了・4コミット bb82252/c602dab/320afa7/23e0375・削減54台・B側9,515台・AC3一致・pytest 64 passed） |
| **B5** | TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計） | Claude+Codex | B4 | ▶次にやる（段3＝B確定run・phase final・9,515台＋バス5台・`--expected-vehicles 9515` 必須・AC7合格帯 n'∈[120,131]） |
| **E1** | 評価を人単位・Type別へ拡張（逃げ遅れ人/完了時間/渋滞/公平性） | Claude | R4',B5 | ✅ 8run帯充填完了（コミット 21c5eb3・A/B完了率算出済み）／主指標ヌル確定（決定105）／⚠️ 再集計要（決定118・replicate_metricsが band_summary/E2と非整合・run無し・主結論ヌルは不変） |
| **E2** | A/B比較CSV生成（人単位・Type別） | Claude+Codex | E1 | 未着手（✅取消・既存CSVは破棄） |
| **E3** | 床効果判定・主指標の確定 | Claude(判断) | E2 | ✅ 主指標ヌル確定（決定105・106・符号表e2004d7）／S系10台も条件付き終了・ヌル頑健（決定113・S-1で確定）／残＝E3本文（regime bimodality主役・方向主張禁止） |
| **S1** | バス台数感度 3/5/10 実行 | Codex | B5 | ✅ **確定終了**（バス10台×B5seed＝5run・`e2d6c55`）。S-1（10台E1符号表 raw 正10/負5・非一貫・`decision109_stop_s_series=True`）で決定113の条件付き終了を解消→ヌルは増車でも頑健。s10_b2 seed42はロックregime帯内保持（決定112）。3台不要（決定115） |
| **S2** | 圧縮率感度でA/B順位の不変性確認 | Claude+Codex | E2 | 取り止め（決定109・[[S系帰結判断_方針判断_fable5]]）。ヌルには順位がなく圧縮率のA/B順位不変性は適用不能 |
| **V1** | Excel成果物生成（P3-IMPL-8） | Claude+Codex | E2 | ✅ 完了（`outputs/p3-impl-8/phase3_results_excel.xlsx`・7シート・8run/15組符号表/raw保守帯/S系10台・目視QA済・エラーセル0） |
| **V2** | アニメHTML（バス/車を区別・P3-IMPL-9） | Claude | B5 | ✅ 完了（`e2d6c55`・`output/sumo/viz/phase3_viz.html`・帯ゼロまたぎ図/二峰性図/Canvasアニメ）／視覚QA PASS（V-1/V-2/V-3・2026-07-13・playwright） |
| **V3** | phase3.html更新（P3-IMPL-10） | Claude | V1,V2 | ✅ 完了（`e2d6c55`・`output/phase3.html`・未実装表記撤去・アニメ/E2/符号表/感度へリンク）／視覚QA PASS（V-1/V-2/V-3・2026-07-13・playwright） |
| **V4** | テスト結果記録（P3-IMPL-11） | Claude | V3 | 未着手 |
| **V5-1** | gen_index.pyソース是正＋実行封印ガード | Claude | — | ✅ 完了（2026-07-18・ソース是正に加え、決定155で`main()`に実行封印ガード〔`GEN_INDEX_UNSEAL=1`でのみ解除〕を追加。数値リテラル追加なし） |
| **V5-2** | ~~ゲート付き再生成~~→**方針転換・破棄**（決定155） | Claude | V5-1 | 🔁 方針転換（2026-07-18・G3で`phase1.css`内容差を検出し停止→原因究明で`gen_index.py`が1世代古い生成器と判明〔taskbar/FAQ/chat未反映・再生成がindex/phase1/phase2をcard-grid化〕。**再生成方針を放棄**し[[段4_HTMLダッシュボード最新化判断_方針判断_fable5]]決定155で「全ページ手保守・再生成全面禁止」へ改訂。index/phase1/phase2はgit HEADから復元し外科的手編集で再適用〔決定156〕） |
| **V5-3** | faq.html外科的手編集（本文＋検索インデックス同期・V5-1/2と並行可） | Claude | — | ✅ 完了（2026-07-18・将来形を実装済みのヌル結論へ更新、Q4のteleport格下げ、本文と検索KBを同期、phase3評価結果へリンク） |
| **V5-4** | 静的QA（ソフトゲート・navリンク/アンカー/撤回値grep/方向主張精査） | Claude | V5-2,V5-3 | ✅ 完了（2026-07-18・全5ページ横断：stale framing 0件・撤回済み数値/X-5違反 0件・欠損アンカー`#overview`/`#phase-list`は復旧で実在復活〔決定158〕・phase3.html不変〔git diff HEAD空〕・真の内容差分は最小〔`--ignore-cr-at-eol`〕。ブラウザ描画QAはWSL/Chrome不在で不能＝環境制約として明記） |
| **V5-5** | 単一allowlistコミット（gen_index.py＋4 HTML＋判断記録） | Claude | V5-1〜V5-4 | ⏳ 実行中（2026-07-18・allowlist＝index/phase1/phase2/faq/gen_index.py＋判断記録＋本タスク文書。EOL churn整形・route等pre-existing除外。ユーザー承認：commit＋push） |

> **2026-07-10 段構成の改訂（[[段2計画_方針判断_fable5]] 決定40）：** 段1.5（E1本体のA側先行実装＋ゲート改修）を段2の前に挿入する。**正本run進行中は `04_プログラム/scripts/` 配下を編集しない**（マニフェストの `git_dirty_scripts=false` を壊すため）。run待ち時間の作業は文書（`01_`／`03_`／`05_`）に限る。卒論本文 P2-DOC-2 は即時着手し、run待ち時間の既定作業とする。

> **2026-07-10 段構成の確定（[[churn是正と決定46改訂_方針判断_fable5]] 決定54）：** 段1.7（churnコミット）→ 段2（B計測run・47分）→ 段2'（削減算出＋診断4スクリプト改修・run無し）→ 段3（B確定run）→ 段4（E系）→ 段5（S系8run・最低3セッション分割）→ 段6（V系・文書）。**打切り基準**：(i) 段2ゲート不合格が2回連続で停止・判断差し戻し、(ii) `.gitattributes` 導入後に `scripts/` churn再発で即BLOCKER停止、(iii) 段5でゲートを外れた設定のみ棚上げし残りを続行。

> **2026-07-10 段2実行方針（[[段2実行方針_方針判断_fable5]] 決定56・57）：** 段2の前にコミットは不要。**直行してよい。** run開始前チェック4点＝(1) route-file の sha256 がR4正本manifestと一致 (2) `git status --porcelain -- 04_プログラム/scripts/` が空 (3) HEAD sha を記録 (4) OneDrive同期を一時停止。実行形＝`p2_traci_bus.py run-bus --city-code 08211 --route-file <scenario_a.rou.xml> --phase measure`。直列・並行run禁止・予算3h（実測47分）。

> **段2の失敗モード事前判定（決定57）：** F1 ゲート不合格→原因特定後に再run、2回連続で停止・判断差し戻し／**F2 `bus_arrived` が0または極小でもAC6と改訂ゲートに合格なら続行**（これは計測の失敗ではなく結果。チューニングによる「改善」を禁止）／F3 boardedがA'参照値の半分未満→F1扱い／**F4 despawn便が7便以上（前回3便の倍増超）→停止・診断**／F5 層構成の大きな乖離→改訂ゲートが捕捉しF1扱い／F6 run所要94分超かつログ進行なし→中断・環境調査／**F7 `scripts/`（cache 2本含む）にdirty出現→BLOCKER停止**。

> **2026-07-11 段2結果解釈（[[段2結果解釈_方針判断_fable5]] 決定59〜66）：** 段2 runは有効（再実行不要）だが、バス到着141人は terminated 2便の車内16人を到着誤計上しており、正味**到着125人・削減54台・B側9,515台**が正。段2'に**集計修正コミット（fixtureテスト付き）を追加**し4コミット構成（cache除去→集計修正→診断4→rou再生成〔最後〕）。**AC6改訂**（arrivedは避難所到着イベント由来に限る・terminated便車内はnot_arrived・終端到着レコードがあればfail）＋**F8新設**（terminated便車内のarrived誤計上でhalt）。段3のAC7合格帯＝n'∈[120,131]・最大2巡・第2巡超過でhalt→Fable。E3予備見通し：完了率押上げ3.87%pt・充足率50.6%・乗車中孤立16人を従指標へ。

> **2026-07-11 段3実行方針（[[段3実行方針_方針判断_fable5]] 決定67〜72）：** 段2' PASS・**段3即時実行承認**（障害なし）。改訂AC6の結合検査・番兵値検査は `p3_validate_b_measure_gate.py:179` に実装済み・measure/final共用。段3は `--phase final`・HEAD `23e0375`・**ゲートに `--expected-vehicles 9515` を必須指定**。AC7（`|floor(n'/2.3)−54|≤2`＝n'∈[120,131]）は手計算。第1巡合格→段4へ／不合格→第2巡（削減₂=floor(n'₁/2.3)・第1巡停留所別到着でLR再配分）／第2巡超過→halt→Fable。n'は**上方バイアス**（削減がバス高活動域 origin_0057/0089 に集中・第2巡確率3〜4割）。層2>48かつ<層3→再加重分解で診断してから進む。**判断6-4（送届＝完了）は廃止**、決定60（terminated車内=not_arrived）が唯一の規範。

> **2026-07-12 段3R全8run完走：** B側5run（n'={75,122,125,125,165}・中央値125）＋A側3run（not_arrived A#1 479／A#2 1,854／A#3 450）が完走。A#2 seed42 は安全策付き再実行で完走し t=780凍結は再現せず（決定94の外部要因裁定を支持）。全run git_dirty_scripts=false・SHA一致。**バンド組成（決定76 E1帯）と符号一貫性判定（決定79）はFable判断へ差し戻し。** A#2の大振れ（1,854）の扱いは決定81との関係でFableへ。実行ログ＝`04_プログラム/テスト結果/phase3/段3R_レプリケーション実行ログ_20260711.md`。

> **2026-07-12 バンド組成判断（[[段3R_バンド組成判断_方針判断_fable5]] 決定99〜104）：** A#2（not_arrived 1,854）は**帯内保持・除外禁止**（決定81・会計完全9,569検算済み）。**従指標not_arrivedは符号非一貫（正2/負13）＝ヌル確定**（「本モデルの分解能ではA/B差は検出されない」・方向主張禁止）。B側n'＝中央値125（raw帯75–165）・保守124.2（帯75–124.2）両併記。**主指標（Type3/4完了率）の拘束的判定は段4のE1充填後・15組合せ・raw/保守両方で全同符号のときのみ方向主張**（規則は決定102で事前固定・符号表が出るまでE3本文を書かない）。即時作業＝powercfg復元・**A#3成果物のarchiveコピー**・A#2機構診断4点（読み取り専用）。決定76/79/81不変。

> **2026-07-12 段4 E1充填完了（コミット 21c5eb3）：** 8run完了率＝A{95.4448, 75.0193(A#2 seed42・regime), 96.5826}／B{92.3560, 95.4980, 95.6786, 96.4499, 97.6844}（分母3,231.5固定）。A#2診断：三層136/123/1594（層3 86.0%）・プラトー11,908秒・滞留541edge/121origin広域分散・挿入バックログ0（ロックregimeであり入口閉塞ではない）。検証記録＝`04_プログラム/テスト結果/phase3/段4_E1充填とA2診断_検証_20260712.md`。

> **2026-07-12 【研究主結論＝ヌル確定】（[[段4_主指標ヌル確定_方針判断_fable5]] 決定105〜111）：** 主指標Type3/4完了率のA/B差は **「本モデルの分解能では検出されない」で確定**（15組合せ符号が非一貫・**raw 正10/負5・保守 正8/負7**・raw点推定+0.23%pt・帯[−4.2,+22.7]%ptがゼロをまたぐ〔符号表再計算後 `e2004d7`〕）。方向主張は本文・要旨・図表で全面禁止（点推定符号・多数決読み・B#1外れ値除外は決定79/81/101が禁じた事後選別＝棄却）。**regime bimodality（A#2完了率75%ロックregime・B#1低完了率）を第一級の発見に格上げ**＝単一run避難シミュの初期条件脆弱性の実証（決定107）。**符号表CSVバグは是正済み**（旧正13/負2→完了率実値ベースで正10/負5・E2再生成・テスト5 passed・決定110・結論ヌルは不変）。**S系（バス10台×B5seed＝5run）は進行中**（決定109・完走後に符号一貫性でS系終了/3台追加を判定）。定量A/B主張は④完了率ヌル一本（①完了時間ECDF・②充足率絶対値・③Type別診断のみ・決定108）。**※本記録と段4メモ2件はSonnet委任が永続化失敗したためOpusが直接記録・検証済み。**

> **2026-07-12 S系（バス10台）完走・帰結判断（[[S系帰結判断_方針判断_fable5]] 決定112〜117）：** バス10台×B側5seed＝5run完走（確定route 9,515台・削減54固定・SHA `3d6977…8297` 一致）。バス到着n'={120, 24(s10_b2 seed42・halt), 180, 281, 257}。**s10_b2（seed42）はnot_arrived 2,159で halt**（A'受容域外）だが、AC全PASS・層2(157)<層3(1,862)・departure_blocked=0 で **valid regimeデータ点として帯内保持・除外禁止**（決定112・段3RのA#2と同型）。**seed42はA側（A#2）とB側10台（s10_b2）で独立にロックregimeへ落ちた**が B側5台では正常＝「seed×構成の相互作用」＝regime bimodality強化（決定116）。**S系は「条件付き終了」**（決定113）：ヌル頑健の裁定は下すが、確定は10台E1完了率の15組符号表（raw＋保守控除・削減54固定）計算後（b2上界0.969>A#1 0.954で符号は計算しないと閉じない）。事前登録判定則＝raw非一貫→即確定・全同符号→Fable差し戻し。バス3台は不要（決定115）。次＝S-1（10台E1集計・機械的・run無し）。決定31〜111は文言不変。

> **2026-07-12 S系確定終了・V系（[[S系帰結判断_方針判断_fable5]] 決定113の解消・コミット `e2d6c55`）：** S-1（10台E1符号表）完了＝raw 正10/負5・非一貫（`decision109_stop_s_series=True`）→ 決定113の判定則で**S系確定終了・「増車してもヌル」確定**（Fable再判断不要）。10台完了率 71.35〜102.01%（S10#4 102%は削減54固定・増車のみ設計の二重計上バイアス＝決定113/114想定内・バイアス下でも非一貫でa fortioriヌル）。**V2（phase3_viz.html）・V3（phase3.html）完了**（帯ゼロまたぎ図・二峰性図・Canvasアニメ）。**V1 Excel未完**（Spreadsheetsローダー不応答・ツール障害）・ブラウザ視覚QA未実施（webview timeout・静的ゲートPASS）。残＝E3本文（決定106文言・regime bimodality 2事例・増車非単調性・方向主張禁止）→ V1/QA → P2-DOC-2。実装検証＝`04_プログラム/テスト結果/phase3/段4_S系V系実装検証_20260712.md`。

> **2026-07-12 I-1〜I-3完了：** V1 Excel（`outputs/p3-impl-8/phase3_results_excel.xlsx`・7シート・エラーセル0）完了＝V系はExcelも含め完了（ブラウザ視覚QAのみ残）。S系CSVの単位系（rate×100=%pt）は修正不要（I-2）。s10_b2 missing_fcd 13台は「走行中滞留」（未挿入ではない・I-3）——ただし対象IDはゲートJSON正本では **`rescue_origin_0088_0004`〜`0016`（救出走行=Type3/4）**（実装者記録の `veh_full` は転記ミス）。決定112のS-2＝非ブロッキング・ヌル結論に無影響。**研究の主結論（ヌル）は不変。残＝E3本文・ブラウザ視覚QA・P2-DOC-2。** 検証記録＝`04_プログラム/テスト結果/phase3/段4_I1I3完了検証_20260712.md`。

> **2026-07-13 計画判断（[[段4_計画判断_方針判断_fable5]] 決定118〜122）：** Fableが**E1監査不整合**を発見・Opus実データ確認＝`phase3r_e1_replicate_metrics.csv`（正13/負2・A#2=75.87/B#4=98.53）が band_summary/符号表/E2（正10/負5・A#2=75.02/B#4=96.45・**引用値=こちらが正**）と非整合（`e2004d7`がreplicate_metricsを再生成し忘れた残置）。**主結論ヌルは頑健**（両カウントとも非一貫）だが監査整合性に穴。**決定118＝replicate_metricsを決定43/44定義で再集計（run無し・最優先ブロッカー・パニック再run禁止）／決定119＝E3本文3段階・着手前提=118完了・差し戻し点X-1〜X-4事前登録／決定120＝視覚QAソフトゲート（今セッションでplaywright実施）／決定121＝I-3のID訂正必須（veh_full→rescue_origin_0088）／決定122＝順序（118→121+120並行→E3本文→V系→P2-DOC-2即時並行可）**。

> **2026-07-13 視覚QA（決定120・[[段4_視覚QA検証_20260713.md]]）：** V-1（描画・帯ゼロ横断・二峰性図・Canvas再生・リンクHTTP200・console error 0）／V-2（方向主張の非暗示・中立配色）／V-3（撤回値の非残存）＝**PASS**。**V-4＝FAIL・判断必須**：ExcelのS10#4 raw 102.01%に対しS系10台の保守系列が未計算（`phase3_s10_*` 3ファイルすべてraw専用・`conservative_sign_counts`等なし）＝決定114のraw＋保守併記要求に欠落（決定118と同種の監査穴・**主結論ヌル・S系終了判定〔決定115・raw非一貫〕は不変**）。S系10台保守系列の再集計（run不要）＋Excel/V2/V3への追加の可否をFableへ付託中。

> **2026-07-13 V-4対応・E1整合パス（[[段4_計画判断_方針判断_fable5]] 決定123〜125）：** V-4（S系10台保守未計算）はOpus検証で**保守も非一貫（正8/負7）・S10#4は保守で97.15%≤100%**を確認＝S系終了(決定115)・主結論ヌル不変。**決定123＝S系保守を再集計しExcel/V2/V3へraw＋保守併記追加（run無し・102%はraw保持＋保守併記、置換禁止）／決定124＝決定118と1パスに束ね1コミット（順序：118でA正本確定〔期待{75.02,96.58}〕→S保守→4表トリップワイヤ〔主raw正10/負5・主保守正8/負7・S raw正10/負5・S保守正8/負7から乖離でhalt〕＋raw⇔保守パリティ検査）／決定125＝差分スコープ再QA**。更新クリティカルパス：決定124（最上流ブロッカー）→〔決定121 ∥ 決定125〕→E3本文（律速）→V系最終。P2-DOC-2は全経路と並行可。

> **2026-07-13 決定124トリップワイヤ発火→決定110反転（[[段4_計画判断_方針判断_fable5]] 決定126〜130）：** E1整合パス実装中にトリップワイヤが発火し、Opus実行コード＋Fable独立検証で**band scriptの不良ハードコード `VERIFIED_COMPLETION_RATES`（決定110・e2004d7導入・A#3=1357は実到着1349超過で物理的に不能）**を検出。**正本は実データ算出＝正13/負2・点推定+1.2348%pt・帯[−3.09,+22.97]／保守正13/負2・+1.21%pt・[−3.09,+21.71]**（4ソース一致）。**決定110/118は誤り（決定118は帰属を逆判断）・決定105/106は正しい値で判断されており"復元"。主結論ヌルは不変**（負2組=B#1のみ・決定105が棄却済み）。**決定128＝実データ一本化＋全再生成（band_summary/符号表/E2/S系raw+保守/Excel/HTML）＋文書差し戻し（+0.23→+1.23等）＋トリップワイヤ4値更新（主raw/主保守=正13/負2・S raw正10/負5・S保守正8/負7）・run無し・最上流ブロッカー／決定129＝ハードコード指標ミラー禁止（真実源はアーカイブ算出のみ）＋自己整合assert新設。** 更新パス：決定128→〔決定121∥決定125〕→E3本文（+1.23で・律速）→V系。

> **2026-07-13 決定128実装手順（オプションC）確定：** 段階的実施手順を `決定128実装手順_オプションC.md` に記録。C-1コード修正（ハードコード削除・自己整合assert・S系保守新設・テスト正値化）→C-2再生成→**C-3 4値ゲート（主raw/主保守=正13/負2・S raw正10/負5・S保守正8/負7・自己整合0）で停止・報告**→C-4文書差し戻し（+0.23→+1.23等）→C-5単一コミット。ゲート不一致でhalt→Fable。

> **2026-07-13 着手前ゲート発火→決定131〜134（[[段4_計画判断_方針判断_fable5]]）：** 手順書の前提SHA`419ceaf`が誤り（会話開始時HEAD）→**現HEAD`e2d6c55`を正として前方是正・巻き戻し禁止（決定131）**。Fableが**循環テスト**（`test_verified_..._decision_110_sign_counts`がハードコードを自己照合・「64 passed」は偽の緑）を発見。**決定132＝是正範囲拡大（テスト脱循環化必須＝tripinfo/vehicle_log地上真実へassert・旧164行従指標表の無検証復活禁止・従指標所在をE3前に確認）／決定133＝未追跡.mjsを単一コミットに含める（band再生成→.mjs再実行→コミット）／決定134＝手順書HEAD訂正＋恒久規範拡張（SHA/完了率/符号を手順・判断にハードコードせず実測）。** 同一クラス事故3例目（band值・循環テスト・手順SHA）＝根本は「ライブ実測よりミラーを信頼」。主結論ヌル不変。

> **2026-07-13 決定128 段C-1完了（[[段4_決定128段C1完了検証_20260713.md]]）：** ハードコード`VERIFIED_COMPLETION_RATES`完全削除・主系列をbuild_metrics実データ一本化・自己整合assert新設・S10にraw/保守完了率＋符号＋パリティassert追加・**循環テストをtripinfo独立パースの地上真実テストへ置換**（決定132）。4ファイル限定。**4値ゲート事前合格**（地上真実テスト：主raw正13/負2・主保守正13/負2・S raw正10/負5・S保守正8/負7・到着数1341/1066/1349をtripinfoで独立検証・関連2テスト7 passed・実装者環境77 passed）。route SHA/CRLF無傷。252ファイル差分は既存EOL churn。**残＝段C-2正本再生成→E2/Excel/V2-V3訂正カスケード→単一コミット。正本ファイルは現時点で旧不良値のまま。** 主結論ヌル不変。

> **2026-07-13 段C-2以降計画（[[段4_計画判断_方針判断_fable5]] 決定135〜138）：** 決定135＝再生成後の4値ゲートは**ディスク実物Read**で再検証（テスト緑≠ディスク正・OneDrive同期消失前科）／**決定136＝コミットは明示allowlist・`git add .`禁止・`scenario_b.rou.xml`（決定86 CRLF churn）と250+churnを除外・コミット前後にroute SHA `3d6977…8297`不変を実測**／決定137＝従指標文書化はE3前ゲート（C-4並行・旧equity復活に非依存）／決定138＝E3前最終go/no-goゲート5条件（ディスク4値整合・旧値残存ゼロ・route不変・従指標文書化・循環テスト0）。主結論ヌル不変。

> **2026-07-13 C-3ゲートが保守帯max取り違えを捕捉→決定139〜140（[[段4_計画判断_方針判断_fable5]]）：** 段C-2再生成中、決定135のディスク実測ゲートがFable手順書の保守帯max**+21.71（B#5対A#2）を取り違えと判定**→ディスク実測**[−3.088349,+22.633452]%pt（max=B#4対A#2・cap124.2でrescue多いB#4がB#5を逆転）**へ訂正（決定139）。**主結論ヌル・保守符号正13/負2・保守点+1.2099644%pt・raw全値は不変**。決定140＝汚染は保守max1点のみ・S系保守は全数列挙で非汚染・新規ガード規範（帯min/maxは15組全数から算出しraw argmaxを保守へ引き継がない）。C-2続行裁可。決定135のディスク実測ゲートが判断者自身の手計算誤りを捕捉した好例。

> **2026-07-13 決定128 段C-2完了＋C-3ディスク実測ゲート合格（[[段4_決定128段C2完了検証_20260713.md]]）：** E2再生成（raw+1.2347207/[−3.088349,+22.970757]・保守+1.2099644/[−3.088349,+22.633452]・**B#4最大**・正13/負2）・Excel 7シートQA PASS・V2/V3 PASS（`gen_index.py`のimport json 1行修正）・S10 raw正10負5/保守正8負7・旧誤値残存なし・77 passed・route SHA無傷。**段C変更＝6スクリプト**（p3_phase3r_e1_bands・p3_s10_sensitivity_metrics・gen_index〔V3〕・p3_build_visualization〔V2〕・test 2本）＋未追跡mjs。HEAD e2d6c55未変更。**残＝段C-4文書差し戻し＋C-4'従指標文書化＋allowlistコミット＋E3前ゲート。** 主結論ヌル不変。

> **2026-07-13 段C-4以降計画（[[段4_計画判断_方針判断_fable5]] 決定141〜144）：** 決定141＝文書差し戻しは二層（現状文書=全訂正／判断記録=監査保持＋前方ポインタ・段4メモ⚠️注記のみ訂正必須）／**決定142＝allowlistにgen_index.py・p3_build_visualization.py追加・gen_index再実行禁止（多ページ副作用）・output系はchurn分類でパス明示add（実差分=phase3.html/phase3_viz.htmlのみ）・一括add禁止・index/phase1/phase2誤stage検査**／決定143＝従指標nativeソース明示＋補正値実測確認（bus125/削減54・旧equity復活禁止）／決定144＝grep-zeroは現状文書限定・判断記録は除外リスト。Opus検証：実内容差分はphase3系2ファイルのみ（他ページ未変更）。主結論ヌル不変。

> **2026-07-13 E3前ゲート実測（[[段4_E3前ゲート実測_20260713.md]]・決定138/144）：** 機械条件1(ディスク4値＋両帯＋8run tripinfo一致)・3(route SHA無傷・禁止ファイル非混入)・4(従指標nativeソース＋補正値)・5(循環テスト0・7 passed)＝**PASS**。条件2(現状文書grep)＝10行ヒットだが全て監査記録/訂正/S系正値でOpus追認＝現在値主張の旧値ゼロ＝**暫定PASS**。**決定138により最終goはFable裁可待ち（E3はno-go継続）。** commit f404837。主結論ヌル不変。

> **2026-07-13 E3前ゲート最終go（[[段4_計画判断_方針判断_fable5]] 決定145〜146）：** 5条件PASS・条件2の10ヒット除外分類はFable裁可（現在値主張の旧値ゼロ）→**E3本文着手go（決定145）**。E3は3段階・主指標raw+1.234721%pt/[−3.088349,+22.970757]・保守+1.209964%pt/[−3.088349,+22.633452]・raw/保守とも正13/負2。**新設X-5＝+1.23はregime分散に埋没の微差・方向読み封じ（最重要）**。監査polish2件（line76太字除去・line105に決定139ポインタ）実施。commit f404837。主結論ヌル不変。

> **2026-07-18 V5系（HTMLダッシュボード最新化）方針確定（[[段4_HTMLダッシュボード最新化判断_方針判断_fable5]] 決定150〜154）：** 主結論ヌル・E3確定稿より古いHTML成果物（index/phase1/phase2/faq）を最新化する。**決定150** スコープ＝4画面のみ（sumo/regions・sumo_viz除外／phase3.html・phase3_viz.htmlは不変ゲート対象）／**決定151** 更新機構＝gen_index.pyソース是正＋ゲート付き限定再実行（生成物直接手編集は不採用・faqのみ手編集・決定142「gen_index再実行禁止」を文脈的規範と位置づけG1〜G5付きで再実行許可・数値リテラルHTML直書き禁止=決定129）／**決定152** 5ゲートG1退避〜G5差分限定（`git restore`禁止=決定86・phase3不変・route SHA `3d6977…8297` 不変）／**決定153** 各画面最小十分集合＋X-5文言境界拡張（equivalence表現も禁止）／**決定154** 全タスクClaude Code直接・順序V5-1→V5-2→V5-4→V5-5（V5-3並行）・視覚QAソフトゲート（環境制約は明記）・HTML最新化は繰延対象外で今実施可。カード＝V5-1〜V5-5。主結論ヌル不変。

---

# タスクカード

## A0：対象規模是正・常総full origins再生成
- **担当**：Codex ／ **依存**：なし ／ **読む正本**：規模乖離判断・規模整合メモ・実装指示書A-1
- **作業内容**：region pipeline で 08211 の派生データ（t7＝A31a想定最大 origins）を再生成する。
  ```
  cd 04_プログラム
  python scripts/p2_region_pipeline.py derived-city --city-code 08211
  ```
- **入出力**：出力 `output/sumo/regions/08211/derived/agent_origins_*.csv`（列：total_pop, elderly_pop, vehicle_count_full 等）。
- **完了条件**：メッシュ数≈405、total_pop合計≈21,539、vehicle_count_full合計≈9,569。旧 `output/agents/origin_points.csv`（2,257人）は主結果に使わず「t0感度ケース」ラベル。
- **注意**：旧 sumo_viz 常総パスを主に使う場合のみ `i3_route_search.py:279` を t7相当へ修正（本フェーズは region pipeline を主経路とする）。
- **完了記録（2026-07-04 Codex）**：`python scripts/p2_region_pipeline.py derived-city --city-code 08211` を `04_プログラム/venv` で再実行。`agent_origins_10pct.csv` は405行、`total_pop` 合計21,539、`elderly_pop` 合計6,191、`vehicle_count_full` 合計9,569、`vehicle_count_10pct` 合計1,151。`derived_data_validation.json` は `origin_unmatched_count=0`、`safe_shelter_unmatched_count=0`、`can_proceed_to_small=true`。

## R1：救出走行パラメータのconfig化
- **担当**：Claude Code ／ **依存**：なし ／ **読む正本**：車両会計判断・P3-IMPL-0 §2
- **作業内容**：`scripts/config.py` に救出走行パラメータを追加：`RESCUE_RATE_R = 1.0`（感度0.5/0.75/1.0）、`RESCUE_PER_VEHICLE_K = 2.3`、`NON_CAR_RATE = 0.15`（=1−CAR_OWNERSHIP_RATE、感度0.10/0.20）、`CARS_PER_HOUSEHOLD = 1.0`（感度上限1.55）。既存 `HOUSEHOLD_SIZE=2.3` を config へ集約（現状 p2_region_pipeline / p2_derived_data にローカル定義）。
- **完了条件**：定数が config に集約され、感度で振れるコメント付き。既存の import 互換を壊さない。
- **完了記録（2026-07-04 Codex）**：`scripts/config.py` に `HOUSEHOLD_SIZE=2.3`、`NON_CAR_RATE=0.15`、`RESCUE_RATE_R=1.0`、`RESCUE_RATE_SENSITIVITY=[0.5,0.75,1.0]`、`RESCUE_PER_VEHICLE_K=2.3`、`NON_CAR_RATE_SENSITIVITY=[0.10,0.15,0.20]`、`CARS_PER_HOUSEHOLD=1.0`、`CARS_PER_HOUSEHOLD_MAX=1.55`、`RESCUE_STOP_DURATION_S=60` を追加。`p2_region_pipeline.py` / `p2_derived_data.py` の `HOUSEHOLD_SIZE` と `p2_phase3_prep_agents.py` の `NON_CAR_RATE` を config 参照へ変更。`py_compile` と定数読み出し確認済み。

## R2：メッシュ別 非保有世帯数・救出走行OD算出
- **担当**：Claude Code ／ **依存**：A0,R1 ／ **読む正本**：P3-IMPL-0 §2/§3
- **作業内容**：agent_origins（08211）から**メッシュ別**に算出する新規関数：
  - 世帯数 = total_pop ÷ HOUSEHOLD_SIZE。車保有世帯 = 世帯×(1−NON_CAR_RATE)、非保有世帯 = 世帯×NON_CAR_RATE。
  - 自家用車避難台数 = ceil(車保有世帯 × CARS_PER_HOUSEHOLD)。救出走行台数 = 非保有世帯 × R（メッシュ合計で約1,405台）。
  - 救出走行OD：発＝当該メッシュ（or 最寄り車保有メッシュ）、経由乗車＝当該非保有メッシュ、着＝最寄り安全避難所（`shelters_safety.csv`）。
- **入出力**：出力 `output/sumo/regions/08211/derived/rescue_od.csv`（列：mesh, 非保有世帯数, 救出走行台数, 発edge, 乗車edge, 着shelter）。
- **完了条件**：救出走行台数の合計が会計（≈1,405台・非保有率15%時）と一致。自家用車台数合計≈8,164台。
- **完了記録（2026-07-04 Codex）**：`p2_region_pipeline.py` の `derived-city` に `rescue_od.csv` 生成を追加。`rescue_od.csv` は405行、`non_car_households` 合計1,404.715（CSV丸め後）、`rescue_vehicle_count` 合計1,405、`private_vehicle_count` 合計8,164。`rescue_start_edge_id` / `pickup_edge_id` / `shelter_edge_id` の欠損0。整数化はメッシュ別raw値にlargest remainder方式を適用し、発edge・乗車edgeは同一メッシュedge、着edgeは最寄り安全避難所edge。

## R3：救出走行2レグtrip生成→scenario_a.rou.xml注入
- **担当**：Claude Code ／ **依存**：R2 ／ **読む正本**：P3-IMPL-0 §3・実装指示書A-2・既存 `p2_region_pipeline.generate_region_scenario`
- **作業内容**：救出走行を**2レグtrip**（`発edge→乗車edge`で停車(stop duration≈60s)→`避難所edge`）としてSUMO trip/route化し、`scenario_a.rou.xml`（full）へ id接頭辞 `rescue_` で追記。既存の自家用車route生成（vehicle_count_full ベース）と別カウントで共存させる。edgeスナップは既存の snap ユーティリティ（`p2_sumo_snap`）を再利用。
- **完了条件**：`scenario_a.rou.xml` に自家用車（≈8,164）＋救出走行（≈1,405）＝合計≈9,569台。SUMOでrouteエラーが出ない（duarouter/netcheck）。
- **完了記録（2026-07-04 Codex）**：`p2_region_pipeline.py scenario-city --city-code 08211 --scenario full` で `scenario_a.rou.xml` を生成。XML内訳は自家用車trip 8,164、救出走行vehicle 1,405、pickup stop 1,405、合計9,569。`scenario_a_vehicle_assignments.csv` も private 8,164 / rescue 1,405 / edge欠損0。`sumo --net-file ../network/08211.net.xml --route-files scenario_a.rou.xml --begin 0 --end 1 ... --ignore-route-errors false` が exit 0。

## R4：シナリオA（救出走行込み）full再実行・比較基準再固定
- **担当**：Codex ／ **依存**：R3 ／ **読む正本**：実装指示書A-2
- **作業内容**：
  ```
  python scripts/p2_region_pipeline.py scenario-city --city-code 08211 --scenario full
  python scripts/p2_region_pipeline.py run-city --city-code 08211 --scenario full
  ```
- **完了条件**：`scenario_a_traci_summary.json`・`scenario_a_tripinfo.xml` 等が生成。車両内訳が会計と一致。**この結果を新しい比較基準（シナリオA）として固定**（`Phase2_比較基準固定.md` に追記）。
- **完了記録（2026-07-09 Codex）**：`output/sumo/regions/08211/results/scenario_a_traci_summary.json` を確認。車両9,569台、到着9,569台、未到着0、long_stopped=102、閉鎖イベント8、最終閉鎖SUMO edge=8,968。R4基準として利用。
- **⚠️ 2026-07-09 ✅取消（[[シナリオB再実行_方針判断_fable5]] 決定3）**：`scenario_a.sumocfg` に `time-to-teleport` 指定がなくSUMO既定300秒のテレポートが有効。テレポート発生数は記録されていないため、**「9,569台全到着」がテレポート非依存であることは未証明**。床効果はこの結果では確定できない。F1〜F4完了後に `teleport=-1` で再実行（R4'）し再固定する。**旧R4の到着数に合わせる操作は禁止**（不一致なら不一致のまま再固定）。

## R4'：シナリオA再実行（teleport=-1・共通モジュール経由）・基準再固定
- **担当**：Codex ／ **依存**：F1〜F4 ／ **読む正本**：[[シナリオB再実行_方針判断_fable5]] 決定1・決定3
- **作業内容**：F1の共通モジュール経由・`time-to-teleport=-1` でシナリオAをfull再実行する。
- **完了条件（AC1）**：`arrived=9,569`・`not_arrived=0` なら床効果確定かつR4数値維持（設定記録のみ更新）。不一致ならそのまま再固定し、床効果の記述を「テレポート補正後」の数値で書き直す。この場合 `long_stopped=102` の扱い（滞留か遅延か）を再判定する。
- **注意**：旧R4との一致確認は共通モジュール抽出（F1）の回帰ゲートを兼ねる。
- **試行記録（2026-07-09 Codex）**：F1〜F4実装後、`scenario-city --city-code 08211 --scenario full` で `scenario_a.sumocfg` を再生成し、`time-to-teleport=-1` が書き出されることを確認。その後 `run-city --city-code 08211 --scenario full` を実行したが、約26分で `scenario_a_fcd.xml` の最終timestepは1260秒までしか進まず、full完走には数時間規模を要する見込みだったため停止。AC1は未達。次はFCD出力抑制・ログ間隔・実行方式の軽量化を検討してR4'を完走させる。
- **完了記録（2026-07-10）**：`run_id: full_20260710T000934_fc2ca003`・コード版 `6106263`・wall-clock 47分で完走。**arrived 9,090／not_arrived 479／long_stopped 4,026**（旧R4は 9,569／0／102）。改訂AC1は「不一致」判定のため、[[A_prime結果解釈_方針判断_fable5]] 決定31によりA'を正本として再固定（旧値回帰は禁止）。**床効果は不成立と確定**（決定32）。滞留479台は三層分解（物理的孤立68／交差点閉塞24＋リング／待ち行列387）で「モデル規約下の滞留」と裁定。マニフェスト検証はAC5第3改訂の全条件をクリア。詳細＝`04_プログラム/テスト結果/phase3/段1_A_prime_full実行結果_20260710.md`。

## B1：バス拠点・停・乗降地点の設定（SUMO edgeスナップ）
- **担当**：Claude Code ／ **依存**：A0 ／ **読む正本**：H1・P3-IMPL-0 §4・既存 `bus_demand_candidates.csv`（P3-IMPL-2✅済）
- **作業内容**：バス拠点（デポ）・避難所側バス停・住宅密集メッシュ側乗降地点を定義し SUMO edge へスナップ。出力 `bus_stops.add.xml`（busStop要素）・`bus_stops.csv`・`bus_depots.csv`。乗車対象はType3/4（`agent_types.csv`／`bus_demand_candidates.csv`）。
- **完了条件**：全busStopが有効edgeにスナップ、避難所16〜19箇所付近をカバー。
- **完了記録（2026-07-09 Codex）**：`p2_phase3_prep_agents.py --city-code 08211` で405メッシュ版 `agent_types.csv` / `bus_demand_candidates.csv` を生成。`p3_bus_scenario.py smoke --city-code 08211 --buses 5` で `bus_plan.csv` / `bus_stops.add.xml` を生成。短すぎる乗車edgeはdespawn原因として除外し、5停（origin_0057/0084/0176/0089/0085）を採用。

## B2：バスroute生成（固定ルート・9往復上限）
- **担当**：Claude Code ／ **依存**：B1 ／ **読む正本**：H1（5台・8人/4人・20km/h・9往復）
- **作業内容**：バス5台（標準8人×4＋福祉4人×1）の固定ルート（乗降地点→避難所のピストン、6h・上限9往復）を `.rou.xml` の `<vehicle>`＋`<stop>` で生成 → `scenario_b_buses.rou.xml`。台数は `BUS_SENSITIVITY` で差し替え可能に。
- **完了条件**：SUMOでバスが走行し停車する（route検証OK）。
- **完了記録（2026-07-09 Codex）**：`p3_bus_scenario.py` を地域別ディレクトリ対応に拡張。`<route repeat>` はSUMO仕様上不可のため、TraCI `setRoute` による動的往復方式を採用。busonly検証で5台・36便・215人輸送、despawn=0、conservation_ok=true。

## B3：救出走行削減の会計連動（バス実輸送÷k）
- **担当**：Claude Code ／ **依存**：R3,B2 ／ **読む正本**：車両会計判断・P3-IMPL-0 §2
- **作業内容**：シナリオBの救出走行台数 = 非保有世帯数×R −（**バス実輸送人数**÷k）。バス実輸送人数はB5のTraCI集計を用いる（初回は机上324人で仮置き→B5後に実測で再生成）。**バス定員を超えて乗れないType3/4はシナリオAと同一（救出走行を残す）**＝会計クローズ。削減対象の救出走行tripを除外するロジックを実装。
- **完了条件**：シナリオBの救出走行台数＝A基準−(バス輸送÷k)。乗れない層の救出走行が残り、A/Bで人・車両総数が閉じる。
- **完了記録（2026-07-09 Codex）**：`バス輸送実測_方針判断_fable5.md` に従い、despawn未到着を輸送完了から除外。交通流込み実測は `bus_transport_total=67`、`bus_not_arrived=24`、`residual_queue=156`。k=2.3では raw=29.13台、整数削減29台。k=1.0感度では67台。
- **⚠️ 2026-07-09 撤回（[[シナリオB再実行_方針判断_fable5]] 決定5）**：上記の実測値（候補247・乗車91・到着67・残queue156）は**実行条件が特定不能なrun由来**（バスログのmtime 14:48:43 が現存 `scenario_b.rou.xml` 14:50:06・`scenario_b.sumocfg` 14:51:09 より前）。**全面破棄**。したがって削減29台も無効。F系完了後の計測run（第0巡・`--phase measure`）で再計測する。撤回理由は「シミュレーションに反映されなかったから」ではなく**分子の67人の出所が不明だから**であり、再計測後は会計量として従指標に復帰できる。

## B4：シナリオB車両route生成（自家用車＋救出走行(削減後)＋バス）
- **担当**：Claude Code ／ **依存**：B3 ／ **読む正本**：実装指示書A-3
- **作業内容**：自家用車route（Aと同一）＋救出走行(削減後)＋バス を統合し `scenario_b.rou.xml` を生成。Type3/4のうちバス乗車者は自家用車/救出走行から除外し二重計上を防ぐ。
- **完了条件**：バス対象者と自家用車/救出走行の重複がない。SUMO route検証OK。
- **完了記録（2026-07-09 Codex）**：`p3_bus_scenario.py build-scenario-b --city-code 08211` で `scenario_b.rou.xml` と `scenario_b_vehicle_assignments.csv` を生成。A基準9,569台から救出走行29台を除外し、B車両は9,540台（private 8,164 / rescue 1,376）。
- **⚠️ 2026-07-09 要再生成（[[シナリオB再実行_方針判断_fable5]] 決定5・決定6）**：削減29台の入力（バス到着67人）が撤回されたため **9,540台は無効**。さらに `p2_traci_bus.py:779` が `scenario_a.rou.xml` を既定にしていたため、**この `scenario_b.rou.xml` は一度もSUMOに読み込まれていない**。F4完了後、計測run（第0巡）の到着人数 n から `floor(n/2.3)` で削減台数を再算出して再生成する。
- **AC3（受け入れ条件）**：route XML台数 = 8,164 +（1,405 − 削減台数）と厳密一致（アサーション通過）。`settle_stranded_to_rescue` の丸め（`rescue_after_bus_vehicles_raw: 1375.585` → 1,376台）とrouteの整数台数の対応は、丸め方向を1箇所に固定すること。

## B5：TraCIシナリオB実行（乗降＋動的閉鎖＋乗車人数集計）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：B4 ／ **読む正本**：既存 `p2_traci_closure.py`
- **作業内容**：既存TraCI動的閉鎖にバス乗降処理を追加し、シナリオBを実行。各バスの往復数・乗車人数・所要時間を `scenario_b_bus_log.csv` に出力。`scenario_b_traci_summary.json` 生成。実輸送人数をB3へフィードバックし救出走行削減を確定（B3→B4→B5を1巡）。
- **完了条件**：道路閉鎖とバス走行が同時に動作。バス運行ログが出力され、実輸送人数で削減式が確定。
- **完了記録（2026-07-09 Codex）**：`p2_traci_bus.py` を地域別・Windows SUMOパス対応に拡張し、乗降ログ `scenario_b_passenger_log.csv`、便ログ `scenario_b_bus_log.csv`、summary `scenario_b_bus_summary.json` を生成。閉鎖打切りのみ送届完了扱いとし、despawnは未到着として別掲するよう修正。最終summaryは boarded=91、arrived=67、not_arrived=24、terminated_by_reason={despawn:3}、conservation_ok=true。despawnは残存リスクとしてE3/V4で扱う。
- **⚠️ 2026-07-09 実測値撤回・再計測待ち（[[シナリオB再実行_方針判断_fable5]]）**：**完走した「車＋バス」のシナリオB runは一度も存在しない。** 上記summaryは 14:48:43 のrun、`scenario_b_fcd.xml`／`scenario_b_tripinfo.xml` は 15:24:14 の**中断run**（`write_bus_outputs` に未到達）。両者は別runであり、E2はこの断片を結合して報告していた。boarded=91／arrived=67／not_arrived=24／residual_queue=156 は**全面破棄**。
  - なお **バス状態機械は無実**：`step_bus` の `sim_time` はTraCIループの `int(traci.simulation.getTime())` 由来で独立時計を持たない（`p2_traci_bus.py:330,340,344,593`）。バスログが17,048秒までありfcd最終が9,900秒なのは、両者が別runだから。**バス状態機械のコードは修正しないこと。**
  - 15:24 runは `scenario_a.rou.xml`（9,569台）で走っており、最終timestepで1,010台（private 860／rescue 146／bus 4）が走行中のまま終了した。原因は `close_edges_with_bus()`（`p2_traci_bus.py:244`）が乗用車をリルートしないこと（→F1で是正）。
- **再計測時の完了条件（AC2・AC5・AC6）**：`departed=9,569`／`arrived+not_arrived+departure_blocked=9,569`（厳密一致）。全B成果物が単一run（run_id一致）で、fcd閉じタグ完全、バス/乗客ログの全時刻 ≤ fcd最終timestep。`boarded=arrived+not_arrived`／`candidates=boarded+residual_queue`。
- **再計測後の検証（決定5）**：各便の所要時間をfcd軌跡と突合し、渋滞区間通過便の所要が自由流所要（バス単独スモークで取得）を上回ることを確認する。`bus_wf_1` の「947秒一定周期」（全19便中15便を占める）は、交通量依存の分散が出るか、経路が実際に無渋滞であることをfcd重畳で説明できるか、いずれかで決着させる。
- **段2 B計測run完走（2026-07-11・run混合是正後の初の有効計測）**：`run_id: measure_20260711T000129_79ef4dc8`・コード版 `d11df9e`・route sha256 `29464ee…`・wall-clock 63分。**gates_ok=true・halt不要**（AC2/AC5/AC6＋改訂ゲート全合格・決定57のF1〜F7に非該当）。バス候補247／boarded 141／arrived 141／not_arrived 0／残queue 106／terminated 2便（`closure_unreachable`）／`conservation_ok=true`。B側 not_arrived 484（A' 479と同水準）、滞留三層 71/36/377（A' 68/24/387と同型）。**段2'の削減台数＝floor(141/2.3)=61台。** 検証記録＝`04_プログラム/テスト結果/phase3/段2_B計測run検証_20260711.md`。
- **段2'完了（2026-07-11・4コミット）**：`bb82252`（cache 2本の追跡解除）→`c602dab`（バス乗客集計修正：terminated便車内をarrivedにせずnot_arrivedへ・fixtureテスト付き・補正集計 `scenario_b_bus_corrected_accounting.json` に arrived=125/not_arrived=16/residual=106・元summary非上書き・sha256継承）→`320afa7`（診断4再加重分解スクリプト化＋テスト）→`23e0375`（rou再生成〔最後〕）。**削減54台**（停留所別largest-remainder・合計54）、**B側9,515台**（AC3期待値と厳密一致・private 8,164/rescue 1,351）。pytest 64 passed・`scripts/` クリーン。検証記録＝`04_プログラム/テスト結果/phase3/段2primeE_集計修正とrou再生成_20260711.md`。次は段3 B確定run。

---

# F系タスクカード（実行系是正・[[シナリオB再実行_方針判断_fable5]]）

## F1：共通モジュール抽出
- **担当**：Claude Code ／ **依存**：なし ／ **読む正本**：[[シナリオB再実行_方針判断_fable5]] 決定1
- **作業内容**：`p2_region_pipeline.py` から**次の3点のみ**を共通モジュール（例：`p2_traci_common.py`）へ抽出し、A・B両方が呼ぶ。
  1. 閉鎖適用＋全車リルート＋出発前ブロック（`reroute_active_vehicles()` 相当・`p2_region_pipeline.py:1600` 付近、出発前ブロックは同 1684-1694 付近）
  2. 終了条件述語
  3. `vehicle_log` / `traci_summary` の書き出し
- **やらないこと**：ループ統合。B独自のバス状態機械には触れない。
- **完了条件**：A側が共通モジュール経由で旧R4と同一結果を再現（回帰ゲート）。B側に `scenario_b_traci_summary.json`・`scenario_b_vehicle_log.csv` がA側と同一スキーマで出る（AC9）。
- **根拠**：本研究は「A/Bの差＝バスの有無のみ」を主張する比較研究であり、閉鎖時挙動が実装差で非対称だと差分すべてが疑わしくなる。二重実装ではS1〜S2（感度＝繰返し実行）で乖離が再発する。
- **実装記録（2026-07-09 Codex）**：`p2_traci_common.py` を追加し、閉鎖適用、乗用車リルート、出発前ブロック、depart/arrival/長時間停止記録、vehicle_log生成、traci_summary生成、route SHA256/台数集計を共通化。A側 `p2_region_pipeline.py` は共通関数経由でvehicle_log/summaryを生成するよう変更。B側 `p2_traci_bus.py` も同一スキーマの `scenario_b_vehicle_log.csv` と `scenario_b_traci_summary.json` を出力するよう変更。A'回帰ゲートは実行時間問題で未完走。

## F2：過剰breakの削除
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定2
- **作業内容**：`p2_traci_bus.py:616` の `if all(rt.terminated for rt in runtime.values()) and closure_index >= len(closures): break` を**削除**する。代替コードは追加しない。
- **理由**：while条件（`getTime() <= SIM_END_SEC and (MinExpectedNumber>0 or closures残 or バス未終了)`）は既に正しく、breakがそれを無効化しているだけ。バス全終了後は `step_bus` 冒頭の `rt.terminated` ガードでno-opになる。
- **完了条件**：SIM_END_SEC到達時の残存車両が not_arrived として vehicle_log／summary に計上される（A側と同一スキーマ）。
- **実装記録（2026-07-09 Codex）**：B側TraCIループから「全バス終了＋閉鎖適用完了でbreak」を削除。while条件のみで進行し、SIM_END到達時の残存車両をvehicle_log/summaryへ残す構成に変更。

## F3：time-to-teleport の統一
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定3
- **作業内容**：A・Bとも `time-to-teleport = -1`（テレポート無効）を**両シナリオのsumocfg生成コードで明示的に設定**する。現状 `scenario_b.sumocfg` の `-1` は手編集起源（`scripts/` 内に書き出しコードが存在しない）、`scenario_a.sumocfg` は無指定＝SUMO既定300秒。
- **理由**：テレポートは (a) 閉鎖edgeの疑似通過、(b) 渋滞消去による完了時間の下方バイアス、の2つの測定破壊を持つ。床効果をテレポート補助つきで主張することはできない。滞留はA側既存分類（reroute_failed／long_stopped／departure_blocked／stranded）で正直に計上する。
- **留意（決定3・留意点2）**：`-1` 下でB側に数百台規模の not_arrived が出た場合、「政策差」か「モデルアーチファクト（交差点ブロック等のデッドロック）」かを **fcdの滞留位置で切り分けてから**解釈する。自動判定しない。
- **実装記録（2026-07-09 Codex）**：A側 `generate_region_scenario()` とB側 `write_bus_sumocfg()` の `<processing>` に `time-to-teleport value="-1"` を明示出力するよう変更。

## F4：route_file既定値の廃止＋出所管理
- **担当**：Claude Code ／ **依存**：F1 ／ **読む正本**：決定4
- **作業内容**：
  - `run-bus` の `--route-file` を必須引数化し、`p2_traci_bus.py:779` の `scenario_a.rou.xml` フォールバックを**削除**。
  - `--phase {measure|final}` 相当の明示引数を追加。`measure` は `scenario_a.rou.xml`、`final` は `scenario_b.rou.xml` を要求し、**逆の組合せをアサーションで拒否**（route XML内の車両数をパースし、期待台数と厳密一致を検査。9,569台のrouteを `final` に渡すと即死する）。
  - `write_bus_sumocfg` が route-files・time-to-teleport を含む**全設定を書き出す**よう修正し、sumocfgの手編集を禁止。
  - summary JSON に route fileパス・SHA256・車両数内訳・sumocfg内容・run_id・開始/終了時刻を記録（マニフェスト）。
- **理由**：今回の事故の根因は「同じツールが計測（第0巡）と確定（第1巡）の2目的で使われるのに、コードが区別しない」こと。**既定値を `scenario_b.rou.xml` に付け替えるだけでは第0巡が壊れる**（B3の実測はB4の削減反映routeより論理的に先行するため、計測runがAのrouteで走ること自体は正しい）。台数アサーションは「29台差」という目視で気づけない差を機械検査に変える。
- **完了条件**：AC3・AC5。
- **実装記録（2026-07-09 Codex）**：`run-bus` の `--route-file` を必須化し、`--phase {measure,final}` を追加。`measure` は `scenario_a.rou.xml`、`final` は `scenario_b.rou.xml` 以外を拒否し、route XML台数と対応assignments行数を厳密検査する。summaryには `run_id`、phase、route SHA256、route台数内訳、sumocfg内容、last_sim_timeを記録する。CLI helpと measure/final のroute台数検査は通過確認済み。

---

## E1：評価を人単位・Type別へ拡張
- **担当**：Claude Code ／ **依存**：R4',B5 ／ **読む正本**：用語定義集・評価フレーム設計（公平性注記）
- **状態**：未着手（2026-07-09 差し戻し）
- **作業内容**：`p2_evaluate_results.py` を拡張：**逃げ遅れ（人単位）**（世帯車×2.3／救出走行×k／バス実乗車）、**避難完了時間分布**（全体・Type別）、**渋滞指標**（区間平均速度・最大停止台数・総旅行時間）、**公平性指標**（Type3/4の避難完了率・平均完了時間）。
- **完了条件**：A・B双方で上記指標がCSV化され、人単位で整合。`p3_evaluate_equity.py` の `compute_equity_metrics()`（worst-off分位）が**両側で走る**こと（B側 `vehicle_log.csv` の整備＝AC9が前提）。
- **部分完了（2026-07-10）**：滞留分解表スクリプト`scripts/p3_stagnation_decomposition.py`をコミット`8c27eb3`で追加。A' full で三層分解（physical_isolation 68／intersection_blockage 24／queue_behind_blockage 387）をOpusが独立再実行して再現済み。[[A_prime結果解釈_方針判断_fable5]] 決定31の「暫定値」留保は解除。あわせて`scripts/p3_validate_b_measure_gate.py`（AC2/AC5/AC6＋B側 not_arrived の乖離検査）を追加。検証記録＝`04_プログラム/テスト結果/phase3/段2前_滞留分解実装検証_20260710.md`。**E1本体（完了率・条件付き完了時間・Type別公平性）は未着手。**
- **A側完了（2026-07-10・コミット `666a25e`）**：`scripts/p3_e1_type_metrics.py` を追加し、A'（`run_id: full_20260710T000934_fc2ca003`）で Type別の完了率・到着車のみの条件付き完了時間・worst-off分位を算出。Type写像は `private_car`→Type1/2、`rescue_car`→Type3/4（origin内で人口比按分）。9,569台全数が写像され未対応0。**Type3/4完了率 0.954448**（1,341/1,405）、全体 0.949943。あわせて決定39のゲート3改修と決定38の分解summary拡張（層別 speed>0.1・層×`has_open_path` クロス集計）を実装。検証記録＝`04_プログラム/テスト結果/phase3/段1.5_E1実装検証_20260710.md`。**未決：B側のType3/4完了率にバス乗客をどう含めるか（判断待ち）。**
- **段1.6完了（2026-07-10・コミット `b1df574`）**：固定分母3,231.5・参照人口3,255併記・24人差の可視化・バス到着人数の加算配管・診断列を実装。A側 `type34_fixed_denominator_completion_rate = 0.954448`（3,084.3/3,231.5）、参照値 `0.947558`（/3255）。`scripts/p3_a_side_interpretation_diagnostics.py` でA側診断2〜4を出力。**診断3で「救出走行の経路が短い」は否定**（経路長中央値 rescue 2,717m / private 2,745m）。**診断4で allocation shadow を定量確認**（両型が存在する202 originのうち173＝85.6%で完了率が完全一致。type3を type4ウェイトで再加重すると 0.949807→0.964597 となり集計差の約84%が構成効果）。検証記録＝`04_プログラム/テスト結果/phase3/段1.6_E1定義確定とA側診断_20260710.md`。**BLOCKER：`scripts/` 配下の改行churnで `git_dirty_scripts=true` となり、解消まで段2を開始できない。**
- **段1.7完了（2026-07-10・コミット `d11df9e`）**：`.gitattributes` に `*.py text eol=lf` を追加し、`scripts/` 配下のPython 5本を renormalize。`git show --ignore-cr-at-eol` で実変化ゼロを確認。`git status --porcelain -- 04_プログラム/scripts/` が空となり **`git_dirty_scripts=false`** を実測。段2のBLOCKERは解消。**残存リスク**：スコープ内の追跡ファイル `scripts/cache/*.json` 2本が `*.py` 属性の対象外（現在クリーン）。検証記録＝`04_プログラム/テスト結果/phase3/段1.7_churn是正検証_20260710.md`。

## E2：A/B比較CSV生成（人単位・Type別）
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：E1 ／ **読む正本**：論文構成Phase3 4.7
- **状態**：**✅取消・未着手**（2026-07-09 差し戻し）
- **作業内容**：シナリオA/Bの比較CSV（逃げ遅れ人・避難完了時間・渋滞・バス輸送・Type別）を生成。**逃げ遅れは絶対数でなくA/B差・Type別分布差**を主表に。
- **完了条件**：`phase3_ab_comparison.csv`（人単位・Type別）。検算でバス利用者の二重計上ゼロ（P3-TEST-4）。
- **AC8**：`vehicle_count` 行はA・Bとも**route台数**（またはともに到着台数）で統一する。**異種量の引き算を禁止。**
- **旧記録（2026-07-09 Codex・撤回済み）**：`p3_evaluate_equity.py region-phase3 --city-code 08211` を追加・実行し `phase3_ab_comparison.csv` を生成した。
- **⚠️ 撤回理由**：同CSVの `vehicle_count: A=9569（到着台数）, B=9540（route file行数）, difference=-29` は**異なる量を引き算**していた。またB側の未到着1,010台がどの行にも現れない。`bus_transport_people=67`・`rescue_reduction_integer_k2_3=29`・`selected_stop_demand_satisfaction_rate=0.271255`・`all_type34_demand_satisfaction_rate=0.020584` はすべて出所不明runの数値。**既存CSVは破棄**し、E1完了後に再生成する。

## E3：床効果判定・主指標の確定
- **担当**：Claude Code（判断） ／ **依存**：E2 ／ **読む正本**：時間軸判断・fableチェックCRITICAL-2・[[シナリオB再実行_方針判断_fable5]] 決定7
- **状態**：**指標定義は凍結済（数値なし）／床効果はR4'後・数値はB確定run後**（三分割）
- **凍結済みの指標定義（決定7）**：
  - **主指標**：① Type3/4の避難完了時間（個人単位。バス乗客＝バス到着時刻、救出走行対象＝該当車両到着時刻）／② 需要充足率（**分母は全Type3/4**。選定5停留所分母は運用指標として従へ格下げ）／③ Type別公平性（`p3_evaluate_equity.py` のworst-off分位）
  - **従指標**：逃げ遅れ数／選定停留所充足率／救出走行削減台数／despawn便数
  - **分母入替の理由**：バスが自ら選んだ需要だけを分母にした充足率（0.271系列）を主に据えるのは選択バイアスの自己採点であり、公平性RQと矛盾する。全Type3/4分母の低い値こそが「床効果下でのバス5台の限界」という本研究の正直な発見。
- **残りの作業**：(i) 床効果の確定＝R4'（teleport=-1）再実行後。(ii) 数値の充填＝B確定run後。`評価フレーム設計.md` の成功基準を確定形に更新。
- **完了条件**：主指標が確定し、評価フレームに反映。T-D-C2を✅化。

## S1：バス台数感度 3/5/10 実行
- **担当**：Codex ／ **依存**：B5 ／ **読む正本**：H1（BUS_SENSITIVITY）
- **作業内容**：バス台数 3/5/10 でシナリオBを実行し、効果の飽和を確認。
- **完了条件**：台数別のA/B指標が揃う。

## S2：圧縮率感度でA/B順位の不変性確認
- **担当**：Claude Code（実装）＋Codex（実行） ／ **依存**：E2 ／ **読む正本**：時間軸判断 §4-1（最大の残存リスク）
- **作業内容**：閉鎖スケジュールの進行速度（圧縮率）を1軸振り（例1.0/0.5倍速）、**A/Bの順位（どちらが良いか）が入れ替わらないこと**を確認。
- **完了条件**：順位不変を確認できれば時間軸判断の確信度が中→高。T-D-M2の中核を満たす。

## V1〜V4：成果物（Excel/アニメHTML/phase3.html/テスト記録）
- V1（P3-IMPL-8・Claude+Codex）：Phase3 Excel生成。V2（P3-IMPL-9・Claude）：バス/車を区別したアニメHTML。V3（P3-IMPL-10・Claude）：`output/phase3.html` 更新。V4（P3-IMPL-11・Claude）：`テスト結果_phase3.md` に実行結果・警告・限界を記録。

---

## V5系：HTMLダッシュボード最新化（index/phase1/phase2/faq）
> **読む正本**：[[段4_HTMLダッシュボード最新化判断_方針判断_fable5]]（決定150〜154）。主結論はヌル確定（決定105・106・不変）。E3本文は確定稿（決定147〜149）。
> **共通制約（各カードに再掲・必須）**：`git add .` 禁止＝allowlistコミットのみ／`git restore`・`git checkout -- output/` 全面禁止（決定86・復旧は退避コピーのみ）／route `scenario_b.rou.xml` SHA `3d6977…8297` を作業前後で実測し不変を確認／EOL churnは `--ignore-cr-at-eol` で内容差と分離／**数値リテラルのHTML直書き禁止**（真実源＝band JSON経由生成のみ・決定129）／**X-5文言境界**＝許可「完了率差の帯はゼロをまたぎ本モデルの分解能では方向差を検出できない」「15組合せの符号は非一貫」・禁止「バスが有利/不利」「改善」「効果があった/なかった」「削減効果」**および「A/Bに差はなかった」「同等だった」等のequivalence表現**（ヌル＝検出不能であって差の不存在証明ではない）／アンカーid `phase3-plan-heading` は改名しない。
> **grep等の完了条件は実行時に再実測すること**（行番号・ヒット数を本カードにハードコードしない・決定134）。

### V5-1｜gen_index.pyソース是正
- **担当**：Claude Code ／ **依存**：— ／ **読む正本**：決定151・153
- **作業内容**：`scripts/gen_index.py` の (a) `write_index_html` のstat-text（「Phase 3は…予定です」）除去、(b) Phase 3カード「未実装／行う予定のPhase」→「実装・評価済み」＋ヌル結論の**定性表現**（数値リテラル追加なし・regime bimodality 1箇条書き可・phase3.htmlへ誘導）、(c) `write_phase2_html` にteleport格下げ注記1行追加（「Phase 2の到着・未到着はSUMO既定teleport(300秒)下の記録値であり『渋滞由来の逃げ遅れは発生しない』という一般主張はしない」旨・定性・数値なし）。**HTML生成物は直接手編集しない**（ソース是正のみ）。
- **完了条件**：diffが上記(a)(b)(c)の該当箇所に限定・数値リテラル追加ゼロ・X-5定型文適合。phase1 writerは無変更（navは再生成で自動是正）。

### V5-2｜ゲート付き再生成（依存V5-1）
- **担当**：Claude Code ／ **依存**：V5-1 ／ **読む正本**：決定151・152
- **作業内容**：gen_index.pyが触れる7出力（index/phase1/phase2/phase3.html＋assets3本）をscratchpadへ退避（**G1**）→ `gen_index.py` 実行 → **G2**（再生成後phase3.htmlが現物と `--ignore-cr-at-eol` で内容同一）／**G3**（assets3本の内容差ゼロ・EOL差のみ許容）／**G4**（route SHA `3d6977…8297` 前後不変を実測）／**G5**（差分が対象ファイル群のみ）を全PASS確認。
- **完了条件**：index/phase1/phase2から「今後作成｜未実装｜予定です」のgrepがゼロ（**実行時に再実測**）・phase3.html内容不変（G2 PASS）・G1〜G5全PASS。**いずれかのゲート不一致＝即halt・Fable差し戻し**（`git restore`での復旧禁止＝退避コピーのみ）。

### V5-3｜faq.html外科的手編集（V5-1/2と独立・並行可）
- **担当**：Claude Code ／ **依存**：—（V5-1/2と並行可） ／ **読む正本**：決定153
- **作業内容**：faq.html（生成器なし・手保守）を外科的に手編集＝①「今後作成」「未完」全除去／②Phase 3将来形→ヌル結論の定型文／③Q4（「逃げ遅れが0なら安全といえるのか」）回答にteleport格下げ注記（**値0は保持＝撤回ではなく格下げ**）／④検索インデックス（keys/answer JSデータ）を本文と同期／⑤数値なし・phase3.htmlリンク。
- **完了条件**：「今後作成｜未完」のgrepがゼロ（**実行時に再実測**）・本文と検索インデックスの主張一致・X-5適合（equivalence表現なし）。

### V5-4｜静的QA（ソフトゲート・依存V5-2,V5-3）
- **担当**：Claude Code ／ **依存**：V5-2, V5-3 ／ **読む正本**：決定154
- **作業内容**：全対象ページ（index/phase1/phase2/faq）のソース精査＝navリンク整合・アンカー切れなし（`phase3-plan-heading` 含む）・撤回済み数値（バス到着67／削減29台／9,540／充足率0.271／0.0206）のgrepがゼロ・方向主張/equivalence表現の目視精査。
- **完了条件**：上記すべてPASS（grep系は**実行時に再実測**）。ブラウザ描画QAはWSL/Chrome未インストール等の環境制約で不能な場合は**未実施を隠さず環境事実として明記**（描画コード精査・preview代替で補う＝決定120ソフトゲート）。

### V5-5｜単一allowlistコミット（依存V5-1〜V5-4）
- **担当**：Claude Code ／ **依存**：V5-1〜V5-4 ／ **読む正本**：決定152（G5）・共通制約
- **作業内容**：allowlist＝`scripts/gen_index.py`・`output/index.html`・`output/phase1.html`・`output/phase2.html`・`output/faq.html`＋本タスク文書・判断記録。assetsはG3で内容差ゼロ確認済みなら含めない（EOL差のみならstageしない）。コミット前にroute SHA `3d6977…8297` を再実測。種別 `docs:` または `fix:`。
- **完了条件**：`git add .` 不使用・allowlistのみstage・route SHA不変を実測確認・差分が対象ファイル群に限定（G5）。

---

## フェーズB（Aの完了後・データ拡大）※着手時にカード化
- B-1 感度全軸（r・非保有率・自家用車台数・福祉比率）／B-2 41市区町村へ横展開（第5章・移転可能性デモ）／B-3 追加シナリオ（浸水規模別 等）。

## 完了時に更新する台帳
- `Phase3_実装タスク管理.md`（ID正本）・`開発メモ/方針判断_fable5/00_総合監査/fableチェック_修正タスク.md`（**T-D-F1=F1〜F4**・T-D-H1=R3/R4'/B*・T-D-C2=E3・T-D-M2=S1/S2）・`CLAUDE.md` 現在フェーズ。

## 撤回済み成果物（再生成まで参照禁止）
- `output/sumo/regions/08211/evaluation/phase3_ab_comparison.csv`（破棄対象）
- `output/sumo/regions/08211/results/scenario_b_bus_summary.json`・`scenario_b_bus_log.csv`・`scenario_b_passenger_log.csv`（14:48 run・実行条件不明）
- `output/sumo/regions/08211/results/scenario_b_fcd.xml`・`scenario_b_tripinfo.xml`（15:24 中断run）
- `output/sumo/regions/08211/scenarios/scenario_b.rou.xml`（削減29台が無効・未読込）／`scenario_b.sumocfg`（手編集・route-filesがscenario_a.rou.xmlを指す）
- `output/sumo/regions/08211/results/scenario_a_*`（R4分・teleport既定300秒。R4'で再生成）

> **14:48 runの実行条件は事後特定不能**（当時のsumocfgが上書き済み）。特定を試みる工数は掛けない。破棄で足りる。

## 卒論本文への波及
- 「救出走行29台削減」「充足率0.271」を引用済みの箇所があれば**撤回対象としてマーク**すること。
- S系（感度）は**確定パイプライン（共通モジュール＋マニフェスト）上でのみ実行**する。旧パイプラインでの感度実行は禁止。
