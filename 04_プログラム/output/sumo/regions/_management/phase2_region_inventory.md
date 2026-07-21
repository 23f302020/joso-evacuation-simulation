# Phase 2 全域拡張 対象地域・入力データ棚卸し

- 生成日時: 2026-05-15 13:25:10
- 全市区町村管理単位: 44 件
- Phase 2 全域拡張対象: 41 件
- 事前確認OK: 41 件
- Phase 1 対象外として保持: 3 件

## 採用判断

Phase 2 の「対象地域全域」は、Phase 1 で成果物化した 41 市区町村とする。鹿嶋市・神栖市・東海村は Phase 1 で洪水浸水想定データの対象外として整理済みであるため、Phase 2 の初回全域拡張にも含めない。

この判断は、Phase 2 の目的が自家用車避難を SUMO 上で再現し、Phase 1 の閉鎖道路・避難経路探索成果と比較可能にすることであるためである。Phase 1 に浸水シナリオと閉鎖道路が存在しない地域を混ぜると、交通挙動の差ではなく入力データ有無の差が比較結果に入る。

## 出力管理方針

- 地域別SUMO成果物は `output/sumo/regions/{city_code}/` に集約する。
- 地域別ディレクトリ配下は `network/`, `derived/`, `scenarios/`, `results/`, `viz/` に分ける。
- 既存の常総市単独SUMO成果物 `output/sumo/` は当面維持し、全域拡張版は `regions/` 以下に分離する。

## 生成ファイル

- `output/sumo/regions/_management/phase2_region_targets.csv`
- `output/sumo/regions/_management/phase2_region_inventory.csv`
- `output/sumo/regions/_management/phase2_region_inventory.md`

## 追加確認が必要な対象

現時点では Phase 2 対象41件すべてで前提ファイルが揃っている。

## Phase 2 対象地域

| コード | 市区町村 | A31a | 事前確認 | Phase2出力先 |
| --- | --- | --- | --- | --- |
| 08201 | 水戸市 | 08_10+08_20 | yes | output/sumo/regions/08201 |
| 08202 | 日立市 | 08_10 | yes | output/sumo/regions/08202 |
| 08203 | 土浦市 | 08_20 | yes | output/sumo/regions/08203 |
| 08204 | 古河市 | 08_20 | yes | output/sumo/regions/08204 |
| 08205 | 石岡市 | 08_10+08_20 | yes | output/sumo/regions/08205 |
| 08207 | 結城市 | 08_10+08_20 | yes | output/sumo/regions/08207 |
| 08208 | 龍ケ崎市 | 08_20 | yes | output/sumo/regions/08208 |
| 08210 | 下妻市 | 08_20 | yes | output/sumo/regions/08210 |
| 08211 | 常総市 | 08_10+08_20 | yes | output/sumo/regions/08211 |
| 08212 | 常陸太田市 | 08_10+08_20 | yes | output/sumo/regions/08212 |
| 08214 | 高萩市 | 08_10 | yes | output/sumo/regions/08214 |
| 08215 | 北茨城市 | 08_10 | yes | output/sumo/regions/08215 |
| 08216 | 笠間市 | 08_10+08_20 | yes | output/sumo/regions/08216 |
| 08217 | 取手市 | 08_20 | yes | output/sumo/regions/08217 |
| 08219 | 牛久市 | 08_20 | yes | output/sumo/regions/08219 |
| 08220 | つくば市 | 08_10+08_20 | yes | output/sumo/regions/08220 |
| 08221 | ひたちなか市 | 08_10+08_20 | yes | output/sumo/regions/08221 |
| 08223 | 潮来市 | 08_10 | yes | output/sumo/regions/08223 |
| 08224 | 守谷市 | 08_20 | yes | output/sumo/regions/08224 |
| 08225 | 常陸大宮市 | 08_10+08_20 | yes | output/sumo/regions/08225 |
| 08226 | 那珂市 | 08_10+08_20 | yes | output/sumo/regions/08226 |
| 08227 | 筑西市 | 08_10+08_20 | yes | output/sumo/regions/08227 |
| 08228 | 坂東市 | 08_20 | yes | output/sumo/regions/08228 |
| 08229 | 稲敷市 | 08_10+08_20 | yes | output/sumo/regions/08229 |
| 08230 | かすみがうら市 | 08_10+08_20 | yes | output/sumo/regions/08230 |
| 08231 | 桜川市 | 08_10+08_20 | yes | output/sumo/regions/08231 |
| 08233 | 行方市 | 08_10+08_20 | yes | output/sumo/regions/08233 |
| 08234 | 鉾田市 | 08_10+08_20 | yes | output/sumo/regions/08234 |
| 08235 | つくばみらい市 | 08_10+08_20 | yes | output/sumo/regions/08235 |
| 08236 | 小美玉市 | 08_10+08_20 | yes | output/sumo/regions/08236 |
| 08302 | 茨城町 | 08_10+08_20 | yes | output/sumo/regions/08302 |
| 08309 | 大洗町 | 08_20 | yes | output/sumo/regions/08309 |
| 08310 | 城里町 | 08_10+08_20 | yes | output/sumo/regions/08310 |
| 08364 | 大子町 | 08_10 | yes | output/sumo/regions/08364 |
| 08442 | 美浦村 | 08_20 | yes | output/sumo/regions/08442 |
| 08443 | 阿見町 | 08_20 | yes | output/sumo/regions/08443 |
| 08447 | 河内町 | 08_20 | yes | output/sumo/regions/08447 |
| 08521 | 八千代町 | 08_20 | yes | output/sumo/regions/08521 |
| 08542 | 五霞町 | 08_20 | yes | output/sumo/regions/08542 |
| 08546 | 境町 | 08_20 | yes | output/sumo/regions/08546 |
| 08564 | 利根町 | 08_20 | yes | output/sumo/regions/08564 |

## Phase 1 対象外として保持する地域

| コード | 市区町村 | 理由 |
| --- | --- | --- |
| 08222 | 鹿嶋市 | 対象外(沿岸・汽水域:河川洪水想定なし) |
| 08232 | 神栖市 | 対象外(利根川河口・沿岸:利根川系A31a未収録) |
| 08341 | 東海村 | 対象外(海岸段丘台地:那珂川浸水域が市境外止まり) |

## 次に行う実装

1. `phase2_region_targets.csv` を入力として、地域別に SUMO ネットワーク変換を行う。
2. 地域別に閉鎖道路・人口重み付き出発需要・避難所目的地を SUMO 用データへ変換する。
3. まず代表3地域で動作確認し、その後41市区町村のバッチ実行に広げる。
