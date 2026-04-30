# テスト結果 Phase 1 — 第5回

## サマリー

全5スクリプト（c3/e1/i1/i2/i3）の実行テストを完了しました。
累積封鎖（選択肢A）を適用してもt0の33本が全タイムスタンプの封鎖エッジを包含しているため、到達不可数は依然として全タイムスタンプで一定であることが判明しました。

| スクリプト | 構文チェック | 実行テスト | 備考 |
|---|---|---|---|
| `c3_get_road_network.py` | ✅ | ✅ | 道路エッジ 12,860 件・CRS EPSG:6668 |
| `e1_load_flood_data.py` | ✅ | ✅ | 浸水ポリゴン 8 時点 |
| `i1_spatial_join.py` | ✅ | ✅ | 閉鎖エッジ数 33/31/31/33/20/15/33/33 |
| `i2_generate_closure.py` | ✅ | ✅ | JSON・CSV 出力完了 |
| `i3_route_search.py` | ✅ | ✅ | 出発地 11 メッシュ・到達不可 各時点 3 メッシュ |

---

## テスト詳細

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
| `e1_load_flood_data.py` | 浸水ポリゴン時点数 | 8 時点 |
| `i1_spatial_join.py` | タイムスタンプ別閉鎖エッジ数 | 33, 31, 31, 33, 20, 15, 33, 33 |
| `i2_generate_closure.py` | JSON・CSV 出力 | 正常生成 |
| `i3_route_search.py` | 出発地メッシュ数・総人口・高齢者数 | 11 メッシュ・人口 723・高齢者 13 |
| `i3_route_search.py` | 避難所件数 | 19 件 |
| `i3_route_search.py` | ルート HTML | 8 ファイル生成 |
| `i3_route_search.py` | 到達不可（各時点） | 3 メッシュ・人口 87・高齢者 13 |

---

## 累積封鎖（選択肢A）検証結果

累積処理はコード上適用されているが、**累積閉鎖エッジ数が全タイムスタンプで33本から変化しない**。

| タイムスタンプ | 累積閉鎖エッジ数 |
|---|---|
| t0 | 33 |
| t1 | 33 |
| t2 | 33 |
| t3 | 33 |
| t4 | 33 |
| t5 | 33 |
| t6 | 33 |
| t7 | 33 |

**原因：** t0 の 33 本がすでに全タイムスタンプの封鎖エッジ集合を包含しているため、累積しても新たなエッジが加わらない。

**結果：** 到達不可は全タイムスタンプで 3 メッシュ（人口87）のまま変化しない。コードバグではなく、`closure_timeline` の集合構造の問題。

---

## 残っている課題

| 課題 | 内容 | 対応方針 |
|---|---|---|
| 到達不可の時系列変化なし | t0 の 33 エッジが全時点を包含しており、累積しても変化しない | `i1_spatial_join.py` の閉鎖エッジ算出が時点ごとに時間発展しているか再検証 |
| 出力ファイル名の不一致 | 第4回文書は `origins.csv`・`unreachable.csv` と記載しているが、実際の `config.py` の出力先は `origin_points.csv`・`unreachable_agents.csv` | `scripts/テスト結果_phase1_02.md` の出力ファイル一覧を修正する |

---

## 次のステップ（優先順）

| 優先度 | タスク | 内容 |
|---|---|---|
| 1 | i1 再検証 | `closure_dict.pkl` の内容をダンプし、t0 が他時点の閉鎖エッジを包含している原因を確認。必要に応じて `i1_spatial_join.py` を修正する |
| 2 | 文書ファイル名修正 | `scripts/テスト結果_phase1_02.md` の出力ファイル一覧を `origin_points.csv` / `unreachable_agents.csv` に修正 |
| 3 | I-4 SUMO 変換 | `i4_convert_sumo.py` 実装：OSMnx 道路 NW を SUMO `.net.xml` に変換 |
| 4 | I-5 シナリオA | `origin_points.csv` から車両エージェントを生成し SUMO `.rou.xml` を作成 |
| 5 | I-6 TraCI 動的封鎖 | `road_closure_timeline.json` を使って時刻別に道路閉鎖・逃げ遅れ車両ログ取得 |
