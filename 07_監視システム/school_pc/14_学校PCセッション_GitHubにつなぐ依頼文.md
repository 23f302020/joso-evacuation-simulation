# 学校PCセッションへの依頼文（GitHub につなぐ・初回）

> 使い方：学校PCの Claude セッションに、下の「依頼文」を貼る。USB は使わない。
> この初回のあとは、開発PCの更新は GitHub から取り込む（`git pull --ff-only`）。

## 構成（開発PC側の判断・2026-11-13）

| 向き | 手段 |
|---|---|
| 開発PC → 学校PC（コード・依頼文） | 公開リポジトリ `23f302020/joso-evacuation-simulation` のブランチ `codex/update-latest-research-results` から pull（取り込み専用） |
| 学校PC → 開発PC（作業報告） | 学校PCでは git の管理外のフォルダ `school_pc_local\` に書き、ユーザーが開発PCのセッションへ貼る |
| 大きなデータ・環境 | 既に USB で配置済み（40,712ファイル照合済み）。git は触れない |

- **新しくクローンしない。** 公開リポジトリには、データ・venv・toolchain・監視の runtime・開発メモが入っていないため、今の `C:\JDRT\research` に git を後からつなぐ。
- **学校PCから push しない。** 認証情報を学校PCに置かない（共有の学校PCから公開リポジトリへ書けないようにする）。
- **git が管理するファイルを、学校PCで編集しない。** 学校PCの記録・報告は `school_pc_local\` に書く（このフォルダは学校PCだけの除外設定 `.git\info\exclude` に入れる）。管理下のファイルを編集すると、次の pull が止まる。
- **pull は、研究 run・親ループ・sequence が動いていないときだけ。** 監視の `watch.py` が変わったときは、監視タスクを再起動する（親ループの事前確認 `preflight` がソースの不一致を検出する）。
- git の管理外のファイル（データ、`config.json`、venv、runtime、`04_プログラム/output` の大半）は、git が触れない。

---

## 依頼文

学校PCの配置先 `C:\JDRT\research` を、GitHub の公開リポジトリに「取り込み専用」でつなぎます。次の順で進めてください。

**守ること：** 研究run・READY・start-next・validate・record・親ループの `run` は実行しない。秘密情報は読まない・入力しない・表示しない。`git push`、認証情報の設定、`git clean`、`git reset --hard`、`git stash` は実行しない。`04_プログラム/output/` 配下には git の書き込み操作（checkout・restore）をしない。git が管理するファイルを編集しない（記録は `school_pc_local\` へ）。

### 1. 前提の確認（読取のみ）
1. 研究 run・親ループ・sequence が動いていないこと（`watch.py status` で実行中の対象が0件、`choice_parent_loop.py show` で実行中でない）。
2. `git --version`。git が無ければ止めて、ユーザーに Git for Windows（公式サイト https://git-scm.com/ ）の導入を頼む。Claude はダウンロード・インストールをしない。
3. `C:\JDRT\research\.git` が無いこと（あれば止めて報告）。

### 2. git をつなぐ（作業ファイルは1つも書き換えない）
```
cd C:\JDRT\research
git init
git config core.autocrlf true
git remote add origin https://github.com/23f302020/joso-evacuation-simulation.git
git remote set-url --push origin DISABLED-no-push-from-school-pc
git fetch origin codex/update-latest-research-results
git reset --mixed FETCH_HEAD
git branch -m codex/update-latest-research-results
git branch --set-upstream-to=origin/codex/update-latest-research-results
```
- `git reset --mixed` は、git の記録（インデックス）だけを合わせる。作業ファイルは変わらない。
- 続けて、`school_pc_local/` の1行を `.git\info\exclude` に追記し、`school_pc_local\reports\` を作る。

### 3. 差の一覧（読取のみ）
4. `git status --porcelain` の結果を `school_pc_local\reports\git_attach_status_20261113.txt` に保存し、次の3つに分けて件数と代表例を報告する。**この段階では何も直さない。**
   - (a) **今回の更新で変わったコード**：`.agents/skills/joso-jdrt-runner/scripts/choice_parent_loop.py`、`test_choice_parent_loop.py`、`07_監視システム/mail_selftest.py`、`test_mail_selftest.py`（新規）、`07_監視システム/school_pc/13_…`・`14_…`（新規）。新規ファイルは「削除」（` D`）として出る。
   - (b) **学校PCの Claude が追記した文書**（例：`05_タスク管理/jdrt/独立監視システム_導入タスク.md`、`学校PC_基盤整理_*.md`）。
   - (c) **その他**（USB で運んだ時点の開発PCの未コミットの変更、改行だけの差など）。
5. (b) の学校PC側の追記は、`school_pc_local\reports\` に、元のファイル名でコピーして保全する（ユーザーが開発PCへ貼るため）。

### 4. 更新の取り込み（(a) だけ）
6. (a) の既存ファイルを `C:\JDRT\backup_20261113b\<path>` へ退避してから、(a) のファイルだけを、取り込んだ版に合わせる：
   ```
   git checkout origin/codex/update-latest-research-results -- ".agents/skills/joso-jdrt-runner/scripts/choice_parent_loop.py" ".agents/skills/joso-jdrt-runner/scripts/test_choice_parent_loop.py" "07_監視システム/mail_selftest.py" "07_監視システム/test_mail_selftest.py" "07_監視システム/school_pc/13_学校PCセッション_通し試験と段8の依頼文.md" "07_監視システム/school_pc/14_学校PCセッション_GitHubにつなぐ依頼文.md"
   ```
   ほかのファイルには、この段階では触れない。(b) と (c) の扱いは、報告を受けて開発PCで決める。
7. `git status --porcelain -- <(a) のパス>` が空になったことを確認する。

### 5. 続き
8. `07_監視システム\school_pc\13_学校PCセッション_通し試験と段8の依頼文.md` の手順のうち、**A の照合と上書き（手順1・2）は済んだものとして飛ばし**、A の試験（手順3）から F まで進める。報告ファイルは13の指定の場所ではなく `school_pc_local\reports\学校PC_通し試験と段8_20261113.md` に書く（git の管理下を汚さないため）。
9. 最後に、この依頼文の結果（手順1〜7）も同じ報告ファイルの冒頭に書く。ユーザーがその内容を開発PCのセッションに貼る。

### 今後の更新の取り込み（2回目以降の決まった手順）
- 前提：研究 run・親ループ・sequence が動いていない。`git status --porcelain` に、(b)(c) 以外の変更が無い。
- `git pull --ff-only`。止まったら何も直さずに報告する（学校PC側でファイルが変わっている）。
- `watch.py` が変わったときは、監視タスクを再起動する（`jdrt-monitor-restart` の手順）。`mail_worker.py` が変わったときはワーカータスクを再起動する。