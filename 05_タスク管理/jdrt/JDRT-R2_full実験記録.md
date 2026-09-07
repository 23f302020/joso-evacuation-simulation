# JDRT-R2 full実験記録

> 対象：常総市（08211）  
> 方式：JDRT-B3 / JDRT-P1 / JDRT-P2-L15  
> 状態：正式0/15セル、invalid試行1件を保全、PAPゲートで技術停止  
> 正本：各runの `manifest.json` と一次出力

## 実行規則

- B3、P1、P2-L15をこの順に、各方式seed `23423, 42, 1, 7, 101`で1セルずつ実行する。
- manifest、人物・request会計、Parameter・8入力SHA、event SHA、全9出力SHA、未処理SUMO Error、teleportを確認してから次へ進む。
- `summary.valid=false`のrunは正式セルへ数えず、削除・上書きしない。
- R2全15セルとJDRT-E1が完了するまで方式間の方向判断を行わない。

## 実行履歴

| 試行 | scenario | seed | run ID | 状態 | teleport | 未処理Error | 扱い |
|---:|---|---:|---|---|---:|---:|---|
| 1 | JDRT-B3 | 23423 | `core_b3_seed23423_20260826_codex01` | INVALID | 4 | 0 | 正式比較から除外し保全 |

## B3 seed 23423 初回invalid記録（2026-08-26）

preflightで常総市08211、SUMO 1.26.0、WaitingVulnerabilityDispatcher、人物3,255、request 1,440、DRT車両5、自家用車8,164、入力SHA 8件を確認し、`core_b3_seed23423_20260826_codex01`を単独実行した。

- manifest：`status=INVALID`、`summary.valid=false`
- invalid理由：自家用車4台のside collision teleport
- 人物保存則：避難46、立ち往生3,209、active 0、cancelled 0、合計3,255
- Type別：Type4 41/935、Type3 5/2,320
- request：完了16、立ち往生1,424、合計1,440
- DRT走行：総VKT 105.49342870822898 km、空車VKT 78.3337838243212 km
- 道路閉鎖：最終8,968 edge
- SUMOログ：Warning 1,407、Error総数4、controller捕捉済みroute拒否4、未処理Error 0
- event：manifest 1,538行＝実ファイル1,538行、SHA一致
- `person_results.csv` 3,255行、`request_results.csv` 1,440行
- manifest記載の9出力ファイルは全SHA一致
- Parameter SHAと8入力SHAは同seed B2正式runと一致

人物・request会計とSHAは成立したが、PAPのteleport 0ゲートに反するため正式セルには採用しない。結果値は方式比較・方向判断に使用しない。run一式をそのまま保全し、SUMO衝突設定、同一seed決定性、Dispatcher差による交通状態変化を診断する。

## 技術診断と判断（2026-08-26）

SUMO公式資料と一次ファイルを照合した。

- SUMOは同一version・引数・入力・seedで原則として決定的であり、無変更再実行は同じ衝突を再現する見込みが高い。
- `time-to-teleport=-1`はgridlock起因teleportだけを無効にする。衝突時の既定`collision.action`は`teleport`である。
- 4件は時刻3,954〜4,229秒、同じ内部lane `:12615788254_0_1` 上の自家用車同士のside collisionであり、全て実在する負のgapを伴う。
- B2/B3のprivate route SHA、初期bus route SHA、Parameter SHA、8入力SHA、SUMO seedは一致する。差はDispatcherによる走行中の交通状態である。
- 衝突actionを`warn`または`none`へ変える案は衝突を隠してteleport 0だけを満たすため却下する。
- seed置換はpaired seedの事前固定に反する。無変更再実行も採用runを得る合理的根拠がない。
- 時間刻み、network、vTypeを修正する場合は全方式共通条件が変わるため、完了済みB2を含む中核20セルを新しい版として最初から再実行する必要がある。

参照した公式資料：

- [SUMO Safety](https://sumo.dlr.de/docs/Simulation/Safety.html)
- [SUMO Randomness / Reproducibility](https://sumo.dlr.de/docs/Simulation/Randomness.html)
- [Why Vehicles are teleporting](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html)

結果観測後にPAPのteleport 0基準を緩和すると方式依存の技術事象を事後採用することになるため、現runを正式化しない。現PAPのままJDRT-R2を技術停止する。

## 再開条件

共通シミュレーション条件の再設計と、B2を含む中核20セル全体を新versionで再実行する明示判断が得られた場合に限り再開する。現在のB2正式5runとB3 invalid runは削除せず旧versionとして保全する。
