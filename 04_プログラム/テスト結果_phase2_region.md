# テスト結果 Phase 2 全域拡張

## 1. 対象・棚卸し生成テスト（2026/05/15）

対象スクリプト：

- `04_プログラム/scripts/p2_region_inventory.py`

生成物：

- `04_プログラム/output/sumo/regions/_management/phase2_region_targets.csv`
- `04_プログラム/output/sumo/regions/_management/phase2_region_inventory.csv`
- `04_プログラム/output/sumo/regions/_management/phase2_region_inventory.md`

実行コマンド：

```powershell
python -m py_compile 04_プログラム\scripts\p2_region_inventory.py
python 04_プログラム\scripts\p2_region_inventory.py all
```

結果：

| 確認項目 | 結果 |
|---|---:|
| 構文チェック | 合格 |
| Phase 2全域拡張対象 | 41件 |
| 事前確認OK | 41件 |
| Phase 1対象外として保持 | 3件 |
| `phase2_region_targets.csv` 行数 | 41行 |
| `phase2_region_inventory.csv` 内訳 | `yes, yes` 41件、`no, no` 3件 |

判定：

- 合格。
- Phase 1対象地域全域は、成果物化済み41市区町村として固定できる。
- 鹿嶋市・神栖市・東海村は、初回のPhase 2全域拡張には含めない判断を棚卸しファイルへ記録した。
- 対象41件は、Phase 1市区町村HTML・道路ネットワーク・基本アセットの存在確認がすべて揃っている。

残タスク：

- 市区町村別SUMOネットワーク変換は未実行。
- 市区町村別edge対応表、閉鎖タイムライン、出発地、避難所、安全性判定の生成は未実行。
- small / 10pct / full の全域実行テストは、地域別SUMO入力生成後に実施する。
