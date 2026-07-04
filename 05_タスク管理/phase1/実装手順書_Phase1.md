# 実装手順書 — Phase 1

> 作成日：2026/04/28
> 目的：ミスを防ぐための詳細な手順分割と役割分担
> 対象：Phase 1（config / c3 / e1 / i1 / i2 / i3）

---

## 役割定義

| 担当 | 作業内容 | 操作方法 |
|------|---------|---------|
| **Claude Code** | データ確認・出力検証・文書更新・config.py作成 | ファイル読み込み・PowerShellコマンド実行 |
| **Codex**（/codex:rescue） | Pythonスクリプトの実装・デバッグ | `/codex:rescue` に指示文を渡す |
| **ユーザー** | スクリプトの実行・ブラウザでのHTML確認 | ターミナルでコマンド実行 |

---

## 共通：スクリプト実行方法

すべてのスクリプトは `scripts/` ディレクトリから venv の Python で実行する。
config.py の相対パスが `scripts/` 基準になるため、必ずディレクトリを移動してから実行すること。

```powershell
cd "C:\Users\Ko_rr\OneDrive - stu.teikyo-u.ac.jp\研究室\4年次本研究\04_プログラム\scripts"
$python = "..\venv\Scripts\python.exe"
& $python c3_get_road_network.py
```

---

## STEP 0：config.py 作成

**担当：Claude Code（直接作成）**
**前提：** なし
**完了条件：** import が通り、主要定数の値が正しいこと

### 手順

1. **Claude Code が `scripts/config.py` を作成する**
   - 実装仕様書（`03_研究設計文書/共通設計/実装仕様書.md` セクション3）の定数をそのまま書き込む
   - 変更禁止の値：`JOSO_CODE = "08211"`・`FLOOD_DEPTH_THRESHOLD = 2`・`CRS_JGD2011 = "EPSG:6668"`

2. **ユーザーが動作確認を実行する**
   ```powershell
   cd "C:\Users\Ko_rr\OneDrive - stu.teikyo-u.ac.jp\研究室\4年次本研究\04_プログラム\scripts"
   $python = "..\venv\Scripts\python.exe"
   & $python -c "import config; print('JOSO_CODE:', config.JOSO_CODE); print('CRS:', config.CRS_JGD2011)"
   ```

3. **Claude Code が出力を確認する**
   - `JOSO_CODE: 08211` と表示されること
   - `CRS: EPSG:6668` と表示されること

---

## STEP 1a：c3_get_road_network.py（道路ネットワーク取得）

**担当：Codex（/codex:rescue）**
**前提：** STEP 0 完了・インターネット接続あり
**完了条件：** GraphML・GeoPackage・HTML の3ファイルが出力されること

### 手順

1. **Claude Code が入力データの存在を確認する**
   - `output/network/` ディレクトリが存在すること（既作成）
   - venv の osmnx が import できること（既確認）

2. **ユーザーが `/codex:rescue` に以下の指示を渡す**

   ```
   以下の仕様書に従い、scripts/c3_get_road_network.py を実装してください。

   【参照ファイル】
   - 03_研究設計文書/共通設計/実装仕様書.md（セクション5-1）
   - scripts/config.py

   【実装する関数】
   - get_road_network() -> nx.MultiDiGraph
       ox.graph_from_place(config.JOSO_PLACE, network_type=config.OSM_NETWORK_TYPE) で取得
   - save_network(G, path) -> None
       ox.save_graphml() で保存
   - network_to_gdf(G) -> tuple[GeoDataFrame, GeoDataFrame]
       ox.graph_to_gdfs() で変換後、to_crs("EPSG:6668") で座標変換
   - visualize_network(edges_gdf, output_path) -> None
       folium.Map でエッジを GeoJson レイヤーとして描画

   【出力先（scripts/ からの相対パス）】
   - ../output/network/joso_road_network.graphml
   - ../output/network/joso_edges.gpkg
   - ../output/network/joso_network_map.html

   【注意事項】
   - スクリプトは scripts/ ディレクトリから実行される前提でパスを記述すること
   - if __name__ == "__main__": ブロックで全関数を順番に呼び出すこと
   - GraphML が既に存在する場合は API アクセスをスキップしてキャッシュから読み込むこと
   ```

