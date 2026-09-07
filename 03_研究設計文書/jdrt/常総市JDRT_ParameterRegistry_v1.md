# 常総市JDRT Parameter Registry v1

> 固定日：2026-08-11  
> 状態：正式固定・実験未実施  
> 機械可読正本：`04_プログラム/config/jdrt_parameters_v1.json`

| ID | 名称 | 正式値 | 単位 | 区分 | 不確実性 | 感度 | 根拠・注意 |
|---|---|---:|---|---|---|---|---|
| JPR-P001 | city_code | 08211 | code | 公的 | 低 | なし | 常総市のみ |
| JPR-P002 | population | 21,539 | 人 | GIS派生 | 中 | なし | `agent_types.csv` |
| JPR-P003 | origin_count | 405 | 地点 | GIS派生 | 低 | なし | 全地点routable |
| JPR-P004 | Type3 | 2,320 | 人 | 推定 | 高 | 別研究扱い | 非車保有15%仮定を含む |
| JPR-P005 | Type4 | 935 | 人 | 推定 | 高 | 別研究扱い | Primary Outcome分母 |
| JPR-D101 | DRT対象 | Type3/4 | 分類 | 政策操作 | 高 | Type4 onlyは将来 | 主分析固定 |
| JPR-D102 | DRT利用率 | 100 | % | 行動仮定 | 高 | なし | 上限需要ケース |
| JPR-D103 | DRT対象人数 | 3,255 | 人 | 派生 | 高 | なし | Type3+Type4 |
| JPR-D104 | request_count | 1,440 | 件 | 派生 | 中 | なし | 定員内の決定的分割 |
| JPR-D105 | request_time | 0 | 秒 | 行動仮定 | 高 | Early/Lateは後段 | 一斉避難 |
| JPR-D106 | rescue substitution | 1,405 | 台 | 政策操作 | 高 | なし | JDRT条件では救出走行を生成しない |
| JPR-D107 | private cars | 8,164 | 台 | 既存派生 | 中 | なし | 全JDRT方式で固定 |
| JPR-V201 | fleet | 5 | 台 | 政策操作 | 中 | 3 / 10 | 既存基準 |
| JPR-V202 | standard vehicles | 4 | 台 | 運用仮定 | 中 | fleetに連動 | capacity 8 |
| JPR-V203 | welfare vehicles | 1 | 台 | 運用仮定 | 中 | fleetに連動 | capacity 4 |
| JPR-V204 | standard capacity | 8 | 人 | 運用仮定 | 中 | なし | 既存基準 |
| JPR-V205 | welfare capacity | 4 | 人 | 運用仮定 | 高 | なし | 既存基準 |
| JPR-V206 | boarding | 300 | 秒 | 運用仮定 | 高 | なし | 既存基準 |
| JPR-V207 | alighting | 300 | 秒 | 運用仮定 | 高 | なし | 既存基準 |
| JPR-V208 | initial edges | bus_plan 5件 | edge | 既存派生 | 中 | なし | 方式間固定 |
| JPR-C301 | dispatch interval | 60 | 秒 | 技術仮定 | 中 | なし | 1秒制御より計算量を抑制 |
| JPR-C302 | travel-time refresh | 60 | 秒 | 技術仮定 | 中 | なし | dispatchと同期 |
| JPR-C303 | assignment lock | true | bool | 設計判断 | 低 | なし | 再割当なし |
| JPR-C304 | pooling | false | bool | 設計判断 | 低 | Optional | 1 pickup→shelter |
| JPR-C305 | safety margin | 300 | 秒 | 配車方針 | 中 | 180 / 600 | 主分析固定 |
| JPR-C306 | waiting weight | 1.0 | 無次元 | 政策判断 | 中 | 後段のみ | 候補集合内正規化 |
| JPR-C307 | vulnerability weight | 1.0 | 無次元 | 政策判断 | 中 | 後段のみ | B3/P1/P2共通 |
| JPR-C308 | pickup weight | 1.0 | 無次元 | 政策判断 | 中 | 後段のみ | B3/P1/P2共通 |
| JPR-C309 | flood weight | 1.0 | 無次元 | 政策判断 | 中 | 後段のみ | P1/P2のみ |
| JPR-F401 | P1 error | 0 | 秒 | 理論条件 | 低 | なし | 理論上限 |
| JPR-F402 | P2 primary error | +900 | 秒 | 操作変数 | 中 | ±1800 / ±3600 | Late Forecast |
| JPR-F403 | Spatial error | 使用しない | — | 範囲外 | — | Optional | 時間誤差だけを扱う |
| JPR-S501 | shelter set | 9 | 施設 | 既存派生 | 中 | なし | safe・routable |
| JPR-S502 | shelter choice | origin固定 | rule | 設計判断 | 中 | なし | `rescue_od.csv` |
| JPR-S503 | shelter capacity | 制約なし | rule | 仮定 | 高 | 将来 | capacity=0を不明値と解釈 |
| JPR-S504 | active interval | 0〜21,600 | 秒 | 仮定 | 中 | なし | 全施設 |
| JPR-R601 | seeds | 23423,42,1,7,101 | 整数 | 実験設計 | 低 | なし | paired 5seed |
| JPR-R602 | simulation end | 21,600 | 秒 | 既存条件 | 低 | なし | 6時間 |
| JPR-R603 | primary outcome | Type4 success | rate | 実験設計 | 低 | なし | 分母935人 |

正式値は結果確認後に変更しない。誤記訂正または入力SHA不一致による改訂は版番号を上げ、変更理由と影響runを記録する。
