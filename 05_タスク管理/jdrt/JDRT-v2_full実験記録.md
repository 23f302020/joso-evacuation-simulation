# 常総市JDRT v2 full実験記録

> 開始日：2026-08-26  
> 対象：常総市（08211）のみ  
> PAP：`03_研究設計文書/jdrt/常総市JDRT_PreAnalysisPlan_v2.md`  
> Parameter Registry：`03_研究設計文書/jdrt/常総市JDRT_ParameterRegistry_v2.md`  
> 状態：中核20/20セル完了（seed 23423・42・1・7・101完了）

## 1. 実行条件

- protocol：v2
- Parameter version：`jdrt-v2-20260826`
- Parameter SHA-256：`c878760eeff72b47110784f17bd98856dc292dd2fcb98636a42c632f6507b411`
- SUMO：1.26.0
- simulation step：0.5秒
- controller interval：1.0秒
- collision action：teleport
- 採用条件：teleport 0、collision teleport 0、未処理Error 0、全会計・SHA一致
- v1 runは本表へ含めない

## 2. 中核セル一覧

| # | scenario | seed | run ID | 状態 | technical valid | teleport | collision | 未処理Error | 備考 |
|---:|---|---:|---|---|---:|---:|---:|---:|---|
| 1 | JDRT-B3 | 23423 | `core_v2_b3_seed23423_20260826_codex01` | COMPLETED | true | 0 | 0 | 0 | v2最初の技術ゲートPASS |
| 2 | JDRT-B2 | 23423 | `core_v2_b2_seed23423_20260826_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 3 | JDRT-P1 | 23423 | `core_v2_p1_seed23423_20260826_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 4 | JDRT-P2-L15 | 23423 | `core_v2_p2_l15_seed23423_20260827_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 5 | JDRT-B3 | 42 | `core_v2_b3_seed42_20260827_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 6 | JDRT-B2 | 42 | `core_v2_b2_seed42_20260827_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 7 | JDRT-P1 | 42 | `core_v2_p1_seed42_20260827_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 8 | JDRT-P2-L15 | 42 | `core_v2_p2_l15_seed42_20260907_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 9 | JDRT-B3 | 1 | `core_v2_b3_seed1_20260907_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 10 | JDRT-B2 | 1 | `core_v2_b2_seed1_20260908_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 11 | JDRT-P1 | 1 | `core_v2_p1_seed1_20260908_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 12 | JDRT-P2-L15 | 1 | `core_v2_p2_l15_seed1_20260908_codex02` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS。`codex01`は外部中断FAILED保全 |
| 13 | JDRT-B3 | 7 | `core_v2_b3_seed7_20260908_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 14 | JDRT-B2 | 7 | `core_v2_b2_seed7_20260908_codex01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 15 | JDRT-P1 | 7 | `core_v2_p1_seed7_20260912_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 16 | JDRT-P2-L15 | 7 | `core_v2_p2_l15_seed7_20260912_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 17 | JDRT-B3 | 101 | `core_v2_b3_seed101_20260912_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 18 | JDRT-B2 | 101 | `core_v2_b2_seed101_20261009_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 19 | JDRT-P1 | 101 | `core_v2_p1_seed101_20261015_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |
| 20 | JDRT-P2-L15 | 101 | `core_v2_p2_l15_seed101_20261015_skill01` | COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |

残り0セル。方式間比較・方向判断は20セル完了後まで行わない。

## 3. B3 seed 23423 技術ゲート

v1で4件のside collision teleportが発生した同じscenario・seedを、v2最初の技術ゲート兼中核セルとして実行した。0.5秒刻みで21,600秒まで完走し、manifestは`COMPLETED`、`summary.valid=true`だった。

### 実測会計

| 項目 | 実測 |
|---|---:|
| controller step | 21,600 |
| technical observation | 43,200 |
| 人物 | 3,255 |
| 避難完了 | 53 |
| 立ち往生 | 3,202 |
| Type4避難完了 | 46 / 935 |
| Type3避難完了 | 7 / 2,320 |
| request | 1,440 |
| 完了request | 19 |
| 立ち往生request | 1,421 |
| DRT総VKT | 133.062781 km |
| event | 1,553 |
| SUMO Warning | 1,399 |
| SUMO Error | 3 |
| controller捕捉済みroute拒否 | 3 |
| 未処理Error | 0 |
| TraCI teleport | 0 |
| collision teleport | 0 |
| gridlock teleport | 0 |

### 独立検証

- Parameter SHA：1/1一致
- 入力SHA：8/8一致
- 出力SHA：9/9一致
- event行数：manifest 1,553＝実ファイル1,553
- event SHA：一致
- `sumo_error.log` Warning：manifest 1,399＝実ファイル1,399
- `sumo_error.log` Error：manifest 3＝実ファイル3
- `teleport`文字列行：0
- `collision` teleport行：0
- 人物：53＋3,202＝3,255
- request：19＋1,421＝1,440

以上によりJDRT-V2-G1を合格とし、このrunをv2中核1/20セルとして採用する。避難完了53人という単一セル値をv1または他方式との差として解釈しない。

## 4. B2 seed 23423

同じseed 23423の`JDRT-B2`を2番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 23 / 3,232 |
| Type4 / Type3避難完了 | 10 / 13 |
| 完了 / 立ち往生request | 8 / 1,432 |
| DRT総VKT | 29.188957 km |
| event | 1,501 |
| Warning / Error | 1,160 / 1 |
| 捕捉済み / 未処理Error | 1 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、Warning/Error実数を独立再計算して全て一致した。単一B2セルをB3との差として解釈しない。

## 5. P1 seed 23423

`JDRT-P1` seed 23423を3番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 20 / 3,235 |
| Type4 / Type3避難完了 | 15 / 5 |
| 完了 / 立ち往生request | 6 / 1,434 |
| DRT総VKT | 63.161297 km |
| event | 1,494 |
| Warning / Error | 1,153 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、Warning/Error実数を独立再計算して全て一致した。P1は完全予測の理論条件であり、この単一セルを政策効果として解釈しない。

## 6. P2-L15 seed 23423

`JDRT-P2-L15` seed 23423を4番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 8 / 3,247 |
| Type4 / Type3避難完了 | 4 / 4 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 66.960634 km |
| event | 1,483 |
| Warning / Error | 1,117 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、Warning/Error実数を独立再計算して全て一致した。これでseed 23423の4方式が揃ったが、残る4seed完了前に方向判断を行わない。

## 7. B3 seed 42

`JDRT-B3` seed 42を5番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 57 / 3,198 |
| Type4 / Type3避難完了 | 47 / 10 |
| 完了 / 立ち往生request | 22 / 1,418 |
| DRT総VKT | 147.601555 km |
| event | 1,567 |
| Warning / Error | 1,698 / 3 |
| 捕捉済み / 未処理Error | 3 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、Warning/Error実数を独立再計算して全て一致した。seed 42の残る3方式前に方向判断を行わない。

## 8. B2 seed 42

`JDRT-B2` seed 42を6番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 43 / 3,212 |
| Type4 / Type3避難完了 | 18 / 25 |
| 完了 / 立ち往生request | 16 / 1,424 |
| DRT総VKT | 67.464445 km |
| event | 1,535 |
| Warning / Error | 1,311 / 1 |
| 捕捉済み / 未処理Error | 1 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、Warning/Error実数を独立再計算して全て一致した。seed42のB3との差は残るP1/P2-L15完了前に解釈しない。

## 9. P1 seed 42

`JDRT-P1` seed 42を7番目のセルとして実行した。中断後の2026年9月7日に完走済み成果物を確認し、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 9 / 3,246 |
| Type4 / Type3避難完了 | 4 / 5 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 49.229187 km |
| event | 1,479 |
| Warning / Error | 1,381 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、Warning/Error実数を独立再計算して全て一致した。seed42のP2-L15と残る3seedが未完了のため方向判断は行わない。

## 10. P2-L15 seed 42

`JDRT-P2-L15` seed 42を8番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 8 / 3,247 |
| Type4 / Type3避難完了 | 5 / 3 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 57.150706 km |
| event | 1,480 |
| Warning / Error | 1,172 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、Warning/Error実数を独立再計算して全て一致した。これでseed42の4方式が揃ったが、残る3seed完了前に方向判断を行わない。

## 11. B3 seed 1

`JDRT-B3` seed 1を9番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 36 / 3,219 |
| Type4 / Type3避難完了 | 33 / 3 |
| 完了 / 立ち往生request | 12 / 1,428 |
| DRT総VKT | 106.562820 km |
| event | 1,526 |
| Warning / Error | 1,269 / 4 |
| 捕捉済み / 未処理Error | 4 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、Warning/Error実数を独立再計算して全て一致した。seed1の残る3方式と残る2seed完了前に方向判断を行わない。

## 12. B2 seed 1

`JDRT-B2` seed 1を10番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 20 / 3,235 |
| Type4 / Type3避難完了 | 8 / 12 |
| 完了 / 立ち往生request | 7 / 1,433 |
| DRT総VKT | 34.171033 km |
| event | 1,500 |
| Warning / Error | 1,179 / 1 |
| 捕捉済み / 未処理Error | 1 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、Warning/Error実数を独立再計算して全て一致した。途中の方式間方向判断は行わない。

## 13. P1 seed 1

`JDRT-P1` seed 1を11番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 9 / 3,246 |
| Type4 / Type3避難完了 | 4 / 5 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 48.964886 km |
| event | 1,486 |
| Warning / Error | 1,148 / 4 |
| 捕捉済み / 未処理Error | 4 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、Warning/Error実数を独立再計算して全て一致した。seed1のP2-L15と残る2seed完了前に方向判断を行わない。

## 14. P2-L15 seed 1

最初の`core_v2_p2_l15_seed1_20260908_codex01`は監視セッション終了時にプロセスが残らず、孤児`RUNNING` manifestを既存復旧関数で`FAILED`へ確定・保全した。同じセルを`core_v2_p2_l15_seed1_20260908_codex02`として再実行し、12番目の有効セルとして採用した。新runのmanifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 8 / 3,247 |
| Type4 / Type3避難完了 | 4 / 4 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 56.722154 km |
| 空車VKT | 33.838942 km |
| 到着時刻P95 | 3,649 sec |
| event | 1,480 |
| Warning / Error | 1,363 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。これでseed1の4方式が揃ったが、残る2seed完了前に方向判断を行わない。

## 15. B3 seed 7

`JDRT-B3` seed 7を13番目のセルとして実行した。manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 52 / 3,203 |
| Type4 / Type3避難完了 | 45 / 7 |
| 完了 / 立ち往生request | 18 / 1,422 |
| DRT総VKT | 127.955678 km |
| 空車VKT | 96.430714 km |
| 到着時刻P95 | 12,185 sec |
| event | 1,549 |
| Warning / Error | 1,432 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。seed7の残る3方式とseed101完了前に方向判断を行わない。

## 16. B2 seed 7

`JDRT-B2` seed 7を14番目のセルとして実行した。run IDは`core_v2_b2_seed7_20260908_codex01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 26 / 3,229 |
| Type4 / Type3避難完了 | 11 / 15 |
| 完了 / 立ち往生request | 9 / 1,431 |
| DRT総VKT | 36.908887 km |
| 空車VKT | 22.085438 km |
| 到着時刻P95 | 7,334 sec |
| event | 1,509 |
| Warning / Error | 1,186 / 1 |
| 捕捉済み / 未処理Error | 1 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 17. P1 seed 7

