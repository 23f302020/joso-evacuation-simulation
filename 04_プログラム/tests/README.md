# tests — 避難シミュレーション自動テスト

本研究の実装（`../scripts/`）の自動テスト。設計思想・全テスト項目・優先度・工数は
**[テスト設計書.md](テスト設計書.md)** を参照。

## クイックスタート

```powershell
# venv をアクティベート後、依存を追加
pip install pytest pytest-regressions hypothesis

# 実行（既定でSUMO@slowは除外）
cd 04_プログラム
pytest tests/ -v

# 回帰テストのgolden file 初回生成
pytest tests/regression/ --force-regen

# SUMO実行を含む全テスト
pytest tests/ -m "slow or not slow" -v
```

## 実装状況

| 分類 | ファイル | 状態 |
|------|----------|------|
| 骨格 | conftest.py / pytest.ini | ✅ 実装済 |
| T3 メッシュ変換 | unit/test_meshcode.py | ✅ 実装済（P0） |
| T4 車両会計 | unit/test_vehicle_accounting.py | ✅ 実装済（P0） |
| T5 エージェント分類 | unit/test_agent_types.py | ✅ 実装済（P0） |
| 5-A スキーマ回帰 | regression/test_output_schema.py | ✅ 実装済（P0） |
| T1 浸水0.5m境界 | unit/test_flood_threshold.py | ⬜ 未（要fixture） |
| T2 閉鎖辞書 | unit/test_closure.py | ⬜ 未（要fixture） |
| T6 評価指標 | unit/test_evaluation.py | ⬜ 未 |
| T7 スナップ・経路 | unit/test_snap_route.py | ⬜ 未 |
| その他 | 5-B/5-C/5-D/T8/slow | ⬜ 未 |

## 方針（要点）

- **再現性最優先**：卒論の結論を支える3段連鎖（閉鎖集合→車両会計→評価指標）を確実に押さえる。
- **回帰テストで手動確認を自動化**：既存の「再実行＋Markdown記録」を pytest に置換。
- **外部依存は境界で切る**：OSM/SUMO/API は呼ばず、小規模固定サンプル・モックで決定論化。
- **やりすぎない**：80%カバレッジは追わない。Phase3（バス比較）にテスト投資を集中。
