# テスト結果 Phase 1 — 第3回

## サマリー

構文チェック（`py_compile`）は4ファイルすべて成功しました。

実行テストでは、環境依存の未導入ライブラリにより c3 / e1 / i1 が停止し、i2 は前段未実行で必要な入力ファイルがないため停止しました。

| スクリプト | 構文チェック | 実行テスト | 停止理由 |
|---|---|---|---|
| `c3_get_road_network.py` | ✅ | ⚠️ | `osmnx` 未導入 |
| `e1_load_flood_data.py` | ✅ | ⚠️ | `geopandas` 未導入 |
| `i1_spatial_join.py` | ✅ | ⚠️ | `geopandas` 未導入 |
| `i2_generate_closure.py` | ✅ | ⚠️ | `closure_dict.pkl` 不在（前段未実行） |

---

## テスト詳細

### 構文チェック

```bash
cd 04_プログラム/scripts && python -m py_compile c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py
```

**結果：** ✅ 4ファイルすべて成功

---

### 実行テスト

```bash
cd 04_プログラム/scripts && for f in c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py; do echo '---' $f; python $f || true; done
```

**結果：** ⚠️ 依存ライブラリ未導入および前段出力未生成という環境制約により停止

| スクリプト | エラー内容 |
|---|---|
| `c3_get_road_network.py` | `Missing dependency: osmnx` |
| `e1_load_flood_data.py` | `Missing dependency: geopandas` |
| `i1_spatial_join.py` | `Missing dependency: geopandas` |
| `i2_generate_closure.py` | `closure_dict.pkl` 不在 |

---

## 現在のエラー解消方法

正常動作のために必要なのは、コード修正より先に実行環境を揃えることです。今の失敗は主に「依存ライブラリ未導入」と「実行順序」の問題です。

### 原因

| スクリプト | 失敗理由 |
|---|---|
| `c3_get_road_network.py` | `osmnx` が未導入 |
| `e1_load_flood_data.py` / `i1_spatial_join.py` | `geopandas` 等が未導入 |
| `i2_generate_closure.py` | `i1` が生成する `closure_dict.pkl` が前提 |

実行済み確認：`python -m py_compile ...` は通過、`python c3_get_road_network.py` 等は依存不足で停止。

---

### 正常稼働させる具体手順

#### 1. 仮想環境の作成・有効化

```bash
cd 04_プログラム

# 仮想環境作成
python -m venv venv

# 仮想環境有効化（Windows）
venv\Scripts\activate
```

#### 2. 依存ライブラリのインストール

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` の依存が入る前提で、各スクリプトは動作します。

> **ProxyError / 403 が出る場合（プロキシ環境）：**
>
> ```powershell
> # PowerShell の場合
> $env:HTTP_PROXY  = "http://<proxy-host>:<proxy-port>"
> $env:HTTPS_PROXY = "http://<proxy-host>:<proxy-port>"
> python -m pip install -r requirements.txt
> ```

#### 3. 実行順序（重要）

```bash
cd scripts
python c3_get_road_network.py   # 道路GPKG を生成
python e1_load_flood_data.py    # 浸水pickle を生成
python i1_spatial_join.py       # closure pickle を生成
python i2_generate_closure.py   # JSON/CSV を出力
```

この順序は各スクリプトの入出力依存に一致しています（i2 は i1 の出力が前提）。

---

### 成功判定（最低限）

以下のファイルが生成されれば正常稼働です（`config.py` 定義準拠）。

| 出力ファイル | 生成スクリプト |
|---|---|
| `output/network/joso_road_network.graphml` | c3 |
| `output/network/joso_edges.gpkg` | c3 |
| `output/flood/flood_polygons.pkl` | e1 |
| `output/closure/closure_dict.pkl` | i1 |
| `output/closure/road_closure_timeline.json` | i2 |
| `output/closure/road_closure_timeline.csv` | i2 |

#### 成功確認コマンド（PowerShell）

```powershell
cd 04_プログラム

# 各ファイルの存在を確認
if (Test-Path output/network/joso_road_network.graphml) { "OK graphml" } else { "NG graphml" }
if (Test-Path output/network/joso_edges.gpkg)           { "OK edges gpkg" } else { "NG edges gpkg" }
if (Test-Path output/flood/flood_polygons.pkl)           { "OK flood pkl" } else { "NG flood pkl" }
if (Test-Path output/closure/closure_dict.pkl)           { "OK closure pkl" } else { "NG closure pkl" }
if (Test-Path output/closure/road_closure_timeline.json) { "OK closure json" } else { "NG closure json" }
if (Test-Path output/closure/road_closure_timeline.csv)  { "OK closure csv" } else { "NG closure csv" }
```
