# テスト結果 — Phase 1（第1回）

**実施日：** 2026-04-30  
**対象：** 4スクリプト実行確認

---

## 概要

作成済み4スクリプトの実行テストを行いました。  
**結論：現環境では依存ライブラリ未導入＋パッケージ取得制限のため、フル実行はできませんでした。**

---

## 実施コマンドと結果

### ❌ 単体実行 — c3_get_road_network.py

```bash
cd 04_プログラム/scripts && python c3_get_road_network.py
```

> `ModuleNotFoundError: No module named 'folium'` で停止

---

### ⚠️ 依存インストール試行

```bash
cd 04_プログラム && python -m pip install -r requirements.txt
```

> `ProxyError (403 Forbidden)` により `osmnx==2.1.0` 取得失敗（環境側ネットワーク制限）

---

### ❌ 4スクリプト連続実行

```bash
cd 04_プログラム/scripts
for f in c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py; do
  echo '---' $f
  python $f || true
done
```

| スクリプト | 結果 | エラー内容 |
|---|:---:|---|
| `c3_get_road_network.py` | ❌ | `folium` 未導入 |
| `e1_load_flood_data.py` | ❌ | `folium` 未導入 |
| `i1_spatial_join.py` | ❌ | `geopandas` 未導入 |
| `i2_generate_closure.py` | ❌ | `closure_dict.pkl` 不在（前段未実行） |

---

## 失敗原因の整理

### 1. 依存ライブラリ不足

各スクリプトが以下ライブラリに依存しているが、現行 Python 環境に未導入：

| スクリプト | 依存ライブラリ |
|---|---|
| `c3_get_road_network.py` | `folium`, `geopandas`, `osmnx` |
| `e1_load_flood_data.py` | `folium`, `geopandas`, `pyogrio` |
| `i1_spatial_join.py` | `geopandas` |
| `i2_generate_closure.py` | —（`closure_dict.pkl` 依存） |

### 2. ネットワーク制限によるインストール失敗

`requirements.txt` に基づくインストールを試行したが、プロキシ制限（403 Forbidden）によりパッケージ取得できなかった。

### 3. パイプライン依存の未生成ファイル

`i2_generate_closure.py` は `i1` の出力 `closure_dict.pkl` を必須としているが、前段が未完了のため入力ファイルが存在しない。

---

## 正しい実行順

```
c3_get_road_network.py
  ↓
e1_load_flood_data.py
  ↓
i1_spatial_join.py
  ↓
i2_generate_closure.py
```

> `i2` は `i1` の成果物 `closure_dict.pkl` が必須のため、必ずこの順で実行すること。

---

## 環境準備手順

### A. ネットワーク制限のない環境

```bash
cd 04_プログラム
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### B. 学内／社内プロキシ環境

```bash
export HTTPS_PROXY=http://<proxy-host>:<proxy-port>
export HTTP_PROXY=http://<proxy-host>:<proxy-port>
python -m pip install -r requirements.txt
```

---

## スクリプト実行コマンド

```bash
cd 04_プログラム/scripts
python c3_get_road_network.py
python e1_load_flood_data.py
python i1_spatial_join.py
python i2_generate_closure.py
```

---

## 成功判定（出力ファイル確認）

以下ファイルがすべて生成されれば成功：

```
output/
├── network/
│   ├── joso_road_network.graphml
│   ├── joso_edges.gpkg
│   └── joso_network_map.html
├── flood/
│   ├── flood_polygons.pkl
│   └── flood_timeline_map.html
└── closure/
    ├── closure_dict.pkl
    ├── road_closure_timeline.json
    └── road_closure_timeline.csv
```

---

## コード改善点（次回対応推奨）

| 対象ファイル | 現状の問題 | 推奨対応 |
|---|---|---|
| `e1_load_flood_data.py` | `gpd.pd.concat` を使用 | `import pandas as pd` → `pd.concat` に変更（より明確） |
| `e1_load_flood_data.py` | KML とタイムスタンプの対応がソート順依存 | ファイル名から時刻を抽出して明示マッピング |
| `c3_get_road_network.py` | `geometry.centroid` で地理座標系警告 | `representative_point()` に変更して警告を回避 |