3. **ユーザーがスクリプトを実行する**
   ```powershell
   & $python c3_get_road_network.py
   ```

4. **Claude Code が出力を確認する**
   - `output/network/joso_road_network.graphml` が存在するか
   - `output/network/joso_edges.gpkg` が存在するか
   - エッジ数が数千件以上（常総市の規模として妥当）か
   - `output/network/joso_network_map.html` をブラウザで開き常総市の道路網が描画されているか

5. **エラーが発生した場合**

   | エラー | 対処 |
   |--------|------|
   | `InsufficientResponseError` | place名不認識 → `ox.graph_from_bbox(*config.JOSO_BBOX)` に切り替えを依頼 |
   | `ConnectionError` | ネットワーク不通 → インターネット接続を確認 |
   | その他 | `/codex:rescue` にエラーメッセージを渡してデバッグを依頼 |

---

## STEP 1b：e1_load_flood_data.py（浸水データ読み込み）― 1a と並列実施可

**担当：Codex（/codex:rescue）**
**前提：** STEP 0 完了・以下のデータが存在すること
- `data/flood_hazard_a31/A31a-24_08_10_GML/`（GMLファイル群）
- `data/flood_kml/D1-No917_joso/`（KMLファイル群 8件）

**完了条件：** `flood_polygons.pkl` が出力され、8時点分のポリゴンが含まれること

### 手順

1. **Claude Code が入力データの存在・ファイル数を確認する**
   - GML ディレクトリ内のファイル一覧を確認
   - KML ディレクトリ内のファイル数が8件であることを確認

2. **ユーザーが `/codex:rescue` に以下の指示を渡す**

   ```
   以下の仕様書に従い、scripts/e1_load_flood_data.py を実装してください。

   【参照ファイル】
   - 03_研究設計文書/共通設計/実装仕様書.md（セクション5-2）
   - scripts/config.py

   【データの特性（重要）】
   - KML（D1-No.917）：ジオメトリが LineString のみ。Polygon は存在しない。
     → buffer(0.0001 度 ≈ 10m) を使って Polygon に変換すること
   - A31a GML：ジオメトリが Polygon。属性 ksj:waterDepth がコード値（整数）。
     → waterDepth >= config.FLOOD_DEPTH_THRESHOLD（=2）のポリゴンのみ抽出
   - 両データともに CRS を EPSG:6668 に変換してから intersects 判定を行うこと

   【統合戦略（Option B）】
   A31a の waterDepth>=2 ポリゴンを「閉鎖候補」として確定し、
   各 KML 時点のバッファ Polygon と intersects する A31a ポリゴンのみを
   その時点の浸水ポリゴンとして採用する。

   【実装する関数】
   - load_a31a_gml(gml_dir: str) -> gpd.GeoDataFrame
       geopandas.read_file() で GML 読み込み → waterDepth>=2 でフィルタ → EPSG:6668 に変換
   - load_kml_timeline(kml_dir: str) -> dict[str, gpd.GeoDataFrame]
       KML ファイルをタイムスタンプ順に読み込み → buffer → EPSG:6668 に変換
       キーは config.KML_TIMESTAMPS の順に対応させること
   - build_flood_polygons(a31a, kml_timeline) -> dict[str, gpd.GeoDataFrame]
       各 KML 時点のバッファ Polygon と a31a を sjoin して浸水ポリゴンを構築
   - save_flood_polygons(flood_dict, path) -> None
       pickle.dump() で保存
   - visualize_flood_timeline(flood_dict, output_path) -> None
       folium で時刻ごとに異なる色でポリゴンを描画

   【出力先】
   - ../output/flood/flood_polygons.pkl
   - ../output/flood/flood_timeline_map.html

   【注意事項】
   - pyogrio を使って読み込む（fiona は使わない）
   - KML の driver は 'KML' または 'LIBKML' を明示的に指定すること
   - GML の layer 名は pyogrio.list_layers(path) で事前確認してから layer= に指定すること
   ```

