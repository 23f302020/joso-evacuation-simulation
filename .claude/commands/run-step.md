---
description: シミュレーションのステップスクリプトを実行する。venv有効化・実行・出力確認を一括で行う。使い方: /run-step <スクリプト名>
---

# /run-step — シミュレーションステップ実行コマンド

## 使い方

```
/run-step c3_get_road_network
/run-step e1_load_flood_data
/run-step i1_spatial_join
/run-step i2_generate_closure
/run-step i3_route_search
/run-step v2_scenario_route_simulation
```

引数なしで呼び出した場合は実行可能なスクリプト一覧を表示する。

## 実行手順

### Step 1: 引数の確認

`$ARGUMENTS` からスクリプト名を取得する（`.py` 拡張子は省略可）。

引数なしの場合：
```bash
ls "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム/scripts/"*.py
```
一覧を表示して終了。

### Step 2: venv の確認と有効化

```bash
SCRIPTS_DIR="/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム/scripts"
VENV_DIR="/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究/04_プログラム/.venv"

# venv 存在確認
if [ ! -d "$VENV_DIR" ]; then
  echo "[ERROR] venv が見つかりません: $VENV_DIR"
  echo "  → cd 04_プログラム && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

source "$VENV_DIR/bin/activate"
```

### Step 3: スクリプト実行

```bash
cd "$SCRIPTS_DIR"
python <スクリプト名>.py 2>&1 | tee /tmp/run-step-output.txt
EXIT_CODE=${PIPESTATUS[0]}
```

### Step 4: 結果確認

実行後、以下を確認してユーザーに報告する：

1. **終了コード** — 0 なら成功、それ以外はエラー内容を表示
2. **出力ファイルの生成確認** — スクリプトに対応する出力先を確認

| スクリプト | 確認する出力 |
|-----------|------------|
| `c3_get_road_network` | `output/network/joso_road_network.graphml` |
| `e1_load_flood_data` | `output/flood/flood_polygons.pkl` |
| `i1_spatial_join` | `output/closure/closure_dict.pkl` |
| `i2_generate_closure` | `output/closure/road_closure_timeline.json` |
| `i3_route_search` | `output/routes/` |
| `v2_scenario_route_simulation` | `output/scenario_v2/scenario_route_simulation.html` |

3. **エラーがあった場合** — エラーメッセージを表示し、原因と対処を提示する

### Step 5: 報告

```
✅ <スクリプト名> 完了
出力: <生成されたファイルパス>
実行時間: <秒>
```

または

```
❌ <スクリプト名> 失敗（終了コード: <N>）
エラー: <メッセージ>
対処: <提案>
```

## よくあるエラーと対処

| エラー | 原因 | 対処 |
|-------|------|------|
| `ModuleNotFoundError` | パッケージ未インストール | `pip install <package>` |
| `FileNotFoundError` | 前のステップ未実行 | 依存スクリプトを先に実行 |
| `UnicodeEncodeError` | Windows ターミナルの文字コード | print 文の特殊文字を ASCII に変更 |
| `CRSError` | CRS 不一致 | `config.py` の CRS 設定を確認 |