`JDRT-P1` seed 7を15番目のセルとして実行した。run IDは`core_v2_p1_seed7_20260912_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 9 / 3,246 |
| Type4 / Type3避難完了 | 5 / 4 |
| 完了 / 立ち往生request | 4 / 1,436 |
| DRT総VKT | 53.226622 km |
| 空車VKT | 39.024221 km |
| 到着時刻P95 | 3,333 sec |
| event | 1,485 |
| Warning / Error | 1,154 / 4 |
| 捕捉済み / 未処理Error | 4 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 18. P2-L15 seed 7

`JDRT-P2-L15` seed 7を16番目のセルとして実行した。run IDは`core_v2_p2_l15_seed7_20260912_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 16 / 3,239 |
| Type4 / Type3避難完了 | 11 / 5 |
| 完了 / 立ち往生request | 8 / 1,432 |
| DRT総VKT | 71.612915 km |
| 空車VKT | 42.692037 km |
| 到着時刻P95 | 8,975 sec |
| event | 1,498 |
| Warning / Error | 1,185 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 19. B3 seed 101

`JDRT-B3` seed 101を17番目のセルとして実行した。run IDは`core_v2_b3_seed101_20260912_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 47 / 3,208 |
| Type4 / Type3避難完了 | 42 / 5 |
| 完了 / 立ち往生request | 16 / 1,424 |
| DRT総VKT | 129.757827 km |
| 空車VKT | 103.652441 km |
| 到着時刻P95 | 9,938 sec |
| event | 1,547 |
| Warning / Error | 1,321 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 20. B2 seed 101

`JDRT-B2` seed 101を18番目のセルとして実行した。run IDは`core_v2_b2_seed101_20261009_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 42 / 3,213 |
| Type4 / Type3避難完了 | 13 / 29 |
| 完了 / 立ち往生request | 17 / 1,423 |
| DRT総VKT | 103.910107 km |
| 空車VKT | 69.769975 km |
| 到着時刻P95 | 18,322 sec |
| event | 1,551 |
| Warning / Error | 1,439 / 1 |
| 捕捉済み / 未処理Error | 1 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 21. P1 seed 101