3. **ユーザーがスクリプトを実行する**
   ```powershell
   & $python e1_load_flood_data.py
   ```

4. **Claude Code が出力を確認する**（以下をユーザーに実行してもらう）
   ```powershell
   & $python -c "
   import pickle
   with open('../output/flood/flood_polygons.pkl','rb') as f:
       d = pickle.load(f)
   print('時点数:', len(d))
   for k, gdf in d.items():
       print(f'  {k}: {len(gdf)}件, CRS={gdf.crs}')
   "
   ```
   - 時点数が8であること
   - 各時点のポリゴン件数が0件でないこと
   - CRS が EPSG:6668 であること

5. **エラーが発生した場合**

   | エラー | 対処 |
   |--------|------|
   | `DriverError: unable to open 'KML'` | `driver='LIBKML'` に変更を依頼 |
   | `LayerError` | `pyogrio.list_layers(path)` で実際のレイヤー名を確認してから指定 |
   | 時点数が8未満 | KML ファイルのファイル名パターンを確認して修正を依頼 |
   | 全ポリゴン件数が0 | CRS 変換前に intersects 判定している可能性 → EPSG:6668 統一を確認 |

---

## STEP 2：i1_spatial_join.py（空間照合）

**担当：Codex（/codex:rescue）**
**前提：** STEP 1a・STEP 1b の両方が完了していること
**完了条件：** 時点ごとの閉鎖エッジ数が出力され、時点が進むにつれ増加傾向にあること

### 手順

1. **Claude Code が前提ファイルの存在を確認する**
   - `output/network/joso_edges.gpkg` が存在するか
   - `output/flood/flood_polygons.pkl` が存在するか

2. **ユーザーが `/codex:rescue` に以下の指示を渡す**

   ```
   以下の仕様書に従い、scripts/i1_spatial_join.py を実装してください。

   【参照ファイル】
   - 03_研究設計文書/共通設計/実装仕様書.md（セクション5-3）
   - scripts/config.py

   【実装する関数】
   - load_edges(path: str) -> gpd.GeoDataFrame
       geopandas.read_file() で joso_edges.gpkg を読み込む
   - find_flooded_edges(edges, flood_poly) -> list[str]
       geopandas.sjoin(edges, flood_poly, how='left', predicate='intersects') で照合
       結合されたエッジの (u, v, key) タプルを文字列 "u_v_key" 形式で返す
   - build_closure_dict(edges, flood_dict) -> dict[str, list[str]]
       8時点分について find_flooded_edges を呼び出し辞書を構築して返す

   【重要】
   - 空間演算の前に両 GeoDataFrame の CRS が EPSG:6668 であることを assert で確認すること
     assert edges.crs.to_epsg() == 6668
     assert flood_poly.crs.to_epsg() == 6668
   - エッジIDは "u_v_key" の文字列形式で統一すること（i3 での networkx エッジ削除に使用）
   - 結果の辞書を ../output/closure/closure_dict.pkl に pickle 保存すること
   - 各時点の閉鎖エッジ件数を標準出力に表示すること
   ```

3. **ユーザーがスクリプトを実行する**
   ```powershell
   & $python i1_spatial_join.py
   ```

4. **Claude Code が出力を確認する**
   - 各時点の閉鎖エッジ件数が標準出力に表示されること
   - 件数が時点順に増加傾向にあること
   - `output/closure/closure_dict.pkl` が存在すること
   - 件数が全時点で0件の場合はCRS不一致の可能性があるため Codex にデバッグを依頼

---

## STEP 3：i2_generate_closure.py（封鎖リスト生成）

**担当：Codex（/codex:rescue）**
**前提：** STEP 2 完了（`output/closure/closure_dict.pkl` が存在すること）
**完了条件：** JSON・CSV の2ファイルが出力され、タイムスタンプ数が8件であること

### 手順

