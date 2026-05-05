---
description: セッション終了時の定型作業。CLAUDE.md更新 → タスク一覧更新 → git commit & push を一括実行する。
---

# /session-end — セッション終了コマンド

このセッションで行った変更を記録し、GitHub にプッシュして次セッションに引き継ぐ。

## 実行手順

### Step 1: 変更内容の把握

```bash
cd "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究"
git diff --stat
git status
```

変更されたスクリプト・出力ファイルを確認する。

### Step 2: CLAUDE.md の更新

`CLAUDE.md` の以下の項目をこのセッションの実績に合わせて更新する：

- **現在フェーズ** — 完了した実装・新たに判明した技術的事実を反映
- **次セッションの優先タスク** — 未完了・次のアクションを書き直す
- **最終更新日** — 今日の日付に変更（YYYY/MM/DD 形式）

更新後、不要になった情報（解決済みの問題、古い次セッションタスク等）は削除する。

### Step 3: タスク一覧の更新

`05_タスク管理/実装タスク一覧.md` を開き、このセッションで完了したタスクを `✅` に更新する。

### Step 4: git commit & push

```bash
cd "/mnt/c/Users/Ko_rr/OneDrive - stu.teikyo-u.ac.jp/研究室/4年次本研究"
git add CLAUDE.md "05_タスク管理/実装タスク一覧.md"
# 変更したスクリプトも追加
git add 04_プログラム/scripts/
git add 03_研究設計文書/
git status  # 確認
git commit -m "$(cat <<'EOF'
<type>: <このセッションの主な変更を一行で>

セッション終了コミット。変更内容：
- <変更点1>
- <変更点2>
EOF
)"
git push origin master
```

`<type>` は `feat` / `fix` / `docs` / `refactor` のいずれか。

### Step 5: 完了確認

```bash
git log --oneline -3
```

プッシュ済みを確認して終了。

## 注意

- `output/` 配下のファイルは `.gitignore` 対象のため commit 不要
- `data/` 配下の大容量ファイルも同様
- `.env` や API キーを含むファイルは絶対に commit しない
