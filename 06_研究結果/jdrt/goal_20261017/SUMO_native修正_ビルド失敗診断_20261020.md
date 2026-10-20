# SUMO native修正：隔離build失敗診断（2026-10-20）

観測時刻 **2026-10-20T08:26:45.727801+09:00**。要求モデルは親タスク指定の `gpt-6.1-sol/high`、実バックエンドは未確認。

## 結果

現在のattemptは **attempt06_20261020 / RUNNING**、phaseは `sumo_netconvert_build_short_path`。state最終更新 `2026-10-20T08:26:32.550437+09:00`。owner PID `17468`、child PID `12700`。同時点のPID実在・creation・commandは同名JSONに保存した。観測後に進むbuildの最新状態は隔離 `build_state.json` を参照する。

旧2026-10-19 attemptは `sumo_netconvert_build_static` がexit 2で終了し、失敗logとstateを保全。Xerces staticのbuild/installはexit 0。原因はZLIB無効構成で到達する `OutputDevice_File.cpp` の分岐で、43/70行の `std::ofstream` 不完全型と67行の未宣言 `compressed`。最初のcompile errorを原logから確認しており、native lateral物理patchのcompile errorではない。

## 最小修正と保全

物理source patchを増やさず、既存 `C:/Ruby31-x64/msys64/ucrt64` のZLIB `1.2.13-3`静的archive `libz.a` と `zlib.h/zconf.h` を隔離コピーし、CMakeのZLIBを有効にした。元ファイルとコピーのSHA一致を検証、コピー・由来・SHAはstateの `zlib_dependency` に保存。Ruby/pacman/global PATH/旧SUMOは変更していない。a03/a04は `b03`、a05/a06は短alias経由の新 `b05` を用い、元 `build-sumo-static` と旧buildを保全した。

attempt02はconfigure自体exit 0だったが、新補助チェックが `#define HAVE_ZLIB 1` だけを期待し、正しい `#define HAVE_ZLIB` にassert失敗した。これは補助側の不備。旧補助版を `attempt02_20261020/rebuild_attempt02_failed.py`、旧stateを各attemptの `previous_build_state.json` に保存し、有効定義行を確認するよう修正したattempt03を新規開始した。既存attemptを再実行する操作は拒否する。build helperは20秒間隔でJSON更新し、owner/childのcreationとcommandを記録する。現在のexec session handleは `2421`。反復するprocess環境・同PID識別・状態保存・log処理を隔離 `native_build_support.py` に集約した。

compileはGCC 12.2.0、portable CMake 3.31.9、2並列。XercesとZLIBをstatic指定し、compiler runtimeもstaticリンク指定。configureはZLIB検出と `HAVE_ZLIB` 有効定義を確認済み。custom versionは `1.26.0-jdrt-choice-latpreserve-93d3ca0c-ucrt12-static-zlib1213-a03-shortpath-a05`。公式release binaryとは扱わない。

source archiveの2870 members（src/build_config/CMakeLists）を独立照合した。存在するファイルの内容差は既存 `MSPModel_Striping.cpp` patchのみ。ただし元の展開に `build_config/debian/tests` の2ファイルと `src/utils/tests` の5ファイルが不在で、完全なsource tree一致とは主張しない。長いvissim名31ファイルは通常Path APIの偽陰性があったためextended-pathで読んでSHA一致を確認した。原照合は `attempt03_20261020/source_integrity.json` に保存し、この作業でsourceを補完・変更していない。

欠落5ファイルの `src/utils/tests` は `src/utils/CMakeLists.txt:15–18` の `if (FOX_FOUND)` 内でだけ追加される。今回はFOX検索を無効化しており、headless sumo/netconvert targetの構成に入らない。Debian package testsの2ファイルもWindowsの両targetに含まれない。GUIや配布用testを含む完全sourceのbuildへ転用できる保証はない。

compile済みと判定するにはsumo/netconvert両targetの成功・生成EXE・SHAが必要。後続の `--version` とPE import列挙はload確認であり、simulationではない。現在の成果物/依存load情報は同名JSONにある。

attempt03はsumoの全objectをcompileできたが、linkでZLIB_LIBRARYのbackslashが消えてarchiveを発見できずexit 2。CMakeへの明示指定がUNINITIALIZED型のbackslash文字列であり、responsefileからldが `C:Users...libz.a` と解釈した。attempt04は旧state/cache/responsefileを保全し、同archiveを `ZLIB_LIBRARY:FILEPATH` / `ZLIB_LIBRARY_RELEASE:FILEPATH` とforward slashで指定して、既存objectを再利用する。物理source・依存SHA・compiler flagsは不変。

MinGWの `ISOLATED_BUILD` はruntime outputをbuild内の各target作業dirへ残す。生成link.txtで実出力は `b03/src/sumo.exe` と `b03/src/netconvert.exe` と確認した。a03補助末尾の `b03/bin` 仮定も訂正が必要だったが、a03はそのlocatorへ到達する前に上記linkで停止した。attempt04は正しい実出力のversion/importsを確認する。

attempt04ではsumoがlink成功した後、netconvertのVissim importerが実在する長名headerを開けず停止した。元の物理pathは266文字。同じheaderが短い表示aliasの213文字pathでGCC syntax check exit 0となり、source欠落や内容変更ではないことを確認した。OSのlong-path設定やVissim機能の削除は行っていない。

attempt05のCMake configureはexit 0で短aliasを保持した。しかし補助チェックがdrive文字の大文字小文字差とCMakeのinclude responsefileを誤判定し、compile前に停止した。error文のcanonicalizedという説明は誤りであり採用しない。attempt06はcache pathを正規化し `includes_CXX.rsp` を読み、全4checkを確認して同じb05を再configureせずresumeする。Vissim関連targetを先にcompileし、その後sumo/netconvertへ進む。

公式traci/sumolib全fileとAUTHORS/LICENSE/NOTICE.mdはsource archiveの169membersへ独立SHA照合し、missing/mismatch/余分file・bytecodeなしを確認した。原一覧は `attempt04_20261020/official_python_tools_inventory.json`。binaryや研究CLIへの採用とは区別する。

未patch対照buildは **未開始**。対照はpatched owner終了後に別source/buildへコピーし、target1ファイルだけを保存archiveの未patch原本へ置換、同configure引数（source/build先のみ変更）・同依存・2並列で構築する。識別用custom versionもcontrolと明記する。最終回帰前提を準備する操作であり、simulationは許可していない。

## Fact-Forcing Gate

1. 対象は隔離build補助・設定・新attemptログ/JSONとこの診断2文書。研究実行器からの参照なし。
2. 研究公開関数/クラス変更なし。既存ZLIB対応をbuild設定で有効化。
3. 旧state/logを保全、新attemptへJSON状態・由来SHA・configure/build/version/importログを保存。
4. 親依頼の引用：「補助設定/compatibility/build修正で済むなら証拠・旧版・Gateを残して新attemptログ/状態で再build可（既存失敗log保全）。」

## 未完と境界

simulation、native regression、研究CLI pin切替、全suite/audit/14smoke/preflightは実施していない。buildとversionが成功しても横位置保持の正当性・研究READYにはならない。研究入力・PAP・共通5実装・frozen系列・既存run・step_busは変更していない。未patch対照binaryの状態は上記と同名JSONを参照する。

一次根拠は同名JSONと隔離stagingの原log/state。MSIX実pathは `C:\Users\Ko_rr\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\JDRT-native-build\choice_v126_20261019`。この報告は親担当の現状文書・公開表示に研究READYを与えない。
