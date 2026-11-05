# Native selected pair — 実行入口と入力来歴の再結合

更新時点：2026-10-20T17:34:50.418519+09:00

selected-pair helperは新primary proofへ接続済み。31隔離契約試験と起動前差分レビュー、Python-onlyの実CIM/handle試験を完了した。試験/レビューの現行source SHAを再照合した。これはnativeの物理合格や研究READYではない。

## 入口の検証範囲

- control/patchedの原本pair/policy/stateと両EXEを一次証拠から照合する。
- 設定/common5/共有runtime/helper/両bundle/原本source・headerを起動前後に凍結照合する。
- 単一owner・実PID作成時刻/command/parentとPopen終了handleを保存し、timeoutだけで再起動しない。
- calibrationはcase PASSと独立fixture validate PASSを必要とする。control repeatedの生receiptがold_remainingでXYだけ不連続の場合だけ予定した再現と分類する。変位の期待値を固定しない。
- patchedの両caseは原CSV/receipt・歩行budget再帰・全出力SHA・独立validateを満たす。両版の物理入力も同一を要する。

証跡：`audit_history/native_selected_helper_20261020/prelaunch_review_v2.json`、`final_unit04.log`、`process_probe_20261020T171240526024/state.json`。前版helperは同所`choice_native_regression.py.before.bin`へ保全。

## 初回の停止：nc261020a / np261020a

初回はFAILED_PRESERVED。control fixtureが`load_inputs()`で設定SHA不一致を検出し、SUMO実行manifest作成前に終了した。親のmanifest FileNotFoundErrorはこの早期停止の二次症状。対照版nativeの予定した物理失敗は未観測であり、patchedも開始していない。元state/原stderr/run01.logと部分fixtureを保全し、IDを再利用しない。

registered02が保持する旧設定を、現行設定のrecord_filesを旧6件へ戻した候補CRLF bytesから再構成したところ、旧manifestのSHAと完全一致した。差は記録先移転とJSON EOLであり研究値変更ではない。入力生成器も旧run保存原本SHAを確認し、差は共通SUMO discoveryからchoice隔離toolchain接続への2行のみ。SHAゲートは正しく拒否しており、旧manifestを手動更新して通さない。

## 新規registered03

設定のinput_directoryだけを変更し、Registryへ技術再結合を追記した。現行入力生成器とcontrol bundleの同じPython toolsで排他生成。registered02の全20artifactと集合・バイトSHAが一致し、人物・施設・終点・経路・位置・需要マスク・seed・時刻・物理netに変更がない。独立入力28項目PASS、source SHAもすべて現行。旧registered01/02と全旧runを保全した。

旧版、設定再構成、実command失敗（最初のshell相対Pythonパス誤り・generator未起動）と訂正、全artifact比較/28検証の原本は`audit_history/input_refresh_registered03_20261020/`。設定/EOLの旧版を戻したのではなく、旧SHAの説明のためだけに再構成した。

## 現在の次の1件

新ID nc261020b / np261020bで同じselected pairを開始した。owner launcher26036 / executor24548、17:33:17 JST生成を実CIMで確認。session38383を継続監視し、constructorの一次証拠照合から同一workflowを待つ。完了/失敗と物理結果は後続の一次stateで確定する。初回の停止から現在までの無観測区間を連続監視扱いにしない。

native broad guards（同/逆方向、複数人、明示/random/legacy、新規出発/自然境界/非対象と実native trace）、全現行suite/反例監査/14smoke/新preflight/G6は未完。正式0/70、READY=falseを維持する。親の実モデル切替なし、実backend未確認。新agent・公開・外部送信なし。


## 2026-10-20T21:43:44.488770+09:00 — b停止の原因と現行c試行

最新HOLD（2026-10-20T21:43:44.488770+09:00）：goal ACTIVE。choice正式0/70・研究core稼働0・READY=false。registered03は旧20入力artifact全バイト一致・独立入力28検査済み。比較bで対照のXY不連続を再現したが、custom版名の識別不足により校正独立INVALIDを保全。版名と現行固定bundle来歴の照合を修正し18試験PASS、保存raw7成分の履歴再計算合格・原本不変。新nc261020c/np261020cを21:41:56 JST開始、同一owner/handleを監視中。修正版物理結果・広いnative guard・全suite/audit/14smoke/preflight/G6未完、core開始禁止。

