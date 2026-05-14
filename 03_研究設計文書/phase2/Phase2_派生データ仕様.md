# Phase 2 派生データ仕様

作成日：2026/05/14  
対象：Phase 2 自家用車避難 SUMO / TraCI ベースライン

---

## 1. 目的

Phase 2では、Phase 1で作成済みの道路ネットワーク、道路閉鎖時系列、人口メッシュ、避難所データをそのままSUMOへ投入できない。

そのため、実装前仕様で確定した判断に基づき、次の派生データを作成する。

| 派生データ | 目的 | 作成時期 |
|---|---|---|
| `shelters_safety.csv` | 避難所が浸水リスクを持つか判定し、安全な目的地だけを使う | SUMO投入前 |
| `agent_origins_10pct.csv` | メッシュ人口から自家用車台数を推定し、1/10試行用台数を作る | SUMO投入前 |
| `time_mapping_sumo.csv` | Phase 1のt0〜t7をSUMO秒に対応させる | SUMO投入前 |
| `edge_id_mapping.csv` | Phase 1 edge ID と SUMO edge ID を対応させる | SUMO変換後 |
| `closure_timeline_sumo.json` | 閉鎖時系列をSUMO edge ID基準へ変換する | edge対応後 |
| `agent_origins_sumo.csv` | 出発地メッシュをSUMO edgeへスナップする | SUMO変換後 |
| `shelters_sumo.csv` | 安全避難所をSUMO edgeへスナップする | SUMO変換後 |

---

## 2. 保存先

| 種別 | 保存先 |
|---|---|
| 派生CSV / JSON | `04_プログラム/output/sumo/derived/` |
| SUMOネットワーク | `04_プログラム/output/sumo/network/` |
| シナリオXML | `04_プログラム/output/sumo/scenarios/` |
| 実行結果CSV | `04_プログラム/output/sumo/results/` |

---

## 3. `shelters_safety.csv`

避難所浸水リスクを判定する表。Phase 2の目的地は、原則として `is_safe_destination = true` の避難所に限定する。

| 列名 | 型 | 内容 |
|---|---|---|
| `shelter_id` | string | Phase 1で使う避難所ID。未設定の場合は連番 |
| `name` | string | 避難所名 |
| `capacity` | integer / blank | 収容人数。原データにない場合は空欄 |
| `lon` | float | 経度 |
| `lat` | float | 緯度 |
| `flood_risk` | boolean | A31a最大浸水範囲と重なる場合 true |
| `max_water_depth_code` | integer / blank | 重なるA31a `waterDepth` の最大コード |
| `is_safe_destination` | boolean | Phase 2の目的地として採用する場合 true |
| `exclusion_reason` | string / blank | 除外理由。例：`flood_risk_water_depth_ge_2` |
| `notes` | string / blank | 手作業確認や例外の記録 |

採用判断：

- A31a `waterDepth >= 2` と重なる避難所は、原則として目的地から除外する。
- 浸水リスクのない避難所だけを目的地にすることで、卒論上は「避難所到着」ではなく「安全な避難所到着」と説明できる。
- 除外した避難所も表には残し、除外理由を追跡できるようにする。

---

## 4. `agent_origins_10pct.csv`

出発地メッシュごとの車両台数を定義する表。小規模テスト、1/10試行、全量試行を同じ表から生成する。

| 列名 | 型 | 内容 |
|---|---|---|
| `origin_id` | string | 出発地ID |
| `KEY_CODE` | string | 250mメッシュコード |
| `lon` | float | メッシュ代表点の経度 |
| `lat` | float | メッシュ代表点の緯度 |
| `total_pop` | integer | 総人口 |
| `elderly_pop` | integer | 65歳以上人口 |
| `estimated_households` | float | `total_pop / 2.3` |
| `vehicle_count_full` | integer | 全量試行の投入車両数 |
| `vehicle_count_10pct_raw` | float | `vehicle_count_full / 10` |
| `vehicle_count_10pct` | integer | 1/10試行の投入車両数。人口があるメッシュは最低1台 |
| `vehicle_count_small` | integer | 小規模テスト用。人口があるメッシュは1台 |
| `notes` | string / blank | 丸め処理などの記録 |

