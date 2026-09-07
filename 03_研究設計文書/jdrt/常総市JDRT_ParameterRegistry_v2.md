# 常総市JDRT Parameter Registry v2

> 固定日：2026-08-26  
> 状態：v1技術的不成立後・v2実験前に正式固定  
> 対象：常総市（08211）のみ  
> 機械可読正本：`04_プログラム/config/jdrt_parameters_v2.json`  
> 継承元：`常総市JDRT_ParameterRegistry_v1.md`

## 1. 継承条件

v1のJPR-P001〜JPR-R603を全て同じ値で継承する。人口、需要、fleet、配車条件、予測誤差、避難所、seed、主指標は変更しない。入力8ファイルの正本とSHAもv1から変更しない。

## 2. v2追加・改訂項目

| ID | 名称 | 正式値 | 単位 | 区分 | 不確実性 | 感度 | 根拠・注意 |
|---|---|---:|---|---|---|---|---|
| JPR-T701 | parameter version | jdrt-v2-20260826 | version | 再現性 | 低 | なし | v1 runと混在させない |
| JPR-T702 | SUMO step length | 0.5 | 秒 | 技術条件 | 中 | v2内変更なし | 交差点内衝突の時間離散化を細分化 |
| JPR-T703 | controller step interval | 1.0 | 秒 | 技術条件 | 低 | なし | v1の状態更新頻度を維持 |
| JPR-T704 | technical observation interval | 0.5 | 秒 | 技術条件 | 低 | なし | 各SUMOステップのteleportを捕捉 |
| JPR-T705 | collision action | teleport | action | 品質ゲート | 低 | なし | 衝突を隠さずinvalidとする |
| JPR-T706 | time to teleport | -1 | 秒 | 技術条件 | 低 | なし | gridlock teleport無効、衝突teleportは有効 |
| JPR-T707 | collision teleport acceptance | 0 | 件/run | 品質ゲート | 低 | なし | 1件以上で当該runを不採用 |
| JPR-T708 | v2 core run count | 20 | run | 実験設計 | 低 | なし | 4方式×paired 5seedを全て再実行 |

## 3. 版分離規則

- completedセルの重複判定はscenario、seed、Parameter SHAの組で行う。
- v1の有効runをv2の20runへ数えない。
- run manifestへparameter version、Parameter SHA、step length、controller intervalを記録する。
- v2最初のB3 seed 23423が技術ゲート不合格なら、v2の設定を追加調整せず停止する。

正式値はv2結果確認後に変更しない。再改訂が必要な場合はv3として設定・PAP・Registry・全影響runを分離する。