対照calibrationの速度契約INVALIDは`unsupported_native_getter_version`、nativeログINVALIDはmovement不合格によるWarning分類の二次拒否。旧version regexは1.26.0の空白/plus終端だけを認識し、隔離build custom suffixを未対応とした。修正は現在のruntime fingerprint全体の一致、controlled native_provenanceのSHAとexact custom version、role/source commit/terminal build版の結合のみ。既存の位置・budget・速度・Warning multiset条件は変更していない。source/base/patchの正しさをこの識別から推定せず、P1/広いnative回帰の独立ゲートを維持する。RED→18試験GREEN、raw全ファイル不変・7成分の歴史診断INCOMPLETEを記録し、旧INVALIDを上書きしない。詳細は`audit_history/native_version_identity_20261020/`。新c試行のsession34648/owner13420/launcher28208と同じ実行を確認する。


## 2026-10-20T21:56:07.793370+09:00 — 既存独立監視を使用

最新HOLD（2026-10-20T21:56:07.793370+09:00）：goal ACTIVE。正式0/70・研究core0・READY=false。新c対照校正は独立7成分PASS、対照反復では予定したXY不連続を再現。修正版np261020cの校正/反復2caseは完走・case PASS、独立validate/SHA比較を同一session34648で実行中。既存Windows独立監視PID25168・source一致・新しい観測を確認し受信箱を使用。case/suite ID差のPID照合警告を原イベント付きで調査。県検証入口はlive GETでも臨時ページへ転送、需要/旅客供給実績は未補完。広いnative guard/全suite/audit/14smoke/preflight/G6未完、core開始禁止。

受信箱は軽量イベント検出の入口とし、公式PASS/原本SHA会計を代替しない。control calibrationの現行validateはstdoutと保存報告の完全一致・7成分PASSを確認した。修正版case_validationの完走だけでselected pair合格を主張しない。監視sourceは未変更、元の警告/通知/診断失敗も維持。G1の3query/県live取得/二次locator監査は研究入力未採用。

## 2026-10-20T22:05:33.397367+09:00 — 選定比較cの終端と独立監視使用

最新HOLD（2026-10-20T22:05:33.397367+09:00）：goal ACTIVE。正式0/70・研究core0・READY=false。nc261020c/np261020c比較はFAILED_PRESERVED。修正版の位置連続8receiptは一致し2case完走したが、反復caseの独立検証で2人の旧計画長とnative可変stage長の照合が不合格。原本・INVALID保全、正式採用/後続開始停止。差の原因はnative内部距離の分岐を調査中で、検証条件の変更未実施。独立監視PID25168は22:04 JSTに同一性・直近観測を確認、受信箱を使用。suite/case ID照合警告は未修正。広いnative guard/全suite/audit/14smoke/preflight/G6未完、core開始禁止。

一次診断：`audit_history/native_pair_c_receipt_diagnosis_20261020/diagnosis.json`。4回の置換・8receiptを全件照合。52.5秒の2人でnative live長−cached計画長は双方−7.33044236321706m。位置/edge/longitudinal/XYは一致。C++ getStage.length→getDistance→walkDistanceが内部距離の蓄積状態で分岐する事実を確認したが、この数値差の独立再構成は未完了。in-memory代入で偽predicateを切り分けたのみで、原本/式/検証条件を修正していない。比較workflow exit1、owner PID13420/launcher28208は現CIMで不在。校正2roleは独立PASS、反復修正版はINVALID。次の試行や研究coreは開始しない。


## 2026-10-20T22:14:04.149922+09:00 — 新d比較の開始

最新HOLD（2026-10-20T22:14:04.149922+09:00）：goal ACTIVE。正式0/70・研究core0・READY=false。旧c比較はFAILED_PRESERVED。距離差をnative形状から2人とも数値再構成し、検証器のlive長と固定計画長の誤った同一視を訂正。20試験PASS・旧raw7成分の履歴再計算、原本/INVALID保全。新nc261020d/np261020dを22:12:28 JST起動し同一executor PID29460/launcher28704・session16184を観測。初期provenance照合中で実fixture開始は未確認。広いnative guard/全suite/audit/14smoke/preflight/G6未完、core開始禁止。独立監視を使用、suite/case ID警告は未修正。