採用判断：

- 1/10試行はメッシュを抽出せず、全メッシュを保持して車両数だけを減らす。
- これにより、浸水範囲内の空間分布を崩さずに計算負荷だけを下げる。
- 全量台数は初期値として世帯換算 `total_pop / 2.3` を使う。車両保有台数との市全体補正は、初回SUMO成功後に必要なら追加する。

---

## 5. `time_mapping_sumo.csv`

Phase 1のt0〜t7を、6時間SUMOシミュレーションへ圧縮する対応表。

| 列名 | 型 | 内容 |
|---|---|---|
| `time_id` | string | `t0`〜`t7` |
| `source_timestamp` | datetime | Phase 1の元時刻 |
| `elapsed_sec_real` | integer | 破堤時刻からの実経過秒 |
| `sim_time_sec` | integer | SUMO上の時刻秒 |
| `compression_ratio` | float | `sim_time_sec / elapsed_sec_real` |
| `notes` | string / blank | t0以前・t7終端などの補足 |

採用済みのSUMO秒：

| time_id | 元時刻 | SUMO秒 |
|---|---:|---:|
| t0 | 2015-09-10 18:00 | 789 |
| t1 | 2015-09-11 06:00 | 2,620 |
| t2 | 2015-09-11 18:00 | 4,452 |
| t3 | 2015-09-12 06:00 | 6,284 |
| t4 | 2015-09-12 18:00 | 8,116 |
| t5 | 2015-09-13 06:00 | 9,948 |
| t6 | 2015-09-13 18:00 | 11,780 |
| t7 | 2015-09-16 10:20 | 21,600 |

---

## 6. `phase1_edge_osm_way_mapping.csv`（中間ファイル）

`p2_sumo_network.py export-osm` が `joso.osm.xml` と同時に出力する中間ファイル。  
OSM XMLに書き込んだ way ID（`phase2_osm_way_id`）とPhase 1 edge IDの対応を保持し、`netconvert` 後の `edge_id_mapping.csv` 生成の基盤となる。

| 列名 | 型 | 内容 |
|---|---|---|
| `phase1_edge_id` | string | `{u}_{v}_{key}` 形式のPhase 1エッジID |
| `u` | integer | 始点ノードID |
| `v` | integer | 終点ノードID |
| `key` | integer | MultiDiGraph のキー |
| `osmid` | string | OSMnx が持つ元のOSM way ID（リスト文字列の場合あり） |
| `phase2_osm_way_id` | integer | OSM XML書き込み時に付与した連番 way ID |
| `highway` | string | 道路種別 |
| `oneway` | string | `yes` 固定（有向グラフ全エッジを一方通行として出力） |
| `length` | float | エッジ長（m） |
| `has_geometry` | boolean | shapelyジオメトリが存在するか |
| `geometry_point_count` | integer | ジオメトリの点数 |

保存先：`04_プログラム/output/sumo/derived/phase1_edge_osm_way_mapping.csv`

採用判断：
- OSM XML出力時に `phase2_osm_way_id` をタグとして way 要素へ埋め込み、`netconvert` 後のSUMO edge IDと `phase2_osm_way_id` を突き合わせることで `edge_id_mapping.csv` を生成する。
- このCSVが欠損した場合、`edge_id_mapping.csv` の自動生成は不可能になる。

---

## 7. `edge_id_mapping.csv`

Phase 2最大の確認対象。Phase 1の道路閉鎖エッジを、SUMOのedgeへ対応させる。

