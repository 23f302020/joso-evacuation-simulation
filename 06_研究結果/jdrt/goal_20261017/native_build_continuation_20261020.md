# 隔離native buildの引継ぎ・限定修正

2026-10-20。前goal作業は進行あり：実状態を再観測し、生成物固定helperの拒否漏れを再現・修正し、隔離ビルドを新attemptで進めた。最終goalはACTIVE、正式0/70、READY=false。研究core・技術SUMO simulation・bundle生成・採用・公開更新は実施していない。

## 実観測と原因

- a06は08:44:16にsumo/netconvert両target compileがexit0。その後sumoのversion起動が3221225785（0xC0000139）となり08:44:18にFAILED_PRESERVED。14:11:50のcanonical監視でowner不在を確認した。08:28〜14:11の独立監視空白は補作しない。
- [DLL診断](audit_history/native_loader_20261020T141258717959/diagnosis.json)はPE import tableを読み、System32限定LoadLibraryExとGetProcAddressで必要関数を照合した。sumoだけがWS2_32.dllのWSCInstallProviderAndChainsを要求し、実OSでそのexportがない。netconvertは全要求exportが存在し、clean-PATH version exit0。
- SUMOのsumolibs whole-archive内にws2_32が入り、不要なimportまで強制抽出されていた。Microsoft公式の[NTSTATUS](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55)と[当該32bit関数](https://learn.microsoft.com/en-us/windows/win32/api/ws2spi/nf-ws2spi-wscinstallproviderandchains)も照合。OS DLLの変更やWinsock設定操作は行わない。
- a07で隔離src/CMakeLists.txtのMinGW sumolibsについてws2_32だけをwhole-archive外へ移動し、生成responseでも確認。sumo --versionはexit0となった。ただし生成version.hを使うHAVE_VERSION_Hが無効で、表示は公式1.26.0のままだったため、自作helperの識別タグ検査でFAILED_PRESERVED。起動正常を独自版の識別済みとは扱わない。
- a08で公式COMPILE_DEFINITIONS設定にHAVE_VERSION_Hを追加し、生成headerの識別文字列を設定。現在の同一exec handleは53072、owner24352、build child27692。14:18:56の[canonical監視](nativebuild監視_20261020T141856129084.json)で両identity matched、異常なし。これは当該時点の観測で、今後の終了や成功を推定しない。

旧EXE・state・設定・原ログは隔離stagingのattempt07/08へ退避した。b05は可変のコンパイル作業領域であり、研究runの再利用ではない。物理C++の19行修正は同じSHAを維持する。CMakeの共有リンク修正と追加コンパイル定義は、今後の未修正版controlにも同じものを適用する必要がある。controlはまだ未ビルドで、同条件比較証拠は未完成。

## 生成物固定helperのレビュー修正

[対象レビュー](choice_toolchain_packager_review_20261020.md)のP2二件を修正した。後続commandの失敗・未終了・bool値のexit code、未hashまたは同サイズ改変されたcommand logを受理していた。人工証拠5反例で意図したREDを再現し、選択attemptの全commandが整数exit0であることと、全logの観測時SHA/サイズ・コピー前後不変を必須化した。

修正後は専用12 tests PASS。mock/人工PEの起動管理・ファイル契約試験であり、nativeの物理正しさは証明しない。[旧版・RED/GREEN原ログ・source SHA](audit_history/packager_review_fix_20261020/)を保存した。親chatで差分の正しさ・最小性・原本保全・副作用・研究契約をレビューした。新しい重い全体テストは繰返していない。

P1のpaired control/patchの客観証拠不足は未解決。両roleのEXE SHA、compiler/dependency/config/flags/link、登録patchとsource差分を実ファイルへ拘束する必要がある。booleanだけで採用しない。packagerを完成扱いせず、実bundle生成は禁止のまま。別担当のchoice_native_regression.pyと専用testも、完了報告・十分な検証がないため未完成として保全し、実起動しない。

## 運用と次の一件

ユーザー更新の`05_タスク管理/スキル・エージェント運用.md`を再読し、現行§0を正本として適用した。定義・要求設定・実backend確認を区別する。3担当がworkspace credit不足で停止したため再起動せず、親chatの実モデル設定は変更していない。各担当の部分成果を成功とはみなさない。

次は同じ53072/state/owner/childを観測し、a08終了後に実EXEのcustom version・全PE imports・source/設定SHAを検査する。成功してもnative回帰の合格ではない。未修正版controlを同一設定で別source/buildへ作り、paired proofを完成させた後に初めて別Gateでbundle/selected pairへ進む。native guard実証、全fixture、独立audit、全14smoke、入力/unit、新preflight、現行sourceのG6再監査が残る。

現行Registryのrecord_filesはユーザーの記録運用更新を反映した7対象になっている。旧6対象の記載を根拠に戻さず、将来の正式採用前に現行全対象・marker・台帳一意を検証する。現行CLIや入力設定のSHAを新たにfreezeするまで旧技術証跡を転用しない。

経過は現状把握Markdownの日付領域から既存status_progress.pyでHTMLへ反映し一致検査PASS。01_経過報告の旧Markdownは編集していない。Cloudflare再公開、GitHub push、外部送信はしていない。保存済み監視automationはPAUSEDを維持し、親chatのポイント観測だけを記録する。
