# SUMO native修正のビルド可能性 — 2026-10-19

調査のみ。ソフト導入、ソース展開、コンパイル、SUMO simulation、研究入力・実行器・PAP変更は実施していない。要求設定 gpt-6.1-sol/high、実バックエンド未確認。新系列正式0/70という親担当の状態を前提とし、研究方法の採否を決める文書ではない。

## 結論

**現環境だけでは直ちにビルドできないが、Windows nativeの隔離ビルドは具体的な候補がある。** PATH外の既存Ruby付属MSYS2に、実起動できるUCRT64 GCC 12.2.0、GNU Make 4.4、リンカ、C++フロントエンド、ヘッダー・CRT・ランタイムが存在する。CMakeとXerces開発ファイルは未検出。最小追加候補はCMake portable ZIPとXerces 3.3.0ソースである。同じGCCでXercesを構築し、SUMO 1.26.0の狭い修正とnetconvertを別フォルダーにビルドする。実コンパイル・リンク・実行互換性は未確認であり、成功を保証しない。

既存GCC/Makeを読取利用すればRuby環境の更新は不要。将来の再現性には使用ツールチェーンのファイルSHA一覧、可能なら既存ucrt64の隔離スナップショットが必要。現在のucrt64のファイル合計は476,623,835 bytes（論理サイズ、約455 MiB）。コピーも今回は実施していない。

## ローカル一次確認

| 対象 | 読取結果 |
|---|---|
| GCC | `C:/Ruby31-x64/msys64/ucrt64/bin/g++.exe --version` → MSYS2 Rev10 GCC 12.2.0、exit 0 |
| Make | 同binの`mingw32-make.exe --version` → GNU Make 4.4、Windows32、exit 0 |
| GCC補助 | `cc1plus.exe`、`ld.exe`、gcc-libs、headers-git、crt-git、winpthreads、gmp/isl/mpfr/mpc、zlib/zstdを既存prefix/package DBで確認 |
| 不足 | 同prefixに`cmake.exe`、Xerces include、`libxerces-c.dll.a`なし。Ninjaも探索で未検出 |
| MSVC | 通常のVS/BuildTools/SDKディレクトリーなし。Program Files、Local Programs、.codex、.cache等の対象探索でもcl/CMake/Ninja/VSBuildTools未検出。全ディスク完全探索の証明ではない |
| WSL | 親担当の実測：Ubuntuで`/bin/echo`成功、x86_64 uid1000、gcc/g++/cmake/ninja/clang/mingw未検出。存在だけでビルド可能とはしない |
| マシン | i5-1240P、論理16、RAM 8,275,980,288 bytes、C空き約269 GB（調査時点） |
| 既存SUMO | 1.26.0、MSVC 19.29.30133.0 Release、FMI Proj GUI FMT Intl SWIG Parquet Eigen。旧binは保全 |
| 既存Xerces | `xerces-c_3_3.dll` FileVersion/ProductVersion `3, 3, 0`、2,818,048 bytes |

SHAの一次値は同名JSONに保存。GCCの起動は確認したが、コンパイル・リンクを伴う試験はこの調査の範囲外。

## 経路比較

| 経路 | 必須追加・条件 | Windows側変更と評価 |
|---|---|---|
| **既存UCRT64 GCCによるWindows native** | portable CMake、同GCCで構築するXerces 3.3.0、固定SUMO source+patch、同toolchainのDLL閉包 | 最小候補。Windows EXEなのでCIM/TraCI subprocessのOS境界を増やさない。Ruby/pacman/PATHの永続変更不要。ただしMSVC→GNU・機能削減・数値実装差があり全技術ゲート再実施必須 |
| Windows MSVC | VS C++ Build Tools/SDK、CMake、MSVCに合うXerces headers/import lib/DLL。公式SUMOLibrariesを使うなら特定commitと必要部分を固定 | 公式Windows経路に最も近い。現在未導入で管理者権限・利用条件・大きな導入が発生し得る。SUMOLibraries repo metadata sizeは4,871,464 KiBだが、これはZIP/clone転送量や展開量の実測ではない。全repo cloneは最小依存ではない |
| WSLのMinGW cross → Windows EXE | Linux g++/CMake/Make、MinGW cross compiler+Windows sysroot、Windows向けXerces、CMake toolchain file、同ABI DLL | 現WSLにcompiler無し。Linux toolchainとcross toolchainの両方を追加するため既存native GCCより手数が多い。出来たEXEはWindows側で試験できるが、cross検出・try-run・DLL配置の追加検証が必要 |
| WSL native SUMO + Windows driver | Linux compiler/CMake/Make/Xerces dev、WSL内のELF binary/共有lib固定、Windows↔Linux起動・TCP・パス・PID監視の橋渡し | EXEにはならない。現binary resolverはPath.is_fileとWindows配置を前提、probeは`binary.parent/netconvert.exe`固定。CIMはLinux SUMOを検出しない。新launcher、path mapping、WSL PID検出・停止・重複防止、TraCI port/localhost、manifest SHAのELF対応が必要。最小変更ではない |

