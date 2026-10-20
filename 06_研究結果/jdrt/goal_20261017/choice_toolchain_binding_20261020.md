# Choice隔離toolchain binding — 2026-10-20

choice専用のprocess-local manifest選択とSHA拘束を実装した。これはtechnical bindingの検証であり、実toolchainの採用、native patch成功、技術READY、正式セル実行を示さない。実manifestは作成していない。研究core・native simulationは起動していない。正式0/70・READY=falseを維持する。指定モデルと実バックエンドは別であり、本担当の実バックエンドは確認できていない。

## 対象と変更理由

共有`jdrt/smoke.py`のresolverはPATH等の既存インストールを探索する。変更前のchoice実行器・検証器・fixture/probe・入力helperもその探索を使用し、fixture/probeのnetconvertはSUMOと同じ親フォルダを仮定していた。隔離control/patchを明示選択する必要があるため、新`jdrt_choice_toolchain.py`へchoiceだけを接続した。共有resolver、旧系列、`step_bus`、PAP、研究入力、既存runは変更していない。

`JDRT_CHOICE_TOOLCHAIN_MANIFEST`は呼出しprocessから継承する選択子である。OSの永続環境設定、PATH、SUMO_HOMEは書き換えない。control/patchを別processの別manifestで選べる。selectorが存在しない場合のみ、技術試験互換のため従来の探索を許す。空値・欠落file・不正schema・SHA不一致ではfallbackしない。coreのrun作成前とREADY preflight冒頭では明示manifestを必須とする。既存READYのschema拒否順序は維持した。

## 実manifestの仕様（実例・架空binarymanifestは未作成）

manifestは専用runtime bundleの直下に置く。JSONの重複keyを拒否する。

| key | 内容 |
|---|---|
| `schema_version` | 整数1 |
| `files` | bundle rootからの正規POSIX相対path → lowercase SHA-256。manifest自身以外の全fileを列挙する |
| `roles` | `sumo`、`netconvert`、`traci_init`、`sumolib_init`の4役割 → `files`内path |
| `provenance` | 非空object。公式base/source、patch、compiler/flags、依存の出典・build proof参照を記録する |

traci/sumolib役割は同じtools directory内の各packageの`__init__.py`を指定する。全Python source・controlled依存DLL・source/build/dependency proof等を同bundleへ含める。resolverは全fileをハッシュし、未列挙file、欠落file、traversal、絶対path、非正規path、symlink、Python bytecode（`.pyc`/`.pyo`）を拒否する。実DLLの配置と依存closureの正しさはbuild/import証拠で別途確認する。

明示選択では、実際の`traci`/`sumolib`および読込済みsubmoduleの`__file__`と現在bytesをbundle inventoryへ照合する。別インストールのmodule cacheや、選択roleとは違うpackage初期化fileは拒否し、暗黙差替えしない。Pythonのbytecode書込みはそのprocess内で抑制し、後のlazy importもbundleを変えない。

## 指紋と受入ゲート

既存runtime keyに加え、専用helper自身SHA、manifest SHA/path、全bundle file SHA、役割path、出典object、実sumo/netconvert pathを記録する。manifestは毎回再読込し、解決後のmanifest・role・出典改変も拒否する。fixture入力成果物の`toolchain_runtime.json`とprobe manifestにもruntime指紋を保存する。

coreのarchived READY、現在runtime、run manifestの既存等値比較を維持した。検証器のREADY metadata検査はmanifest SHAを持たない旧runtimeを拒否する。preflightの必須unitへ新toolchain moduleのテストを追加した。common-fiveのうち実行器・入力helper・検証器・専用CLIの4fileが変化し、policyは不変。完全な旧/新SHAは下記JSONから読み取る。新helperはcommon-fiveへ追加せず、全receiptのruntime fingerprintで拘束する。

旧suite、counterexample、14smoke、READY、G6 source proofは現行版の証拠として再利用できない。native回帰/build proof後にsource/toolchainをfreezeし、新suite・独立audit・14smoke・unit/input・新preflight・G6再監査が必要である。

## 検証

最終確認は**84 unit PASS**（toolchain15 + 既存choice69、16.276秒、exit0）。テストは一時file・synthetic moduleとmockを使い、native processを起動しない。既存choice suiteのprocess生存確認はPythonの試験childである。

検査した内容：exact役割選択、netconvert別directory、legacy未指定技術互換、core/READY未指定拒否、空/欠落/不正manifest拒否、path traversal、binary/controlled DLL/Python source/出典fileの改変拒否、未列挙file/bytecode拒否、重複JSON key拒否、別module cache拒否、選択package roleとの一致、初回/lazy import後のfingerprint一致・pyc無生成、manifest出典/role改変による旧選択拒否、helper source SHAの変化、mock factoryで実役割のnetconvert commandを確認した。

途中の82テスト確認で、coreの新manifest検査が既存READY schema拒否より先に走り、既存の2テストが想定外例外になった。検査をREADY schemaの直後かつrun作成前へ移し、83テストで解消を確認した。schema versionの整数型検査を追加した最終84テストもPASSした。受入条件は緩めていない。

対象PythonのAST parse、差分、末尾空白を確認した。新しい末尾空白なし。`git diff --no-index --check`はsourceがuntrackedであるため保存した旧sourceと比較した。exit1は差分存在によるもので、whitespace errorはない。CRLF→LF注意は既存CRLF fileの両側へ表示されており、line-endingの一括変換は行っていない。

