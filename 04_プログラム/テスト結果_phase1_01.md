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
