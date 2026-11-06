# 03 push手順

> pushはユーザーの明示依頼があるときだけ行う。PowerShellでの手順を示す。
> **本書は公開リポジトリ`joso-evacuation-simulation`専用。** `開発メモ/`の非公開リポジトリは[05_開発メモ非公開リポジトリ](05_開発メモ非公開リポジトリ.md)の手順に従う。

---

## 1. アカウント運用（2026-11-06決定）

**このプロジェクトでは`23f302020`だけを使い、`JI-life`には触れない。**

| 項目 | 内容 |
|---|---|
| 使うアカウント | `23f302020`（リポジトリ所有者・push/admin権限あり） |
| 触れないアカウント | `JI-life`（このPCの`gh`で有効になっているが、本リポジトリへのpush権限はなく403になる） |
| してはいけないこと | `gh auth switch`、`gh auth logout`、`JI-life`のトークン利用、`gh`のグローバル設定変更 |
| 方法 | push時だけ、そのコマンドの間に限り`23f302020`のトークンを環境変数で渡す（§4） |
| コミット作者 | ローカル設定 `user.name=23f302020`・`user.email=280485999+23f302020@users.noreply.github.com` |
| GitHub MCP | `plugin:github`は`23f302020`で認証済み（2026-11-06確認）。MCPで書き込む場合もこのアカウント |

コミット前に作者設定を確認する。

```powershell
git config user.name; git config user.email
```

**トークンを画面・ログ・ファイル・コミットに出さない。** `gh auth token`の出力は変数にだけ入れ、使用後すぐ消す。

## 2. push前チェックリスト

すべて確認してからpushする。1つでも満たさなければ止まって報告する。

| # | 確認 | コマンド例 |
|---|---|---|
| 1 | ユーザーの明示依頼がある | — |
| 2 | 現在のブランチが作業ブランチ | `git branch --show-current` |
| 3 | 差分が依頼範囲だけ（無関係な変更を含まない） | `git status --short`・`git diff --cached --stat` |
| 4 | 空白エラーがない | `git diff --cached --check` |
| 5 | 除外対象が入っていない（`開発メモ/`・PDF・data本体・巨大出力） | `git diff --cached --name-only` を目視 |
| 6 | 秘密情報がない | §3 |
| 7 | 50MB超のファイルがない | §3 |
| 8 | 記録の同期済み（必要に応じ`context.md`・現状把握MD→HTML・タスク管理・決定ログ） | `status_progress.py --check` 等 |
| 9 | 研究run実行中に`scripts/`・入力設定を含めていない | — |
| 10 | `master`も更新する場合、FF可能か | `git merge-base --is-ancestor origin/master HEAD` が成功 |
| 11 | `master`更新で`04_プログラム/output/**`が変わる場合、Pages本番反映になることをユーザーに伝えた | `git diff --name-only origin/master HEAD -- 04_プログラム/output` |

## 3. 秘密情報・大容量の検査

```powershell
# 秘密情報らしき文字列（ステージ済み差分）
git diff --cached -U0 | Select-String -Pattern 'ghp_|gho_|github_pat_|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]|password\s*[:=]|secret\s*[:=]|token\s*[:=]'

# 50MB超のステージ済みファイル
git diff --cached --name-only --diff-filter=AM | ForEach-Object { if ((Test-Path $_) -and (Get-Item $_).Length -gt 50MB) { "{0}  {1:N1}MB" -f $_, ((Get-Item $_).Length/1MB) } }
```

ヒットしたら内容を確認する。誤検出でなければステージから外し、ユーザーに報告する。

## 4. 実行コマンド

```powershell
cd "C:\Users\Ko_rr\Documents\Codex\研究室\4年次本研究"
git fetch origin

# 23f302020 のトークンをこのプロセスの間だけ使う（画面に出さない）
$env:GH_TOKEN = (gh auth token --user 23f302020)
try {
  # 作業ブランチだけを push
  git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin codex/update-latest-research-results

  # 作業ブランチと master を同時に更新（master は FF のみ。非FFなら拒否される）
  # git -c credential.helper= -c "credential.helper=!gh auth git-credential" push --atomic origin HEAD:codex/update-latest-research-results HEAD:master
} finally {
  Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
}
```

- `-c credential.helper=`で既存の資格情報ヘルパーを無効にし、`gh auth git-credential`に環境変数`GH_TOKEN`（＝`23f302020`）を使わせる。`gh`の有効アカウント（`JI-life`）は変わらない。
- 書き込み権限だけ確かめたいときは`push --dry-run`を使う（変更は送られない）。2026-11-06にこの方法で認証が通ることを確認済み。
- GitHub MCPで作業する場合も、push相当の操作（ブランチ作成・ファイル更新）は同じく明示依頼の範囲に限る。

## 5. push後の読み戻し確認

```powershell
git fetch origin
git rev-parse HEAD
git ls-remote origin refs/heads/codex/update-latest-research-results refs/heads/master
```

- ローカル`HEAD`とGitHub側のSHAが一致することを確認する。
- `master`を更新し、Pagesのデプロイ条件に当たる場合は、Actionsの実行結果を確認する。

  ```powershell
  $env:GH_TOKEN = (gh auth token --user 23f302020)
  gh api "repos/23f302020/joso-evacuation-simulation/actions/runs?per_page=3" --jq '.workflow_runs[]|"\(.created_at) \(.name) \(.head_branch) \(.status) \(.conclusion)"'
  Remove-Item Env:GH_TOKEN
  ```

- 確認後、`gh api user --jq .login`が`JI-life`のまま（＝グローバル状態を変えていない）であることを確かめる。

## 6. 完了報告に書くこと

- push先ブランチとコミットSHA
- 反映先の区別：「GitHub反映済み」「Pages本番反映済み（Actions成功）」「Cloudflareは対象外」など
- 実施したチェックと、実施していないこと