## 証拠と限界

- [変更前source・旧SHA](audit_history/choice_toolchain_binding_20261020/before_sha256.json)
- [最終SHA・common-five比較・差分check](audit_history/choice_toolchain_binding_20261020/after_sha256_and_checks.json)
- [正規化した対象差分](audit_history/choice_toolchain_binding_20261020/changes.patch)
- [最終unit結果](audit_history/choice_toolchain_binding_20261020/unit_result.json)

このresolverは、提供されたbundleの全bytesと実Python moduleの選択を拘束する。WindowsのOS DLLや外部動的DLLの実ロード先を列挙せず、PE import closureを証明しない。build担当のimport/dependency proofで非OS依存が隔離bundleへ適切に同梱され、control/patchが同じ依存・flagsを用いることを確認する。provenance objectの存在は、その記載事実の独立確認を代替しない。実binary/version、native guard成立、native位置/距離/速度回帰は未検証であり、この実装だけでREADYへ進めない。

## 再利用packager追加（2026-10-20）

control/patchedの2種を同じ手順で隔離するため、既存スキルへ`choice_package_toolchain.py`を追加した。resolver/common-five、研究入力、既存run、global SUMO、実build状態はこの担当では変更していない。正式0/70・READY=falseを維持し、実bundleは作成・採用していない。起動指定は`gpt-6.1-sol`/`high`、実バックエンドは未確認として区別する。

新destinationは`04_プログラム/output/sumo/toolchains/`下に限り、既存file/directoryへの書込みを拒否する。precheckでsource/proof不足・不一致ならdestinationを作らない。作成後にcopy/SHA/列挙検査が失敗した場合は`FAILED.json`とpartial bytesを保存し、同じdestinationの再利用を拒否する。完了manifestは既存resolverのexact schema 1に従い、自身以外の全filesと四役割、非空provenanceを記録する。

入力proofはbuilderの`isolated_native_provenance_v1`を原文bytesのまま収集する。最新の両target build exit0、各exe実SHA/size、custom-version log SHA・exit0、PE import tableと申告importsの一致を要求する。Python標準ライブラリでPEを直接読取り、非OS DLLとdelay importを拒否するstatic依存限定のpackagerである。明示OS DLL名の判定は実OS loader pathの証明を代替しない。source commitは公式Python tools inventoryへ拘束し、traci/sumolib全bytesとlicenseの完全性を再照合する。compiler/config/source ZIP/Xerces/zlib等の提供file参照もSHAを再計算し、copy途中のsource/proof改変を拒否する。

manifest内のprovenanceは公式inventory/native proofへの参照とrole/source commit/非OS runtime DLL 0を記す。元JSONの絶対pathを改稿せず、copyしたmetadata/config/build/version logと追加`--evidence`を全SHA列挙する。compiler exe・static archive・公式source ZIP本体はbundleへ複製せず、照合済み参照として残す。元ZIPを展開せずtraci/sumolibとlicenseの全member bytes・集合を独立再計算し、inventoryの記載だけに依存しない。native proofとinventoryのsource commitも等値必須とした。追加patch/source/dependency/license証拠は`--evidence`で明示添付する。proof存在やmock test PASSを実build成功とみなさず、実exe/version/source/patch/compiler/depsの採用判断は親担当の確認後に別Gateで行う。

`--verify-manifest`はfresh processで2回のresolve→実traci/sumolib import→runtime fingerprintを行い、指紋・実module path・全inventory不変を照合する。SUMO simulationは実行せず、bundleへfileを生成しない。実bundle採用後はmonitor/status/check/fixture/validate/preflightにも同一process selectorを渡す。selector省略による旧installed runtimeへの復帰を避け、path/SHAを現在地・automationへ登録する作業は親担当へ引き継ぐ。

対象検証は人工PE、temporary Python packages、明示mock proofだけを用いた。既存resolver15 testsと新packager10 testsの計25 PASS、27 subtests PASS（27.25秒・exit0）。上書き・研究run destination・source欠落/改変/余剰・bytecode・binarySHA/PE imports/失敗version・非terminal build・control比較不足・copy途中失敗/元proof改変・inventoryと異なる元ZIPmemberを拒否し、FAILED保全、全files完全列挙、元JSON一致、2回の実Python import/fingerprintとpyc無生成、freeze後の余剰file/改変拒否を確認した。研究unit全体やnative simulationは実行していない。

最初のREDはpackager未実装による5 failures。追加統合テストの初回root呼出しは既存testの`from scripts`探索設定不足でcollection errorとなったため、既存慣例に合わせ`04_プログラム`をcwdとして実行し解消した。コードを探索エラーの回避目的で変更していない。最終の対象結果・SHA・差分検査は[audit保存先](audit_history/choice_toolchain_packager_20261020/)を参照する。変更前ref/report原文とSHAを同所へ保全した。

同じchat内で`code-review-and-quality`の五観点を確認した。対象は新packager/testsとpackager手順追記に限定した。独立再計算は実fileSHA、PE import table、bundle全file集合、実Python module path/指紋で行い、別モデルの追認は用いていない。実native correctness・実loader依存元・研究READYは未検証であり、この変更から開始権限を推定しない。
