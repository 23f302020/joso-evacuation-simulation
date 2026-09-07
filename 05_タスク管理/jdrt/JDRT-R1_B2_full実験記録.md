# JDRT-R1 B2 full実験記録

> 対象：常総市（08211）  
> 方式：JDRT-B2 Dynamic Travel-Time  
> 状態：正式5/5 seed完了・JDRT-R1完了  
> 正本：各runの `manifest.json` と一次出力

## 実行規則

- paired seedは`23423, 42, 1, 7, 101`とする。
- 1セルずつ実行し、manifest、人物・request会計、Parameter・8入力SHA、event SHA、出力SHA、未処理SUMO Error、teleportを確認してから次へ進む。
- invalid/failed runは削除しない。
- B2単独または途中seedの値から方式間の方向比較を行わない。

## 進捗

| seed | run ID | 状態 | 避難完了 | Type4 | 完了request | DRT総VKT | teleport | 未処理Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 23423 | `core_b2_seed23423_20260811_codex10` | COMPLETED / valid | 18 / 3,255 | 7 / 935 | 6 / 1,440 | 30.178350 km | 0 | 0 |
| 42 | `core_b2_seed42_20260826_codex01` | COMPLETED / valid | 21 / 3,255 | 7 / 935 | 7 / 1,440 | 22.376323 km | 0 | 0 |
| 1 | `core_b2_seed1_20260826_codex01` | COMPLETED / valid | 18 / 3,255 | 7 / 935 | 6 / 1,440 | 20.992360 km | 0 | 0 |
| 7 | `core_b2_seed7_20260826_codex01` | COMPLETED / valid | 19 / 3,255 | 9 / 935 | 7 / 1,440 | 35.137077 km | 0 | 0 |
| 101 | `core_b2_seed101_20260826_codex01` | COMPLETED / valid | 24 / 3,255 | 9 / 935 | 8 / 1,440 | 33.820620 km | 0 | 0 |

## seed 42 検証記録（2026-08-26）

正式runは`core_b2_seed42_20260826_codex01`である。preflightで常総市08211、SUMO 1.26.0、DynamicTravelTimeDispatcher、人物3,255、request 1,440、DRT車両5、自家用車8,164、8入力SHAを確認してから単独実行した。

終了後の独立再計算で次を確認した。

- manifest：`status=COMPLETED`、`summary.valid=true`
- 人物保存則：避難21、立ち往生3,234、active 0、cancelled 0、合計3,255
- Type別：Type4 7/935、Type3 14/2,320
- request：完了7、立ち往生1,433、合計1,440
- DRT走行：総VKT 22.37632271026174 km、空車VKT 8.248484466189906 km
- 道路閉鎖：最終8,968 edge
- teleport：0
- SUMOログ：Warning 1,156、Error総数1、controller捕捉済みroute拒否1、未処理Error 0
- event：manifest 1,498行＝実ファイル1,498行、SHA一致
- `person_results.csv` 3,255行、`request_results.csv` 1,440行
- manifest記載の9出力ファイルは全SHA一致
- Parameter SHAと8入力SHAはseed 23423の正式runと一致

route拒否1件はPAP 13節の技術的明確化に該当し、controllerが理由付き終端として処理した。未処理Error 0、人物保存則、teleport 0が同時成立しているため正式採用する。Warningと捕捉済みErrorは削除・非表示にしない。

## seed 1 検証記録（2026-08-26）

正式runは`core_b2_seed1_20260826_codex01`である。preflightで正式条件との一致を確認してから単独実行した。

- manifest：`status=COMPLETED`、`summary.valid=true`
- 人物保存則：避難18、立ち往生3,237、active 0、cancelled 0、合計3,255
- Type別：Type4 7/935、Type3 11/2,320
- request：完了6、立ち往生1,434、合計1,440
- DRT走行：総VKT 20.99236007187704 km、空車VKT 7.743669610151735 km
- 道路閉鎖：最終8,968 edge
- teleport：0
- SUMOログ：Warning 1,648、Error総数2、controller捕捉済みroute拒否2、未処理Error 0
- event：manifest 1,495行＝実ファイル1,495行、SHA一致
- `person_results.csv` 3,255行、`request_results.csv` 1,440行
- manifest記載の9出力ファイルは全SHA一致
- Parameter SHAと8入力SHAは既存正式runと一致

route拒否2件はいずれもPAP 13節の技術的明確化に該当する。未処理Error 0、人物保存則、teleport 0が同時成立しているため正式採用する。

## seed 7 検証記録（2026-08-26）

正式runは`core_b2_seed7_20260826_codex01`である。preflightで正式条件との一致を確認してから単独実行した。

- manifest：`status=COMPLETED`、`summary.valid=true`
- 人物保存則：避難19、立ち往生3,236、active 0、cancelled 0、合計3,255
- Type別：Type4 9/935、Type3 10/2,320
- request：完了7、立ち往生1,433、合計1,440
- DRT走行：総VKT 35.137076957237014 km、空車VKT 19.711375085157776 km
- 道路閉鎖：最終8,968 edge
- teleport：0
- SUMOログ：Warning 1,175、Error総数1、controller捕捉済みroute拒否1、未処理Error 0
- event：manifest 1,499行＝実ファイル1,499行、SHA一致
- `person_results.csv` 3,255行、`request_results.csv` 1,440行
- manifest記載の9出力ファイルは全SHA一致
- Parameter SHAと8入力SHAは既存正式runと一致

route拒否1件はPAP 13節の技術的明確化に該当する。未処理Error 0、人物保存則、teleport 0が同時成立しているため正式採用する。

## seed 101 検証記録（2026-08-26）

正式runは`core_b2_seed101_20260826_codex01`である。preflightで正式条件との一致を確認してから単独実行した。

- manifest：`status=COMPLETED`、`summary.valid=true`
- 人物保存則：避難24、立ち往生3,231、active 0、cancelled 0、合計3,255
- Type別：Type4 9/935、Type3 15/2,320
- request：完了8、立ち往生1,432、合計1,440
- DRT走行：総VKT 33.820619665701244 km、空車VKT 14.948967195332381 km
- 道路閉鎖：最終8,968 edge
- teleport：0
- SUMOログ：Warning 1,386、Error総数1、controller捕捉済みroute拒否1、未処理Error 0
- event：manifest 1,510行＝実ファイル1,510行、SHA一致
- `person_results.csv` 3,255行、`request_results.csv` 1,440行
- manifest記載の9出力ファイルは全SHA一致
- Parameter SHAと8入力SHAは既存正式runと一致

route拒否1件はPAP 13節の技術的明確化に該当する。未処理Error 0、人物保存則、teleport 0が同時成立しているため正式採用する。

## JDRT-R1完了判定

事前固定seed `23423, 42, 1, 7, 101` の5セルはすべて `COMPLETED / valid` となり、人物・request保存則、Parameter・8入力SHA、event行数・SHA、全9出力SHA、teleport 0、未処理Error 0を確認した。B2内の避難完了人数は中央値19人（範囲18〜24人）、Type4避難人数は中央値7人（7〜9人）、完了requestは中央値7件（6〜8件）、DRT総VKTは中央値30.178350km（20.992360〜35.137077km）だった。これはB2の反復記述であり、方式間の方向比較ではない。

## 次のセル

`JDRT-B3 seed 23423`を同じゲートで実行する。