1. **ユーザーが `/codex:rescue` に以下の指示を渡す**

   ```
   以下の仕様書に従い、scripts/i2_generate_closure.py を実装してください。

   【参照ファイル】
   - 03_研究設計文書/共通設計/実装仕様書.md（セクション5-4）
   - scripts/config.py

   【入力】
   - ../output/closure/closure_dict.pkl（i1_spatial_join.py の出力）

   【実装する関数】
   - save_closure_json(closure_dict: dict, path: str) -> None
       json.dump() で保存。キー=タイムスタンプ文字列、値=エッジIDリスト
   - save_closure_csv(closure_dict: dict, path: str) -> None
       各行が (timestamp, edge_id) となる CSV を保存

   【出力先】
   - ../output/closure/road_closure_timeline.json
   - ../output/closure/road_closure_timeline.csv

   【確認用出力】
   各タイムスタンプの封鎖エッジ件数を標準出力に表示すること
   ```

2. **ユーザーがスクリプトを実行する**
   ```powershell
   & $python i2_generate_closure.py
   ```

3. **Claude Code が出力を確認する**
   ```powershell
   & $python -c "
   import json
   with open('../output/closure/road_closure_timeline.json') as f:
       d = json.load(f)
   print('タイムスタンプ数:', len(d))
   for k, v in d.items():
       print(f'  {k}: {len(v)}件')
   "
   ```
   - タイムスタンプ数が8であること
   - 各時点に1件以上のエッジIDが含まれること

---

## STEP 4：i3_route_search.py（迂回ルート検索・逃げ遅れカウント）

**担当：Codex（/codex:rescue）**
**前提：** STEP 3 完了。以下のファイルが存在すること
- `output/network/joso_road_network.graphml`
- `output/closure/road_closure_timeline.json`
- `data/population_mesh/.../tblT001178Q08.txt`
- `data/shelters/.../P20-12_08.dbf`（SHP・SHX・PRJ も同ディレクトリに必要）

**完了条件：** `unreachable_agents.csv` が出力され、t=0 で件数少、t=7 で件数増加

### 手順

1. **Claude Code が T001178 の列構成を確認する（Codex への指示に必要）**
   ```powershell
   & $python -c "
   import pandas as pd
   df = pd.read_csv('../data/population_mesh/5歳階級別人口250メッシュ_茨城/tblT001178Q08.txt',
                    encoding='shift_jis', nrows=3, dtype=str, header=None)
   for i, row in df.iterrows():
       print(f'行{i}:', list(row[:15]))
   "
   ```
   - 先頭行がヘッダ（項目名）・2行目が単位である場合は `skiprows=2`
   - 総人口列・高齢者人口列のインデックスを特定して Codex への指示に含める

2. **ユーザーが `/codex:rescue` に以下の指示を渡す**（列インデックスを確認後に記入）

   ```
   以下の仕様書に従い、scripts/i3_route_search.py を実装してください。

   【参照ファイル】
   - 03_研究設計文書/共通設計/実装仕様書.md（セクション5-5）
   - scripts/config.py

   【T001178 のデータ構造（事前確認済み）】
   - エンコーディング：Shift-JIS
   - ヘッダ行数：[STEP 4-1 で確認した値] 行
   - KEY_CODE 列：col[0]（10桁文字列）
   - 総人口列：col[確認した値]
   - 高齢者人口列：col[確認した値]
   - 常総市メッシュの抽出条件：KEY_CODE の先頭6桁が "543907" または "543917"

   【250mメッシュ重心座標の計算（JIS X 0410 準拠）】
   以下のロジックで KEY_CODE から緯度・経度を計算すること：
       key = str(key_code).zfill(10)
       p, u = int(key[0:2]), int(key[2:4])
       q, v = int(key[4]), int(key[5])
       r, w = int(key[6]), int(key[7])
       s, x = int(key[8]), int(key[9])
       lat = p / 1.5 + (r * 30 + s * 15 / 2) / 3600
       lon = 100 + u + v * 0.125 + w * 0.125 / 2 + x * 0.125 / 4

   【P20 Shapefile の仕様】
   - ファイルパス：config.SHELTER_DBF（.shp も同ディレクトリに存在）
   - 抽出条件：P20_001 == "08211" かつ P20_007 == "1"（洪水対応 19件）
   - CRS：EPSG:4612 → 使用前に EPSG:4326 に変換すること

   【実装する関数（仕様書セクション5-5 参照）】
   - load_mesh_origins(mesh_file, flood_poly) -> gpd.GeoDataFrame
   - load_shelters(dbf_path) -> gpd.GeoDataFrame
   - make_subgraph(G, closed_edges) -> nx.MultiDiGraph
       G.copy() から closed_edges に含まれるエッジを remove_edge() で除去
   - find_nearest_node(G, lon, lat) -> int
       ox.distance.nearest_nodes(G, lon, lat) を使用
   - compute_route(G, origin_node, dest_nodes) -> list[int] | None
       nx.shortest_path(G, origin, dest, weight='length') を試し NetworkXNoPath なら None
   - run_all_timesteps(G, closure_timeline, origins, destinations) -> dict

   【出力先】
   - ../output/agents/origin_points.csv（KEY_CODE, lon, lat, total_pop, elderly_pop）
   - ../output/agents/shelters.csv（name, capacity, lon, lat）
   - ../output/routes/unreachable_agents.csv（timestamp, KEY_CODE, total_pop, elderly_pop）
   - ../output/routes/evacuation_routes_t0.html ～ t7.html（8ファイル）

   【エラー処理】
   NetworkXNoPath が発生した場合は例外を捕捉し unreachable_agents に記録すること
   ```

