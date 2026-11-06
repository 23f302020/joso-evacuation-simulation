# GitHub運用ガイド

> このフォルダは、本研究リポジトリをGitHubで管理するときの恒久ルールと手順の正本である。
> 進捗・残タスクは書かない（`context.md`）。過去の同期記録は`00_全体整理/決定ログ.md`。
>
> **制定：** 2026-11-06（ユーザー指示「このpc上にあるローカルなプロジェクトのgithubにある該当フォルダの運用ガイドフォルダを詳細に定義しておいた方がいいね」）

---

## 対象

| 項目 | 値 |
|---|---|
| GitHubリポジトリ | [23f302020/joso-evacuation-simulation](https://github.com/23f302020/joso-evacuation-simulation)（**public**・MIT） |
| ローカル作業ツリー | `C:\Users\Ko_rr\Documents\Codex\研究室\4年次本研究`（親の`研究室/`はgit管理外） |
| 既定ブランチ | `master`（ブランチ保護なし） |
| 使用アカウント | **`23f302020`のみ**（→[03_push手順](03_push手順.md)） |

このPCで他にgitリポジトリは`OneDrive\ドキュメント\GitHub\car_oil_price`だけで、remote未設定のため本ガイドの対象外とする。

## 本番として扱う公開先

| 公開先 | URL | 更新契機 |
|---|---|---|
| GitHubリポジトリ本体 | https://github.com/23f302020/joso-evacuation-simulation | push した時点で公開 |
| GitHub Pages | https://23f302020.github.io/joso-evacuation-simulation/ | `master`へのpushで`04_プログラム/output/**`か`.github/workflows/deploy-pages.yml`が変わると自動デプロイ |
| Cloudflare（現状把握HTML） | https://joso-research-status.30k-012rei.workers.dev | GitHubとは別。ユーザーの明示指示があるときだけ手動配信 |

**完了報告では「ローカルのみ」「GitHub反映済み」「Pages本番反映済み」「Cloudflare反映済み」を区別して書く。**

## 基本ルール（要約）

1. **pushはユーザーの明示依頼があるときだけ。** 依頼のない自動push・ついでのpushをしない。
2. **アカウントは`23f302020`だけを使う。** `JI-life`には触れない（切替・ログアウト・トークン利用・設定変更をしない）。
3. **作業は作業ブランチで行い、同期時に`master`へfast-forwardする。** force push・履歴書換えをしない。
4. **公開範囲は`.gitignore`が正本。** `開発メモ/`・取得元原本・巨大データ・依存物・秘密情報は載せない。
5. **push前チェックリストを全部通す。** 秘密情報・除外対象・大容量・記録同期を確認する。
6. **push後はGitHub側を読み戻して一致を確認する。** Pagesが動いたら実行結果も確認する。
7. **`git restore`／`git checkout -- output/`は使わない**（CRLFがLF化しSHAゲートが壊れる。`CLAUDE.md`恒久禁止事項3）。

## ファイル構成

| ファイル | 内容 |
|---|---|
| [01_公開範囲と除外ルール.md](01_公開範囲と除外ルール.md) | 何をGitHubに載せ、何を載せないか。`.gitignore`の区分と変更手順 |
| [02_ブランチとコミット.md](02_ブランチとコミット.md) | ブランチ構成、命名、コミットメッセージ書式、masterへの反映方法 |
| [03_push手順.md](03_push手順.md) | アカウント運用、push前チェックリスト、実行コマンド、読み戻し確認 |
| [04_トラブル対応.md](04_トラブル対応.md) | 403、non-fast-forward、大容量、誤push等の対処 |

## 関連する正本

| 内容 | パス |
|---|---|
| 除外設定 | `../../.gitignore`・`../../.gitattributes` |
| Pagesデプロイ設定 | `../../.github/workflows/deploy-pages.yml` |
| 経過報告の記録方式（コミット本文に詳細を残す） | `../../CLAUDE.md`「変更・検証・記録」・`../../context.md` |
| 過去の同期実績（2026-10-20） | `../決定ログ.md`「Markdown先行・更新日別の経過報告とGitHub同期」 |
| 経緯：2026-06-25のリポジトリ改善計画（data除外・Pages allow-list・LICENSE） | `../../開発メモ/github改善案.md`（ローカルのみ・GitHub除外） |
