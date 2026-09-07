# 常総市JDRT Pre-Analysis Plan v2

> 固定日：2026-08-26  
> 対象：常総市（08211）のみ  
> 状態：v1技術的不成立後・v2実験前に正式固定  
> 基礎計画：`常総市JDRT_PreAnalysisPlan_v1.md`  
> 技術判断：`開発メモ/方針判断_codex/01_JDRT/常総市JDRT_v2技術条件判断_codex.md`

## 1. 改訂の位置づけ

v1の`JDRT-B3` seed 23423は、人物・request・入力SHAの会計を満たした一方、自家用車4台のside collision teleportにより不採用となった。v1の採用条件を結果観測後に緩和せず、共通シミュレーション条件を改訂した別プロトコルとしてv2を開始する。

v1の有効5runと無効1runは監査資料として保存するが、v2の方式比較、5seed集計、効果量には混在させない。

## 2. 研究条件

研究質問、主比較、補助比較、人口、request、自家用車、DRT fleet、乗降時間、配車間隔、予測条件、避難所、主指標、副指標、paired seeds、分析方法、主張限界はv1の第1〜15節をそのまま継承する。

- 対象地域：常総市（08211）のみ
- 中核条件：B2、B3、P1、P2-L15
- paired seeds：23423、42、1、7、101
- v2中核：4方式×5seed＝20runを全て新規実行
- 主指標：Type4 935人の避難成功率
- simulation end：21,600秒

## 3. v2で変更する技術条件

| 項目 | v1 | v2 | 目的 |
|---|---:|---:|---|
| SUMO step length | 1.0秒（既定） | 0.5秒 | 交差点内の離散時間起因衝突リスクを低減 |
| controller更新 | 1秒ごと | 1秒ごと | 配車・閉鎖・状態機械の研究条件を維持 |
| 技術観測 | 1.0秒ごと | 0.5秒ごと | teleport開始・終了を各SUMOステップで捕捉 |
| collision action | teleport（既定） | teleport（明示） | 衝突を隠さず不採用判定へ反映 |
| gridlock teleport | `time-to-teleport=-1` | `time-to-teleport=-1` | v1条件を維持 |

network、車両型、route、需要、seedは変更しない。0.5秒は全4方式・全5seedへ共通適用する。

## 4. 実行順と停止規則

1. 設定・実行器・単体テストを固定する。
2. v1で衝突した`JDRT-B3` seed 23423をv2最初の技術ゲート兼中核セルとして実行する。
3. teleport 0、衝突teleport警告0、未処理SUMO Error 0、会計・SHA一致を満たした場合だけ、残り19セルへ進む。
4. 最初のセルが不合格なら、同じv2内でstep length、vType、network、受入条件を追加変更せず停止する。再設計する場合はさらに版番号を上げる。
5. 同一v2セルに複数の有効runが生じた場合は自動選択せず停止する。

## 5. 採用条件

v1第13節の条件を全て維持し、次を明示する。

- `teleport_count = 0`
- `collision_teleport_count = 0`
- `unhandled_error_count = 0`
- 人物3,255人、request 1,440件、DRT車両5台、自家用車8,164台の会計一致
- v2 Parameter SHA、8入力SHA、event SHA、全出力SHA一致
- controllerは整数秒に各1回だけ実行され、技術観測は0.5秒ごとに行われる

捕捉済みbus route拒否はv1の技術的明確化どおり件数を保存し、未処理0と人物保存則を同時に要求する。

## 6. 解釈制限

- v2は技術条件改訂後の再実験であり、v1との数値差を配車方式の効果として解釈しない。
- v2の20セルが揃うまで方式間の方向主張を行わない。
- 既存Phase 3のA/B主指標ヌル結論を変更しない。
- 常総市以外へ実装または効果量を一般化しない。

## 7. 技術根拠

- SUMO Safety: <https://sumo.dlr.de/docs/Simulation/Safety.html>
- SUMO Randomness / Reproducibility: <https://sumo.dlr.de/docs/Simulation/Randomness.html>
- SUMO Why Vehicles are teleporting: <https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html>

0.5秒刻みは衝突ゼロを保証する設定ではない。衝突を不可視化せず、最初の技術ゲートで実測判定する。