3. **ユーザーがスクリプトを実行する**（実行時間が長い可能性あり）
   ```powershell
   & $python i3_route_search.py
   ```

4. **Claude Code が出力を確認する**
   ```powershell
   & $python -c "
   import pandas as pd
   df = pd.read_csv('../output/routes/unreachable_agents.csv')
   print('全逃げ遅れ件数（行数）:', len(df))
   print(df.groupby('timestamp')['total_pop'].sum().to_string())
   "
   ```
   - t=0（封鎖なし）で逃げ遅れ人口が少数または0であること
   - t=7（最大封鎖）で逃げ遅れ人口が増加していること
   - `output/agents/shelters.csv` の行数が19件であること

5. **エラーが発生した場合**

   | エラー | 対処 |
   |--------|------|
   | `KeyError`（T001178列） | STEP 4-1 の列確認を再実施して正しいインデックスを Codex に渡す |
   | `FileNotFoundError`（P20 SHP） | SHP・SHX・PRJ が DBF と同じディレクトリにあるか確認 |
   | 実行が極端に遅い | メッシュを浸水エリア内のみに絞っているか Codex に確認 |
   | 全時点で unreachable=0 | 封鎖エッジIDの形式不一致（"u_v_key" 文字列）を確認 |

---

## 各 STEP の完了チェックリスト

| STEP | 完了の証跡 | 確認担当 |
|------|-----------|---------|
| 0 config.py | `import config` 通過。JOSO_CODE=08211 | Claude Code |
| 1a c3 | graphml / gpkg / html が出力される | Claude Code |
| 1b e1 | pkl に8時点・各ポリゴン件数>0・CRS=EPSG:6668 | Claude Code |
| 2 i1 | 閉鎖エッジ件数が時点順に表示・pkl 保存 | Claude Code |
| 3 i2 | JSON のキー数=8・各時点に件数>0 | Claude Code |
| 4 i3 | t=0 逃げ遅れ少・t=7 増加・避難所19件 | Claude Code |

---

## トラブルシューティング早見表

| エラー | 原因 | 対処 |
|--------|------|------|
| `InsufficientResponseError`（osmnx） | place名不認識 | `JOSO_BBOX` で代替取得に変更 |
| `DriverError: KML` | ドライバ未指定 | `driver='LIBKML'` に変更 |
| `AssertionError`（CRS） | CRS変換漏れ | `to_crs("EPSG:6668")` を追加 |
| `NetworkXNoPath` | 孤立ノード・全閉鎖 | try/except で unreachable に記録 |
| 全封鎖エッジ数=0 | CRS 不一致で sjoin がヒットしない | EPSG:6668 統一を再確認 |
| `FileNotFoundError`（SHP） | SHP が DBF と別ディレクトリ | 同じフォルダに SHP/SHX/PRJ を確認 |
| 実行が極端に遅い | 全メッシュに Dijkstra を実行している | 浸水エリア内メッシュのみに絞り込む |
