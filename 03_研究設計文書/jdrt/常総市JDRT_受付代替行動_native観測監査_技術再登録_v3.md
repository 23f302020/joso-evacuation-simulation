# 受付・代替行動：短道路の遷移時刻を訂正する技術再登録 v3

登録日：2026-10-24。protocol=realtime_choice_v1、registration_id=choice_native_observation_v3_20261024。技術準備中であり、READYでもcore開始許可でもない。

旧登録choice_native_observation_v2_20261021の正式8件と、9件目nc26102402のINVALID_PRESERVED原本を保全する。旧8件を新比較へ転記しない。元COMPLETED manifest・元独立INVALID・診断はgoal_20261017/transition_time_candidate_20261024/repair_baseline.jsonおよびnc26102402_短道路・交差点_閉鎖進入診断_20261024.md/jsonから追跡する。

## 訂正する契約

短い通常道路を1step内に通過して下流交差点のinternal laneへ到達した場合、次の通常道路が見えるまで待つ旧観測は通過区間の上限を遅く記録する。元netのsource/target接続とnative route_indexの出現位置から、下流internalに到達した時点でsource通常道路を通過済みと証明する。生成側は前向きの接続展開、独立検証側は逆向きのsource証明で再構成し、生成関数を検証から共有しない。

連続時刻の真値は推定せず、既存CSV列で観測区間を保存する。初期private出発イベントのanchor、native到着の明示終端index、反復経路・経路版・待機/再出庫を照合する。未知のinternal接続・不整合index・欠測を無言で補わない。真の閉鎖後進入・上限が予定Tの進入・曖昧遷移は引き続き拒否する。旧runのCSV・判定は書き換えない。

## 維持する研究方法と版

- 全70セル、登録順、5seed、D0/D1、需要・供給・人物・施設・退出・受付・配車・取消・乗降、徒歩能力、主副指標・分母・比較式・除外規則は既存PAP/Registryと同一。
- 予定閉鎖T、実呼出しmax(0,T−0.5)、観測上限T、phase、0.5秒stepを維持する。物理制御・車両経路選択・native binary/patch・TraCI制御呼出しは変えない。
- 観測・検証のみの技術訂正であり、受入閾値、Warning分類器、歩行予算を緩和しない。未知異常は保全し後続停止する。
- 新workspaceは04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_nativeaudit_v3。新入力、新実験記録、新JSONL台帳を使用する。旧登録・旧READY・旧成果物は履歴であり新証拠へ付け替えない。

## 開始条件

関連unitと反証、短道路/下流internal/到着を含む現行全実SUMO fixtureと独立監査、全反例、全14設定smoke、現行入力・依存SHA、新preflight READY、容量、G6の現行source照合、07監視の新対象をそろえるまでcoreを開始しない。全70採用で共通5版を統一する。

専用CLIで1セルずつvalidate PASS→record7→全7ファイルrun ID同期・台帳一意→statusを行う。退出は施設受入と別計上し、全70採用前に方式の方向を解釈しない。全70後も資料不足・限界・数式考察・最終報告・全体整合までgoalを継続する。研究方法の変更が必要になった場合はAGENTS §7の明示判断へ戻る。
