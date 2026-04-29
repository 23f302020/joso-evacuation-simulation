# テスト結果 — Phase 1（第2回）

**実施日：** 2026-04-30  
**対象：** 4スクリプト動作確認

---

## 概要

作成済み4スクリプトの動作確認を実施しました。  
**結論：現環境では依存ライブラリ不足のため c3/e1/i1 が起動時に失敗し、i2 は前段成果物（`closure_dict.pkl`）未生成のため失敗しました。**

---

## 実施コマンドと結果

### ✅ 構文チェック — py_compile

```bash
cd 04_プログラム/scripts
python -m py_compile c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py
```

> 4スクリプトすべて構文エラーなし。

---

### ❌ 実行確認 — 4スクリプト連続実行

```bash
cd 04_プログラム/scripts
for f in c3_get_road_network.py e1_load_flood_data.py i1_spatial_join.py i2_generate_closure.py; do
  echo '---' $f
  python $f || true
done
```

| スクリプト | 結果 | エラー内容 |
|---|:---:|---|
| `c3_get_road_network.py` | ❌ | `ModuleNotFoundError: No module named 'folium'` |
| `e1_load_flood_data.py` | ❌ | `ModuleNotFoundError: No module named 'folium'` |
| `i1_spatial_join.py` | ❌ | `ModuleNotFoundError: No module named 'geopandas'` |
| `i2_generate_closure.py` | ❌ | `FileNotFoundError: ../output/closure/closure_dict.pkl`（前段未実行のため） |

---

## 第1回からの変化

| 確認項目 | 第1回 | 第2回 |
|---|:---:|:---:|
| 構文チェック（py_compile） | 未実施 | ✅ 全スクリプト通過 |
| 依存ライブラリ不足による失敗 | ❌ | ❌（変わらず） |
| `closure_dict.pkl` 不在による失敗 | ❌ | ❌（変わらず） |

> **新たに判明した点：** スクリプトの構文自体は正しい。問題は実行環境の依存ライブラリのみ。

---

## 残存課題

依存ライブラリが導入可能な環境（venv 整備済み、またはプロキシ制限なし）での実行が必要。  
実行順・環境準備手順は [テスト結果_phase1_第1回.md](./テスト結果_phase1_第1回.md) を参照。
