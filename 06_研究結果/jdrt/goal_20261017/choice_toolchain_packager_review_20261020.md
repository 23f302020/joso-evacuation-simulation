# Choice toolchain packager 対象差分レビュー — 2026-10-20

判定：要修正。実bundle生成・採用、研究READY、core開始は確認していない。起動指定は `gpt-6.1-sol` / `high`、実バックエンドは未確認。実装修正は担当へ引継ぎ、本レビューは実装・ビルド・packaging・SUMO・正本更新を行っていない。

## 対象と版

- `.agents/skills/joso-jdrt-runner/scripts/choice_package_toolchain.py` SHA-256 `834f7d28db6e71fba03133490cf5adceeca5721cb21a2d9e2343f5f23bb4b55d`
- `04_プログラム/scripts/jdrt_choice_toolchain.py` SHA-256 `97cd450b34d1804ecc3c7ca4b894d5125cebf00bca8ae8662dc326a5756b24f2`
- 参照試験 `04_プログラム/tests/test_choice_package_toolchain.py` SHA-256 `42a2ddda5d0b50de1261ad749eb5519a0eb922640be6fb4662976db589052320`

AGENTS、code-review-and-quality、joso-jdrt-runnerとrealtime_choice参照、binding報告末尾のpackager報告、対象source/testsを静的確認した。想定された独立 `choice_toolchain_packager_20261020.md` は存在せず、報告は `choice_toolchain_binding_20261020.md` 末尾にある。既存25 tests/27 subtests PASSは実nativeの物理証拠として扱っていない。無関係dirty差分は変更していない。

## 修正が必要な指摘

### P1：patch・対照比較の客観証拠と選択EXEを拘束しない

対象：packager **136–145行**、関連 **178–203行**。

`role=patched` では `patch_applied_sha256` が64桁hexであれば通り、patch実体もsource比較もpaired compiler/dependency/flags比較も必須ではない。`role=control` でも `source_comparison` のtruthinessと比較booleanだけを検査し、比較対象のcontrol/patched両方のEXE SHA、両方のcompiler/dependency/config/flags/link内容、実source差分との対応を再計算しない。`proof.files` はbasename集合とfile SHAを照合するが、それらが当該buildとpaired comparisonの実内容に対応するとは照合しない。例えば正しいファイルハッシュを持つ不一致compiler設定を置いても、comparisonのTrueを据え置けば該当guardを通過する。

実害：patchedの宣言だけでcontrol executableや未適用patchを包む、または異なるflags/dependencyの対照を「同条件」とするbundleを生成できる。後段resolverは生成済みmanifestのbytesを固定するため、この対応不足を発見しない。packagingがREADYを付与しない点とは別に、機械受入の比較証拠が不足する。

確認方法：既存試験 **206–218行**は `source_comparison={'mock_unpatched_source': True}` とbooleanだけでcontrol成功を期待し、この不足を直接示す。修正時は両roleでpaired proofを必須にし、対になる2 EXEずつのSHAと各build metadataの参照・SHA・正規化内容を照合する。patch実体SHAと登録差分、source-tree差分を拘束し、比較artifact欠落、相手EXE差替え、compiler/dependency/flags/linkの片側変更、patch欠落/不一致を個別に拒否する反例が必要。nativeの物理成立は別途build担当が検証する。

### P2：成功combined build後の失敗commandを無視する

対象：packager **132–135行**、**234–239行**。

`state.commands` からsumo/netconvert両targetを同時指定したcommandだけを抽出し、その最後のexit codeだけを検査する。後続の `cmake --build ... --target sumo` / version / configure等がexit非zeroでも、terminal statusとbinary/version各フィールドが以前の成功値なら通る。後段は全commandのlogを複製するだけで失敗を拒否しない。

実害：最後の作業が失敗している不整合provenanceを、成功build由来bundleとして生成できる。

確認方法：既存の成功fixtureにログ付きの後続単独target `exit_code=1`、またはversion `exit_code=1` を追記し、terminal statusを据え置いた反例を追加する。古い成功を候補とする場合は、失敗attemptを独立保全し、受理するattemptの終端・command集合・EXE/version対応を明示する必要がある。本レビューではpackaging禁止のため実行していない。

### P2：build logは同サイズ改変を検出できない場合がある

対象：packager **234–242行**、関連 **256–257行**。

command logは `log_bytes` とのサイズ一致だけを確認し、観測時SHAとの一致を確認しない。`proof.files` や他のhash付き参照にも入っていないcommand logでは、同サイズの改変後bytesを240行で初めて正当なコピー元SHAとして採用する。前後の `validated` 再照合にもそのlogは追加されない。

実害：build観測原本の同サイズ書換えを成功として包み、元の観測証拠との連続性を失う。bundle生成後のSHA固定では過去の改変を検出できない。

確認方法：hash付き `proof.files` にないcommand logへ、長さを保った内容変更を与える反例を追加する。各command logに観測時SHAを必須とし `track` へ通す、またはhash付きproof参照に全command logが含まれることを必須にしてコピー前後に再検査する。

## 確認した保全・残る限界

コピー前/後のsource/proof SHA再照合、新destination限定、失敗後 `FAILED.json` とpartial filesの保全、既存destination再使用拒否は実装されている。resolverは全bundle file集合/SHA、実traci/sumolib module path、manifest/selection再一致を確認する。これらの経路について本対象静的確認で新たな要修正は特定していない。

実bundleは未生成、実version/PE imports/loader、patch成立、paired native回帰は未確認。fresh-process import verificationも実bundleでは行っていない。修正後の再レビューと、実buildの客観証拠確認を完了するまで採用判断へ使用しない。
