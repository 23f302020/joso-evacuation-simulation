# 常総市JDRT v2 実装記録

> 実装日：2026-08-26  
> 対象：常総市（08211）のみ  
> タスク：JDRT-V2-I1  
> 状態：完了・後続のB3 seed 23423技術ゲートPASS

## 1. 目的

v1のrunと出力を変更せず、`jdrt_parameters_v2.json`を明示指定したときだけ0.5秒刻みのv2を実行できるようにする。衝突を隠さず、v1/v2の正式セルを混同しないことを最優先とした。

## 2. 実装内容

- CLIへ`--protocol-version {v1,v2}`を追加し、既定はv1のまま維持した。
- v1/v2の設定ファイルをprotocolから解決し、preflightと本実行で同じファイルを読むようにした。
- completedセルの重複判定をscenario＋seedだけでなくParameter SHA単位へ変更した。
- v2設定からSUMO step length 0.5秒、controller interval 1.0秒、collision action teleport、time-to-teleport -1を取得・検証するようにした。
- SUMOは0.5秒ずつ進め、controllerは整数秒に1回だけ実行する。離脱、到着、teleport、走行距離は各0.5秒ステップで観測する。
- `sumo_error.log`からcollision teleportとgridlock teleportを分離集計する。
- collision teleport 0、controller 21,600回、技術観測43,200回をv2のvalid条件へ追加した。
- manifest、CORE_RUN_STARTED event、metricsへprotocol、parameter version、simulation設定、実行・観測回数を保存する。
- `metrics.json`はSUMO終了後に衝突件数を取得してから一度だけ書き出す。

## 3. 変更ファイル

- `04_プログラム/scripts/jdrt/full_run.py`
- `04_プログラム/tests/unit/test_jdrt_full_run.py`
- `04_プログラム/config/jdrt_parameters_v2.json`

既存Phase 1〜3、Scenario C、Phase 3の`step_bus`、v1 run出力は変更していない。

## 4. 検証結果

| 検証 | 結果 |
|---|---|
| Python構文検査 | PASS |
| `test_jdrt_full_run.py` | 10 passed |
| unit全体 | 171 passed |
| v2 preflight | READY |
| city | 08211 |
| SUMO | 1.26.0 |
| 人物 / request / DRT / private | 3,255 / 1,440 / 5 / 8,164 |
| 入力SHA件数 | 8 |
| Parameter version | `jdrt-v2-20260826` |
| Parameter SHA-256 | `c878760eeff72b47110784f17bd98856dc292dd2fcb98636a42c632f6507b411` |
| step / controller | 0.5秒 / 1.0秒 |
| collision action | teleport |

SUMO 1.26.0の`--help`でも`--step-length`、`--collision.action`、`--time-to-teleport`が認識されることを確認した。

## 5. 次のゲート

`JDRT-B3` seed 23423を`--protocol-version v2`で1セルだけ実行する。COMPLETEDかつtechnical valid、teleport 0、collision teleport 0、未処理Error 0、controller 21,600回、技術観測43,200回、人物・request・SHA会計一致を独立検証する。不合格ならv2内で追加調整せず停止する。

2026-08-26に`core_v2_b3_seed23423_20260826_codex01`を実行し、全条件を満たした。詳細は`JDRT-v2_full実験記録.md`。このセルをv2中核1/20として採用し、実行器タスクの後続ゲートも成立した。
