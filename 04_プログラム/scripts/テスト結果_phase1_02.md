# テスト結果 Phase 1 — 第4回

## サマリー

全5スクリプト（c3/e1/i1/i2/i3）の構文確認・実行テストをすべて完了しました。
実害のある不具合（OneDrive ファイルロック・KML バッファ CRS・列名解釈・座標式・型差異・最近傍ノード）を修正し、通しで正常動作を確認しました。

| スクリプト | 構文チェック | 実行テスト | 備考 |
|---|---|---|---|
| `c3_get_road_network.py` | ✅ | ✅ | 道路エッジ 12,860 件・CRS EPSG:6668 |
| `e1_load_flood_data.py` | ✅ | ✅ | 浸水ポリゴン 8 時点・CRS EPSG:6668 |
| `i1_spatial_join.py` | ✅ | ✅ | 閉鎖エッジ数 33/31/31/33/20/15/33/33 |
| `i2_generate_closure.py` | ✅ | ✅ | JSON・CSV 出力完了 |
| `i3_route_search.py` | ✅ | ✅ | 出発地 11 メッシュ・到達不可 各時点 3 メッシュ |

---

## テスト詳細

### 構文チェック（AST parse）

```bash
cd 04_プログラム/scripts
python -c "import ast, sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" \
  c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py i3_route_search.py
```

**結果：** ✅ 5ファイルすべて成功

---

### 実行テスト

```bash
cd 04_プログラム/scripts
python c3_get_road_network.py
python e1_load_flood_data.py
python i1_spatial_join.py
python i2_generate_closure.py
python i3_route_search.py
```

**各スクリプトの確認結果：**

| スクリプト | 確認項目 | 結果 |
|---|---|---|
| `c3_get_road_network.py` | 道路エッジ数・CRS | 12,860 件・EPSG:6668 |
| `e1_load_flood_data.py` | 浸水ポリゴン時点数・CRS | 8 時点・EPSG:6668 |
| `i1_spatial_join.py` | タイムスタンプ別閉鎖エッジ数 | 33, 31, 31, 33, 20, 15, 33, 33 |
| `i2_generate_closure.py` | JSON・CSV 出力 | 正常生成 |
| `i3_route_search.py` | 出発地メッシュ数・総人口・高齢者数 | 11 メッシュ・人口 723・高齢者 146 |
| `i3_route_search.py` | 避難所件数 | 19 件 |
| `i3_route_search.py` | ルート HTML | 8 ファイル生成 |
| `i3_route_search.py` | 到達不可（各時点） | 3 メッシュ・人口 87 |

---

## 今回修正した不具合

| 修正内容 | 対象スクリプト |
|---|---|
| Windows/OneDrive 既存ファイルロック時の `PermissionError` 対策 | c3・e1・i1・i2・i3 |
| KML バッファを地理座標系（度）から投影 CRS（EPSG:6690・メートル）で実施 | e1 |
| T001178 CSV の総人口列（`T001178001`）・65歳以上列（`T001178043`〜`T001178055`）を明示指定 | i3 |
| 250m メッシュ座標式をセル南西隅からセル中心点（`+3.75秒`/`+5.625秒`）に修正 | i3 |
| 避難所フラグ `P20_007` の整数/文字列型差異に対し `.astype(str)` を追加 | i3 |
| `ox.distance.nearest_nodes()`（scikit-learn 依存）を純 Python `min()` で代替 | i3 |

---

## 生成された出力ファイル一覧

| 出力ファイル | 生成スクリプト | 確認状態 |
|---|---|---|
| `output/network/joso_road_network.graphml` | c3 | ✅ |
| `output/network/joso_edges.gpkg` | c3 | ✅ |
| `output/network/joso_network_map.html` | c3 | ✅ |
| `output/flood/flood_polygons.pkl` | e1 | ✅ |
| `output/flood/flood_timeline_map.html` | e1 | ✅ |
| `output/closure/closure_dict.pkl` | i1 | ✅ |
| `output/closure/road_closure_timeline.json` | i2 | ✅ |
| `output/closure/road_closure_timeline.csv` | i2 | ✅ |
| `output/agents/origins.csv` | i3 | ✅ |
| `output/agents/shelters.csv` | i3 | ✅ |
| `output/routes/evacuation_routes_t0.html` 〜 `t7.html` | i3 | ✅（8ファイル） |
| `output/routes/unreachable.csv` | i3 | ✅ |

---

## 残っている課題

### 到達不可メッシュ数が全タイムスタンプで一定

封鎖なし（`closure=[]`）では到達不可 0 になるため封鎖の影響自体は出ているが、時系列変化が見られない。

原因と対応方針の選択肢：

| 選択肢 | 内容 | 影響 |
|---|---|---|
| A（累積封鎖） | 浸水ポリゴンを時点ごとに累積扱いにする | 時間が進むほど封鎖が増え到達不可が増加する |
| B（浸水範囲拡張） | 出発地の対象メッシュを浸水エリア外まで広げる | より多くの出発地を扱い変化が出やすくなる |

どちらを採用するかは研究のモデル設定（実際の洪水進行をどう扱うか）に関わるため、**指導教員への確認が必要**。

---

## 次のステップ（優先順）

| 優先度 | タスク | 内容 |
|---|---|---|
| 1 | I-3 モデル判断 | 到達不可が時系列変化しない問題を選択肢A・Bどちらで解消するか指導教員に確認 |
| 2 | 進捗文書の更新 | `実装タスク一覧.md`・`AGENTS.md` の c3〜i3 完了状態を更新 |
| 3 | I-4 SUMO 変換 | `i4_convert_sumo.py` 実装：OSMnx 道路 NW を SUMO `.net.xml` に変換 |
| 4 | I-5 シナリオA | `origins.csv` から車両エージェントを生成・SUMO `.rou.xml` 作成・走行テスト |
| 5 | I-6 TraCI 動的封鎖 | `road_closure_timeline.json` を使って時刻別に道路閉鎖・逃げ遅れ車両ログ取得 |
