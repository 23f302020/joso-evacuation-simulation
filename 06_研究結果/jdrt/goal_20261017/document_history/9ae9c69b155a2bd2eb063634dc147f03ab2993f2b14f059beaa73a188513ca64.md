# 受付・代替行動：native観測監査の技術再登録 v2

登録日：2026-10-21。protocolはrealtime_choice_v1を維持し、登録識別子をchoice_native_observation_v2_20261021とする。現在は技術準備・未READYである。

ユーザーが承認した最終goalと技術実装・検証の自律実行に基づく観測/監査の改訂であり、PreAnalysisPlan_v1の研究条件、主要・副指標、比較方式、除外規則を変更しない。新しい研究方法の採用権限を追加する文書ではない。

## 改訂の根拠

旧workspace jdrt_realtime_choice_v1のch261021_001はR0の正式採用1件として保全する。ch261021_002は未知のnative急減速警告により独立INVALID、その後専用rejectでINVALID_PRESERVEDとした。原manifest・完走時刻・全出力・原警告・検証・実装/configは変更前SHAとともに保全した。

原速度差・時計・車線・native警告式は整合し、同じbinary/car型の隔離APIで通常/緊急減速度4.5/9.0m/s²を観測したが、元coreに緊急減速度の直接観測がない。固定した横断者あり/なしのpairは警告を再現しなかった。旧R1を後付けで合格へ変更せず、native制約の直接観測を追加して新しい共通版の全比較をそろえる。

診断、原証跡、代替案、非再現と限界、人工反証は06_研究結果/jdrt/goal_20261017/audit_history/R1_native_braking_20261021/に保存する。

## 維持する研究契約

- 全70セル、seed順23423/42/1/7/101、各条件と登録順を維持する。旧セルを新台帳へ転記しない。
- 需要、供給、徒歩能力・距離予算、受付・取消・乗降、予測、洪水閾値、施設/退出、終点と接続、分母・全指標・分析式を変更しない。
- 車両/人物制御、native物理パラメータ、native binary・patchを変更しない。従来のsemi-implicit Eulerと警告threshold既定値を実引数へ明示する。
- Error/collision/teleport/gridlock、人物会計差、二重移動、欠測、閉鎖後進入、曖昧遷移など0件を維持する。既存のidle等のfixtureが課す急減速なし条件を維持する。
- 退出と施設受入を別計上し、全70採用前の方式方向解釈をしない。研究方法・主要指標・比較・除外規則を変える必要が生じた場合はAGENTS §7の明示判断へ戻る。

## 観測・検証の改訂

車両の全step actor CSVへnative購読によるemergency_decel_mps2を追加する。通常減速度からの推定や欠損の補完をしない。欠損・非有限・不正な関係は失敗にする。nativeの所有process IDと実Popen引数、登録識別子、監査契約をmanifestへ保存する。Popen引数の保存を、独立したOS argv観測と混同しない。

一般道路走行の急減速Warningについては、対応するactorの3時点の直接観測、pre-move lane/after-step時計、通常/緊急native制約、速度差、native式・表示精度、距離整合と対応の一意性を独立監査する。native source/compiled config/binary/options/schemaが未対応、観測が欠損・曖昧、制約逸脱等の場合は未知診断としてINVALID・保全・後続停止を維持する。actor名や文字列だけのwhitelistを作らない。emergency stopを新たに許可しない。

ログ分類は物理的安全性・唯一原因・現実の避難成功を証明するものではない。他の全独立監査の合格を代替しない。元coreの欠けた観測を隔離試験で補作しない。

## 版の分離と開始条件

新workspaceは04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v2、新入力は同所inputs/registered01。新実験記録・新JSONL台帳を使用し、現在地/詳細task/決定ログ/現状把握md/htmlは履歴を残して新登録を明示する。旧workspace・旧台帳・旧run・旧READY・旧記録は保全する。

共通5実装は技術修正とレビュー/必要な試験後に固定する。旧SHAのsuite/smoke/READYの付替えはしない。独立入力検証、対象unit/反証、現行全26統合、全14設定smoke、preflight READY、容量、G6実装証拠と既存07監視の新対象を確認するまでcore開始は禁止。新IDで1セルずつvalidate PASS→record7→同期/台帳一意→statusを行う。全70の完了だけで最終goalを完了扱いにしない。