WSLのWindows→Linux localhost接続は公式に対応するが、当該マシンのネットワークモード・TraCI subprocess終了・異常時停止を実証した事実ではない。[Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking)

## Windows native候補の固定方法

1. 既存SUMO 1.26.0と旧/frozen系列を保持する。global PATH/SUMO_HOME、Ruby prefix、pacman DBを変更しない。新系列だけが選ぶtoolchain bundleを作る設計とする。
2. ASCII staging候補：`C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019`。研究repoの空白・日本語を含むパスでのMinGWビルド成功は未確認であるため、追加の不確定要因を避ける候補。ASCII必須という公式保証は確認できていない。CMake公式はMinGW MakefilesをWindows command prompt/mingw32-make/cmd.exe用とし、MSYS shellとの非互換を明記する。[CMake 3.31 MinGW Makefiles](https://cmake.org/cmake/help/v3.31/generator/MinGW%20Makefiles.html)
3. 保全bundle候補：`04_プログラム/output/sumo/toolchains/choice_native_v126_20261019`。runディレクトリーとして流用しない。EXE/DLL/tools/manifest/logを固定し、native simulationは常に別new run ID。
4. SUMO tag `v1_26_0`の実commitは`fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3`。そこから狭いpatchだけを適用し、patch SHAとソース全体の識別子を残す。最新mainや1.28への置換はこの案に含めない。
5. Xercesは現SUMOと同じ3.3.0を候補とする。upstream tag `v3.3.0`の実commitは`31b4b3a06105dcd607db9fda9d1883ad7e489bfe`。現MSVC DLLをMinGWのリンク先には流用しない。GNU C++ ABI/import library/runtimeが揃う同GCCビルドを用いる。
6. CMake 3.31.9 x86_64 portable ZIPは46,643,973 bytes、公表SHA256は`dc16867d0c0ffb35026976aff119335d5b47def44e76ae82ffafdc1f98b3d59d`。今回バイナリーZIPは取得していない。将来は公式checksumと取得物のSHA一致後に展開する。3.xを固定することでSUMO1.26の古いCMake互換性問題を増やさない候補であり、最小版の主張ではない。[公式配布](https://github.com/Kitware/CMake/releases/tag/v3.31.9)・[公式checksum](https://github.com/Kitware/CMake/releases/download/v3.31.9/cmake-3.31.9-SHA-256.txt)

現在MSYS2のXerces3.3.0-4配布は約2.69 MB/展開31.61 MBだが、`cc-libs`とICUへ依存する。旧GCC12のDLL群との混在を検証なしで許可しない。利用するなら依存閉包・ABI/runtime version・全archive SHAを固定し直す必要がある。同compiler source buildが少ない依存で成立する候補。[MSYS2公式package](https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-xerces-c)

## 最小構成コマンド案（未実行）

以下は将来のbuild担当向けの案。変数は専用staging内の絶対ASCIIパスへ設定し、GCC/Make binだけを子プロセスのPATH先頭へ加える。MSYS `/usr/bin`や既存SUMO binをPATHへ追加しない。必要DLLはobjdumpで再帰列挙して閉包を確定する。

```powershell
# CMake/Xerces/SUMO sourceの取得・checksum/commit照合・patch適用後の案。
# $cmake, $gcc, $gxx, $make, $xsrc, $xbuild, $xprefix, $ssrc, $sbuild は絶対パス。
& $cmake -S $xsrc -B $xbuild -G 'MinGW Makefiles' `
  "-DCMAKE_MAKE_PROGRAM=$make" "-DCMAKE_C_COMPILER=$gcc" "-DCMAKE_CXX_COMPILER=$gxx" `
  -DCMAKE_BUILD_TYPE=Release "-DCMAKE_INSTALL_PREFIX=$xprefix" `
  -DBUILD_SHARED_LIBS=ON -Dnetwork-accessor=winsock -Dtranscoder=windows `
  -Dmessage-loader=inmemory -Dmutex-manager=windows -Dmfc-debug=OFF
& $cmake --build $xbuild --target xerces-c --parallel 2
# header/config/importlib/DLLの揃った専用prefixを作るには、Xerces installの対象を確認する。
# installがsamplesも要求する場合は必要targetを構築し、勝手なヘッダー手編集はしない。
& $cmake --install $xbuild --prefix $xprefix
& $cmake -S $ssrc -B $sbuild -G 'MinGW Makefiles' `
  "-DCMAKE_MAKE_PROGRAM=$make" "-DCMAKE_C_COMPILER=$gcc" "-DCMAKE_CXX_COMPILER=$gxx" `
  -DCMAKE_BUILD_TYPE=Release -DISOLATED_BUILD=ON "-DCMAKE_PREFIX_PATH=$xprefix" `
  -DCHECK_OPTIONAL_LIBS=OFF -DCMAKE_DISABLE_FIND_PACKAGE_FOX=TRUE `
  -DCMAKE_DISABLE_FIND_PACKAGE_Proj=TRUE -DFMI=OFF -DNETEDIT=OFF `
  -DENABLE_PYTHON_BINDINGS=OFF -DENABLE_JAVA_BINDINGS=OFF -DENABLE_CS_BINDINGS=OFF `
  -DPARQUET=OFF -DCCACHE_SUPPORT=OFF -DTCMALLOC=OFF
& $cmake --build $sbuild --target sumo netconvert --parallel 2
```

XercesのWinSock/Windows transcoder/in-memory messages/Windows mutexは公式オプション。ICU/curlを必須依存にしない候補だが、UTF-8/XML/ローカルschema参照とXerces unit試験で確認する。networkを無効化する変更はこの案では行わない。[Apache build説明](https://xerces.apache.org/xerces-c/build-3.html)

**1.26固有の注意：** 現行SUMO docsの`ENABLE_FOX=OFF`/`ENABLE_PROJ=OFF`/`ENABLE_FMI=OFF`をそのまま流用しない。1.26のCMakeListsにはそれらのoptionは無く、`FMI`、`find_package(FOX)`、`find_package(Proj)`を使う。`CHECK_OPTIONAL_LIBS=OFF`だけでもFOX/Proj検索は止まらない。generic CMakeの`CMAKE_DISABLE_FIND_PACKAGE_<name>`で対象を明示し、configure logのunused-variable警告、選択feature、実際のリンクを確認する。[1.26 CMakeLists](https://github.com/eclipse-sumo/sumo/blob/fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3/CMakeLists.txt)

最小候補でもSUMO単体だけでは足りない。現probeのfixture生成は同binの`netconvert.exe`を使う。両者を同source・compiler・依存で固定する。Python TraCI/sumolib toolsも同commitを明示選択する必要があり、既にimportされた別traciが勝つ現helperの挙動は配線時に確認対象。

## GUI/PROJ等を省く成立範囲

現runtimeはheadless sumo、plain net XML、plain routes XML、plain tripinfoを渡し、圧縮CSVはPython側で書く。調査したruntime/probeにconvertGeo、geo出力、`--threads`指定はない。GUI/Parquet/libsumo言語binding/FMIはこの経路では要求されていない。

ただし登録netのlocationはUTM zone54の`projParameter`を保持している。既存辺/lane形状は既にメートル座標であり、SUMO1.26のGeoConvHelper constructorはPROJ無しでも一般projection文字列の読込で直ちにthrowしない実装。**これは現入力の実ロードPASSを意味しない。** PROJ無しでgeo↔cartesian変換、geo-route入力、geo出力を利用してはいけない。netXMLのprojection文字列削除や入力編集で通す案ではない。全26suite・反例監査・全14設定smoke・新preflightで登録入力をそのままロードし、必要ならPROJも同compiler依存として追加する。[GeoConvHelper 1.26](https://github.com/eclipse-sumo/sumo/blob/fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3/src/utils/geom/GeoConvHelper.cpp)・[NLHandler 1.26](https://github.com/eclipse-sumo/sumo/blob/fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3/src/netload/NLHandler.cpp)

## 容量・時間の見込みと限界

| 経路 | 計画用の概算（未実測） | 確信 |
|---|---|---|
| 既存GCC＋Xerces＋SUMO | 追加downloadはCMake約46.6 MB＋SUMO/Xerces source。source取得形態により合計約0.1–0.5 GB程度、展開・object・logsを含むstagingは3–8 GBを仮予約。compiler snapshotを行う場合さらに約0.48 GB＋ファイルシステム差分。取得後の初回buildは30–120分を仮見積もり | 低。実コンパイルなし。8 GB RAMなので16並列を使わず2並列開始。patch/link/configure不具合で延長する |
| MSVC新規導入 | 数GB以上のtoolchainにSDK、libraries、source、buildを加える。20–50 GB程度の空き枠を計画上確保し、実component選択画面で確定 | 低。Microsoft全製品の公表範囲850 MB–210 GB/typical20–50 GBは、SUMO最小BuildToolsの実測値ではない |
| WSL cross/native | compiler/sysroot/library/source/object用に概ね2–8 GB＋WSL側更新分。buildだけ30–120分程度でも、driver橋渡し・再監査時間は別 | 低。apt dry-runも導入も実施していない |

時間範囲には全26suite、反例監査、14smoke、preflight、70セル実行を含めない。回線速度・サーマル・RAM圧迫・AV・OneDrive負荷も未測定。MSVC量の出典は[Microsoft system requirements](https://learn.microsoft.com/en-us/visualstudio/releases/2022/system-requirements)。公式Windows/Linux build資料に当該マシンのビルド時間保証は無い。

## 使用開始前の必須条件

- source upstream commit、patch SHA、custom fork/toolchain ID、compilerと依存のSHA一覧、CMakeCache、configure/build log、EXE/netconvert/全non-system DLL/TraCI+sumolib treeのSHA、`--version`を固定する。同じ`1.26.0`表示だけで公式MSVC版と混在させない。
- MinGW DLL閉包はobjdumpで再帰確認する。compiler自身もlibgcc/gmp/isl/mpc/mpfr/winpthread/zlib/zstd等へ依存する。libstdc++だけコピーして完成としない。Windowsのsystem UCRT/KERNEL32はOS versionで別記する。
- binary resolver・preflight・runtime primary manifestが新固定toolchainを選んだ証拠を確認する。既存`runtime_sha256`のsumo_binary/traci_init/traci_vehicle/shared helperだけではcompiler/build/source/全DLL閉包を表せないため、新系列primary manifestで追加契約が必要。
- 狭いnative修正自体のlifetime/遷移安全性は別担当のpatch設計と独立試験で確認する。本調査はpatch正当性を承認しない。
- 新共通toolchainで全26suite・反例監査・全14設定smoke・新preflightをやり直し、旧toolchainのPASSを代用しない。正式0/70を変えない。
- 導入・build開始前に親担当のFact-Forcing Gateと対象所有範囲を確定する。管理者インストール、署名操作、利用規約への代理同意、外部CIへのコード送信、有料計算、global更新は本調査で実行しない。

## 参照・調査範囲

公式GETとローカル読取のみ。Firecrawl検索・scrapeを資料取得に使用し、外部評価/feedback/問い合わせ/公開送信は行わない。公式docsは現行1.28の記述も含むため、実装オプションは固定1.26 sourceへ照合した。[SUMO Windows Build](https://sumo.dlr.de/docs/Installing/Windows_Build.html)・[SUMO Linux Build](https://sumo.dlr.de/docs/Installing/Linux_Build.html)・[SUMOLibraries](https://github.com/DLR-TS/SUMOLibraries)・[Xerces固定source](https://github.com/apache/xerces-c/tree/31b4b3a06105dcd607db9fda9d1883ad7e489bfe)

今回変更したのは本報告と同名JSONだけ。共有helper・研究実行器・PAP・入力・run・Ruby・旧SUMOは編集していない。
