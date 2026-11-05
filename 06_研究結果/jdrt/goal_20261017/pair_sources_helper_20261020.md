# native比較ソース：現在バイトの独立照合

2026-10-20。既存JDRTスキルの反復検証へ`choice_pair_sources.py`を追加した。前段の保存snapshot比較から進み、実際のcontrol/patched source tree全件を読み直した。研究条件・実行器・SUMO source・既存runを編集していない。

## 実測と範囲

[一次報告](native_pair_sources_20261020T150645971959.json)は両role各6,228件の集合・SHAをprepared snapshotと照合し、各現行バイトを公式commit ZIPの原本と比較した。登録native patchはpatched側だけ、既存CMakeリンク修正は両側へ、unified diffを原本へ厳密適用して結果SHAを再計算した。許容差以外の改変はなかった。これは公式ZIPの全223,068ファイルを展開済みという意味ではない。

必須build範囲CMakeLists.txt/src/build_configは2,861件。欠けた7件は以前分類したFOX GUI試験5件とDebian package試験2件だけで、両roleの現行cache/config/生成target/source guardから対象外であることを再計算した。欠損を補完済みとは扱わない。scope外でも、現存する全ファイルはZIPと照合し、共通の余計な改変を許さない。

source helperはプロセスを起動せず、source/ZIP/patchを変更しない。呼出し側は公式archive・登録proposal・共有patch・欠損分類・prepared inventoryの承認済み参照をSHAで拘束する必要がある。単に任意のpolicyを渡して成功しても研究の採用根拠にならない。

## 試験・原因診断・レビュー

[検証台帳](audit_history/pair_sources_helper_20261020/verification.json)と同directoryのログを参照。初期10試験では11反例subcaseが不具合を再現してRED、実装後GREEN。実原本では共有CMake diffの保存改行がCRLFであるため最初の実照合を拒否した。CRLF転送diffと混在改行拒否の人工試験を追加し、12試験中1 ERRORのREDを確認してから修正した。diffテキストの均一CRLFだけを処理し、公式sourceと適用後sourceのバイト/SHAは変換しない。12試験GREEN後に実6,228件×2roleも成功した。失敗・旧helper bytesは保存した。

試験はmissing/extra、stale inventory、両側共通の未登録変更、patch未適用、偽after SHA、base/context/target不一致、ZIP重複/traversal、同一root、CRLF転送/混在を確認。人工の重複ZIP警告は意図した反例生成による。親chat内で対象diffをレビューし、path/集合/SHA、原本保全、限定的改行処理、研究ゲートとの分離を確認した。別モデルの同意やnative物理試験ではない。ASTと対象whitespace検査も実施した。

## 残る開始ゲート

P1全体は未完了。次は両terminal state、EXE、version/build logs、compiler/static依存、全10metadataを同じ客観的pairへ拘束し、相手EXEやcompiler/dependency/flags/linkの差替えを拒否する試験を行う。packagerへ未接続、実runtime bundleなし、selected pair/native guard未実行、READY=false・正式0/70を維持する。全26fixture/audit/14smoke/new preflight/G6と最終研究分析も残る。
