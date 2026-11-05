# 受付・代替行動：停車履歴の共通native修正 技術再登録v5（隔離下書き）

状態：DRAFT_NOT_APPLIED、技術READY=false、本実験開始不可。この文書はgoal内の準備資料であり、03_研究設計文書の正本や実設定を置換していない。両bundleの完了・原本照合・manifest SHA固定後に、技術登録正本と設定を一まとまりで確定する。

## 目的と旧登録の保全

新登録候補は `choice_shared_stopindex_v5_20261029`、新workspace候補は `04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5`。旧v4は「native binary/patchは変更しない。」と明記するため、修正版nativeを黙って差し替えない。v4の12件の設定smoke独立PASSと13件目のFAILED、v3の旧9採用と失敗10、旧native・全build/診断/来歴検査の失敗を保全し、新主比較へ移記しない。

v4の残経路API訂正・停止済み取消・位置観測と、それ以前の位置/時計/会計契約は引き継ぐ。置換するのはv4のnative不変という技術登録条件だけで、研究方法・比較方式・主要/副指標・除外規則の変更ではない。

## 修正する動作と数式の範囲

経路置換の前後で現在道路の経路内番号が変わる際、過去停車番号だけが旧経路の番号を保持すると、新しい経路の範囲外を参照し得る。元の13件目はnativeアクセス違反を記録し、別の人工観測で新経路2区間に過去停車番号66が残る条件を観測した。人工観測自体はクラッシュしていないため、元停止の全因果や全経路形状の安全性が証明済みとはしない。

旧現在番号を i_old、新現在番号を i_new、旧過去停車番号を j_old とし、対応候補を

`j_new = j_old - i_old + i_new`

とする。`0 <= j_new <= i_new`、かつ新経路の当該道路がその過去停車の道路と一致する場合だけ、過去停車番号を更新して保持する。それ以外は新経路での過去停車履歴から除く。範囲内への単純な丸め、将来道路の閉鎖検査の無効化、位置の補間や瞬間移動、観測に出ないsimulationStepを導入しない。予定された将来停車の保持・ループ内の道路の複数出現・停止/走行状態の妥当性は、別途の実native回帰で確認する。

修正対象は `src/microsim/MSBaseVehicle.cpp` のみ。原本SHA `9e46ef6907cd293b2b3a629f27709da042c35f61cd9d57a5081d966d9d4f22d3`、修正後SHA `eeb62ad14b9afd1984da4bd42f64b89288b67e62fc670a46811ede2cfd4e4fa1`、パッチSHA `c6570afbcba31f9ae0a9fb38a4b244e50307955051b779a69a1965112dce849d`。同じ修正を対照/選択両版に適用する。両版間の差分は登録済みの歩行lateral保存修正だけとし、停車履歴修正まで方式差へ混ぜない。

## 確認済みの来歴と未実証の範囲

両版の全ソースからのビルドと別々の標準DLL/関数解決・clean PATHでのversion確認が終了した。対照versionは `1.26.0-jdrt-choice-stopindex-control-repair02_20261029`、選択versionは `1.26.0-jdrt-choice-stopindex-patched-repair03_20261029`。

元の来歴検査02は正常終了し、原本13,004ファイル、各6,228ソース、設定10組、依存ツール9件、ヘッダ471件を照合した。公式ZIPからの修正範囲と旧ポリシーの継承も検査した。対照と選択の新しい設定10ファイルは一致する。旧ビルドとのGit検出版の差は保全し、旧/新の全設定一致や再現ビルド同一性は主張しない。

この来歴の合格は、修正後の物理挙動、現実の精度、本実験の採用・開始許可ではない。隔離候補での代数契約7件・限定native6件は、今回の正式bundleの全回帰を代替しない。一次記録の旧/新形式差で不合格となった来歴検査01は保全し、原本に要約成功値を補作せず、6工程の実コマンド・終了コード・ログSHAと独立loaderから直接照合する対応を試験した。

## 維持する研究条件

全70セルのID・登録順・値とseed `23423,42,1,7,101`、目的地/需要/予測方針、人口と属性・意思/受付・供給・施設と退出、初期/目的地位置、洪水と閉鎖予定/呼出し/観測の時計、配車・取消・乗降、主要/副指標・分母・比較式・除外規則をv4から維持する。設定下書きは6つの管理項目以外の全値が一致することを比較済み。未取得の現実の需要・供給・路面高などを、この修正で校正済みとはしない。

新入力は旧物理入力を保全した別workspaceへ作り、人物・施設・危険・共通実現・ネットワークの原本SHAを照合する。新全70セルで同じcommon5・native bundle・入力版を使い、旧run/ID/保存先の再利用・上書き・削除をしない。退出は施設受入と別計上、全70正式記録前に方式の方向を解釈しない。

## 正式化前と本実験前の必須条件

1. 両bundleのパッケージ作成が元処理の正常終了まで完了し、manifest/全ファイルSHA・version・原本対応を独立確認する。現在は対照版を作成中、選択版は未開始。SHA欄を不明のまま本実験へ進めない。
2. 現config/正本/旧台帳/入力をSHA付きで保全し、この文書と管理情報だけの新config・新実験記録・新JSONL台帳を確定する。候補のstatusはDRAFTで、未適用のままREADYへ読み替えない。
3. 新入力を専用helperで作成し、旧入力不変・科学的設定と全セル集合の一致を独立確認する。
4. 新両版のnative回帰、限定経路・時刻・閉鎖・乗降・ループ/予定停車と人物会計、現行全controller fixtureと独立全成分/改変反例を完了する。実際に失敗した設定は全14smokeの該当条件でも確認し、重複した成功runを増やして穴を埋めない。
5. 全14設定smoke、新専用preflight READY原本と共通5/入力/依存SHA、G6の式と登録集合、1セル分の容量予約、07監視の本人確認・対象と鮮度を確認してから、親chatが最初のcoreを新IDで開始する。
6. 以後は1セルずつ独立validate PASS/core adoption permitted、専用record7、7ファイル読戻し/台帳一意/statusを完了してから次へ。失敗・未診断・部分記録・孤児・SHA/時計/会計不一致や容量不足では原本保全して停止する。

## 正本化時に固定する証拠（未固定欄を残さない）

- 対照bundle manifest/SHA：PENDING
- 選択bundle manifest/SHA：PENDING
- 科学的条件不変の比較：`v5_registration_candidate/comparison.json`、元config SHA `782252f9f3ffaf044a1598d79ef89a38f63a90ba17ffdd45273f3817f49882b8`
- 両版の終端/loader/ソース：`native_stop_index_pair_policy/terminal_roles_readback.json`
- 全来歴02/独立読戻し：`full_pair_primary02/verification.json`、`full_pair_primary02_terminal_readback.json`
- 新共有修正ポリシー：`native_stop_index_pair_policy/policy.json`、原本の旧ポリシーは維持
- 形式対応と試験：`raw_primary_adapter_review.json`
- 現操作・元handle/PID・次の1件：G4実装・実SUMO_継続チェックポイント.json、operations.jsonl

最終goalは全70だけで完了とせず、比較・数式考察・不足資料/限界・後続大型バス・報告と全体文書整合まで継続する。Drive読取のみ、外部送信・公開更新なし。