詳細：native_live_length_数値再構成・修正_20261020.md。初期13,003件のprovenance再照合中はsuite manifestが未作成でも実owner同定で待つ。タイムアウトのみで再起動しない。

## 2026-10-20T22:30:44.499288+09:00 — 比較dは最後のinventoryゲートで停止保全

最新HOLD（2026-10-20T22:30:44.499288+09:00）：goal ACTIVE。正式0/70・研究core0・READY=false。d比較の対照校正と修正版2caseは独立全7成分PASS、対照反復は予定したXY不連続を再現。最終input比較helperの14番目toolchain receiptの一覧漏れでFAILED_PRESERVED。原本不変、helperを各role固定bundleへ完全照合するよう修正し33試験・実4入力SHA/2case物理比較を確認。旧dは昇格せず、現行版の新ID比較が必要。独立監視PID25168は生存・同一性一致、suite/case警告の修正は未実施。次は監視の狭い照合修正後に新比較。native trace13群の契約/7source経路確認済みだが未実装。広いnative guard/全suite/audit/14smoke/preflight/G6未完、core開始禁止。

4caseの全14artifact SHAに不一致なし。相違はbounded.net.xmlのcomment metadataと各roleのtoolchain_runtime.jsonだけ。canonical netと物理/条件表は同一。runtime receipt全辞書を固定selected bundleのbinary/manifest/files/roles/provenance/shared-sourceから再導出し、別role・誤SHA・余剰key・欠損を拒否。RED/GREEN33/差分/実原本154ファイル不変/レビューはaudit_history/native_pair_inventory_20261020。raw比較は診断であり、元dの失敗statusをPASSへ書き換えていない。新しいworkflowで受入を確認する。

次段native traceはaudit_history/native_guard_trace_contract_20261020に13群・7native source SHAを固定。XML walkのdepartPosLatを使う必要があり、person.addへ存在しない引数を渡さない。実装/compile/branch実測は未実施。


## 2026-10-20T22:42:37.955366+09:00 — 監視修正後の新e比較

最新HOLD（2026-10-20T22:42:37.955366+09:00）：goal ACTIVE。正式0/70・研究core0・READY=false。独立監視のsuite/case対応・exact argv・初回未確認cache・照合中終了/PID再利用を修正。27試験/人工Windows daemon確認、旧24イベント/配送履歴保全。既存タスクだけ再起動しPID29296・読込source一致を確認。修正済みinput比較helperで新nc261020e/np261020eを22:41:07 JST開始、同一executor22048/launcher30140・session18767の来歴照合を観測。旧dは物理/独立PASSだがinventory gate FAILED保全。native trace13群は契約/入力経路確認のみ。広いnative guard/全suite/audit/14smoke/preflight/G6未完、core開始禁止。

27試験/レビュー/旧版と実稼働確認は07_監視システム/verification/command_binding_20261020/。新e ownerは前処理のI/Oを進めており、現時点ではsuite manifest生成/実SUMO開始を未確認。15分監視は同じPID/handleから続け、タイムアウトで再実行しない。


## 2026-10-21T07:58:12.766443+09:00 — fの完了再照合・traceの準備

最新HOLD（2026-10-21T07:58:12.766443+09:00）：goal ACTIVE。正式記録0/70・研究core稼働0・READY=false。選択比較nc261020f/np261020fは正常終了、3独立報告7成分PASS・2物理入力一致・全13,682 binding再照合差異0。反復の4 reroute/8位置receiptを一次証跡から再計算。広いnative guardは未完。観測専用trace挿入helperは6試験と実g++構文検証PASS、未適用で診断binaryは未作成。独立監視PID30168の同一性/直近観測を確認。PC睡眠中の観測空白は補作せず、旧失敗/INVALIDを保全。次は別source/build/SHAの隔離診断build、13群traceとproduction回帰、全suite/audit/14smoke/input-unit/preflight/G6。core開始禁止。

詳細：[確認と準備](native_f確認・trace準備_20261021.md)。静的6試験と構文検証を実native guard合格へ転用しない。