| 列名 | 型 | 内容 |
|---|---|---|
| `phase1_edge_id` | string | Phase 1側のエッジID |
| `u` | string | GraphML / OSMnx の始点ノード |
| `v` | string | GraphML / OSMnx の終点ノード |
| `key` | string / integer | MultiDiGraphのkey |
| `osmid` | string | OSM way IDまたはリスト |
| `sumo_edge_id` | string | SUMO変換後のedge ID |
| `mapping_method` | string | `direct_id`, `osmid`, `geometry_nearest`, `manual` など |
| `mapping_status` | string | `matched`, `ambiguous`, `unmatched`, `manual_checked` |
| `notes` | string / blank | 分割edge、逆方向edge、手動確認の記録 |

採用判断：

- まずGraphMLからOSM XMLへ変換する段階で、`u`, `v`, `key`, `osmid` を保持できる形式にする。
- `netconvert` 後にSUMO edge IDが変わる可能性があるため、必ず対応表を作る。
- `mapping_status != matched` の閉鎖対象edgeが残る場合は、TraCI閉鎖実装へ進まない。

---

## 7. `closure_timeline_sumo.json`

`road_closure_timeline.json` をSUMO edge ID基準に変換したファイル。

想定構造：

```json
{
  "metadata": {
    "source": "road_closure_timeline.json",
    "edge_mapping": "edge_id_mapping.csv",
    "time_mapping": "time_mapping_sumo.csv",
    "closure_rule": "A31a waterDepth >= 2",
    "sim_duration_sec": 21600
  },
  "closures": [
    {
      "time_id": "t0",
      "sim_time_sec": 789,
      "closed_sumo_edge_ids": ["edge_001", "edge_002"],
      "unmapped_phase1_edge_ids": []
    }
  ]
}
```

採用判断：

- TraCIで直接使うファイルはSUMO edge IDだけを持たせる。
- 対応漏れは `unmapped_phase1_edge_ids` に残し、実行前チェックで停止できるようにする。

---

## 8. `agent_origins_sumo.csv`

出発地メッシュ代表点をSUMO edgeへスナップした表。

| 列名 | 型 | 内容 |
|---|---|---|
| `origin_id` | string | 出発地ID |
| `KEY_CODE` | string | 250mメッシュコード |
| `lon` | float | 元の経度 |
| `lat` | float | 元の緯度 |
| `sumo_edge_id` | string | スナップ先SUMO edge |
| `snap_distance_m` | float | スナップ距離 |
| `vehicle_count_small` | integer | 小規模テスト台数 |
| `vehicle_count_10pct` | integer | 1/10試行台数 |
| `vehicle_count_full` | integer | 全量台数 |
| `snap_status` | string | `matched`, `far`, `unmatched` |

---

## 9. `shelters_sumo.csv`

安全避難所をSUMO edgeへスナップした表。

| 列名 | 型 | 内容 |
|---|---|---|
| `shelter_id` | string | 避難所ID |
| `name` | string | 避難所名 |
| `lon` | float | 経度 |
| `lat` | float | 緯度 |
| `capacity` | integer / blank | 収容人数 |
| `is_safe_destination` | boolean | 目的地採用可否 |
| `sumo_edge_id` | string | スナップ先SUMO edge |
| `snap_distance_m` | float | スナップ距離 |
| `snap_status` | string | `matched`, `far`, `unmatched` |

---

## 10. 実装前チェック

実装へ入る前に、次を確認する。

| 確認項目 | 通過条件 |
|---|---|
| 安全避難所 | `is_safe_destination = true` の避難所が1件以上ある |
| 1/10車両 | 人口があるメッシュの `vehicle_count_10pct` が0にならない |
| 時間対応 | `sim_time_sec` が0〜21,600秒に収まる |
| edge対応 | 閉鎖対象の `mapping_status` が全て `matched` または `manual_checked` |
| 出発地スナップ | `snap_status = unmatched` がない |
| 避難所スナップ | 採用避難所の `snap_status = unmatched` がない |

