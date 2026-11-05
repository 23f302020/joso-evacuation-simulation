# native比較用metadata照合を既存スキルへ集約

2026-10-20。既存joso-jdrt-runnerへ`choice_pair_metadata.py`を追加し、反復していたビルドmetadata照合の不足を限定修正した。新しい独立スキルやSDKは追加しない。研究実行器/PAP/入力/受入条件は変更しない。

## 契約とRED/GREEN

従来の単純なパス置換・全文比較は、CMakeCacheの表記差だけでも不一致となり、逆に`C:/source_extra`のような別directoryまでprefix置換して隠す可能性があった。11テストで契約を定義し、初期実装に7失敗を確認した。import/collection失敗をREDへ数えていない。[RED原ログと初期source](audit_history/pair_metadata_helper_20261020/)を保全した。

修正後は11 tests PASS。全10 metadataを必須とし、重複cache key、不正compiler型/相対path、missingを拒否。宣言したsource/build rootの境界とCRLFだけを正規化する。compiler pathのslash/caseとpath互換のcache型は区別して保存し、その他の値・型・macro/flagの大文字小文字は維持する。空のPython reason項目を欠落と同値にするのは、両方のnative Python bindingsがOFFの場合だけである。

設定変更、include/link変更、非空診断、bindings ON時の空診断の差、別directoryのprefix、cache型・compiler変更の拒否を人工metadataで検証した。テストはコンパイラ・SUMOを起動しない。実compiler file/EXEやnative挙動を検証したというflagはfalseのままで返す。

## 実artifactへの使用

`native_build_metadata_comparison_20261020.py`はこのhelperを呼ぶよう更新し、同じ正規化ロジックの手書き重複を除いた。[実10組の再照合](audit_history/native_metadata_pair_20261020T145127376675/comparison.json)では実効差0。両roleのstate/rawmetadataと各SHAは同folderへ保存。従来のraw CMakeCache差分も別historyへ保全し、都合よく削除していない。

cache型の背景は[CMake 3.31系の-D仕様](https://cmake.org/cmake/help/v3.31/manual/cmake.1.html#cmdoption-cmake-D)を照合した。実toolは保存済み3.31.9である。compiler path・file SHAの同一性は別途確認し、型だけを根拠に同じcompilerと推定しない。

親chatで対象差分をcode-review-and-qualityの観点（正しさ、最小性、既存構造、外部作用、研究契約）で確認した。runtime/package APIへP1合格を付与する変更ではない。実効metadataの一致を、source/binaryの結び付け・native guard・全fixture・READYの代用にしない。P1全体とnative回帰helperは未完成、実bundle生成はまだ禁止。

起動/モデル運用は更新済み`05_タスク管理/スキル・エージェント運用.md`§0に従う。credit停止agentは再起動せず、親chatのモデルを変更したとは記録していない。旧原本/失敗/台帳・現在のコンパイルprocessを保全し、外部送信や公開更新は行っていない。