`JDRT-P1` seed 101を19番目のセルとして実行した。run IDは`core_v2_p1_seed101_20261015_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 22 / 3,233 |
| Type4 / Type3避難完了 | 17 / 5 |
| 完了 / 立ち往生request | 7 / 1,433 |
| DRT総VKT | 63.826115 km |
| 空車VKT | 43.026289 km |
| 到着時刻P95 | 8,375 sec |
| event | 1,495 |
| Warning / Error | 1,205 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。全20セル完了前の方向判断は行わない。

## 22. P2-L15 seed 101

`JDRT-P2-L15` seed 101を20番目のセルとして実行した。run IDは`core_v2_p2_l15_seed101_20261015_skill01`、manifestは`COMPLETED`、`summary.valid=true`だった。

| 項目 | 実測 |
|---|---:|
| controller / observation | 21,600 / 43,200 |
| 避難完了 / 立ち往生 | 10 / 3,245 |
| Type4 / Type3避難完了 | 6 / 4 |
| 完了 / 立ち往生request | 5 / 1,435 |
| DRT総VKT | 59.043182 km |
| 空車VKT | 33.841274 km |
| 到着時刻P95 | 3,778 sec |
| event | 1,482 |
| Warning / Error | 1,158 / 5 |
| 捕捉済み / 未処理Error | 5 / 0 |
| teleport / collision | 0 / 0 |

Parameter SHA 1/1、入力SHA 8/8、出力SHA 9/9、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。これで中核20セルが全て揃った。

## 23. 中核20セル完了

全セルの集計・頑健性評価へ進む。
