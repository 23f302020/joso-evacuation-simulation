# 判断学習の技術説明 — ACEローカル窓口

2026-10-22導入。上流 [ace-agent/ace](https://github.com/ace-agent/ace) のコミット `82709de050e1db6e6ef2f07bcb0393560b94992a` を固定。Apache-2.0の原LICENSEは取得先に保持する。本窓口は実際の上流 `playbook_utils.py` を読み込み、ADDと評価カウンター更新を行う。ACEに似せてアルゴリズムを書き直したものではない。

日常の入口は[統一運用 §0.4](../../../05_タスク管理/スキル・エージェント運用.md)。本書は同じ仕組みのコマンド・導入/保守資料であり、別運用の入口ではない。[台帳](../../../00_全体整理/判断と結果の台帳.md)が判断と結果の根拠、ACEの最新snapshotが現在使う暫定基準を保持する。PAP・AGENTS・ユーザー指示に優先しない。

## 有効な機能と制約

- 現在のchatがGenerator/Reflector/Curatorの工程を順に行い、根拠のある教訓だけJSON deltaへ整理する。別agentは自動起動しない。
- `ace.ps1` が研究venvとは別のPythonを `-I` で起動する。上流ソース26件のSHAを適用前に照合し、dotenv自動探索を無効化、tokenizerは準備済みキャッシュを使う。Python監査hookで通信・socket待受・子プロセス・os.systemを拒否する。
- 操作はADDとhelpful/harmful/neutralの評価に限定。既存事例ID・元playbook SHA・単一writer・重複根拠を検査し、スナップショットを排他的に追記する。過去のsnapshotは上書きしない。
- 自動の外部LLM生成/省察/整理、意味類似度による重複排除、FiNER/AppWorld/Mind2Web評価は有効にしていない。APIキー不要のローカル限定構成。上流の名称`offline`も通常はAPI通信するため、本窓口と混同しない。
- これはPythonプロセス内の通信/操作制限であり、OSの権限隔離ではない。上流の評価CLIを直接起動すると本窓口の制限は掛からない。直接起動を運用対象にしない。

## 使い方

プロジェクトルートのPowerShellで実行する。

```powershell
& '.agents/tools/ace/ace.ps1' status
& '.agents/tools/ace/ace.ps1' show
& '.agents/tools/ace/ace.ps1' apply --delta '.agents/tools/ace/proposals/<new-proposal>.json'
```

いつ参照・記録・更新するかとchat間の担当は統一運用§0.4に従う。以下は同手順で使用するdeltaの書式。

```json
{
  "base_sha256": "statusが返す現行playbook_sha256",
  "operations": [
    {
      "type": "ADD",
      "section": "COMMON MISTAKES TO AVOID",
      "content": "適用条件・先にする確認・中止条件を含む一行の暫定教訓",
      "evidence": ["台帳の既存JD-ID"]
    }
  ],
  "bullet_tags": []
}
```

評価のみならoperationsを空配列にし、bullet_tagsに`{"id":"err-00001","tag":"helpful","evidence":["新しい結果事例ID"]}`を置く。既に同じ基準の評価へ使った根拠は再利用できない。カウンターは記録された評価数であり成功確率ではない。初期5基準は全カウンター0。

`state/000001.json`以降にplaybook本文・delta・前snapshot SHA・台帳読込時SHAを保存する。最新snapshotから`show`で表示し、別の手編集playbookを維持しない。破損・欠番・古い元版・writer.lock残存は停止する。失敗ファイル/lockを理由なく削除せず、本chatで調査する。証跡IDが存在することの検査は、証跡内容の正しさを保証しない。

## セキュリティ確認

[Codex Security生成報告](C:/Users/Ko_rr/.codex/state/plugins/codex-security/scans/ace-source-20261022/82709de050e1db6e6ef2f07bcb0393560b94992a_20261022T003730Z_cbuy4x3e/report.md)。上流のFiNER評価にCWE-95・中程度1件。取込targetがevalへ到達し、モデルpredictionのevalはtarget評価成功が追加前提。本窓口は該当評価器をimport/起動しない。上流そのものの修正完了や安全保証とは扱わない。

全Python runtime/評価CLI・主要設定/文書を静的確認。大規模データの意味的全件監査、未初期化AppWorld gitlink、依存実装/外部モデル/providerは未監査でcoverageはpartial。通常の全文ログ・最大1000再試行にも注意が必要なため、外部API経路は未接続。独立baseline/architectureと親のsource追跡を実施した。

最小コア22依存のpip-auditは既知脆弱性該当0。上流uv.lockをそのまま使わず、`requirements-core.lock`を2026-10-22にPyPIから解決し、wheel限定・SHA付きで固定。意味類似度/別provider用の重い依存は未導入。これは既知情報との照合であり依存コード全体の安全性証明ではない。

## 配置と再構築

- 上流：`%LOCALAPPDATA%/JDRT/tools/ace-source-20261022`
- 専用venv・token cache：`%LOCALAPPDATA%/JDRT/tools/ace-runtime-82709de/`
- 版/SHA/配置：`installation.json`。ローカルパスを含むが認証情報は含まない。
- 試験/実測記録：[ace_20261022](../../../06_研究結果/判断支援/ace_20261022/)。RED/GREENと実上流統合を含む20試験PASS、初期5基準の適用/再読込済み。研究runは追加しない。

再構築は同じコミットを取得して原ソースを照合し、専用Python3.13環境へ`uv pip sync requirements-core.lock --require-hashes --only-binary :all:`で依存を入れる。tokenizerキャッシュを準備してからinstallation.jsonの配置とSHAを実測更新し、下記試験を行う。設定ファイルだけ書いて導入成功としない。上流版/依存更新時は再監査・回帰検証が必要。

```powershell
& "$env:LOCALAPPDATA/JDRT/tools/ace-runtime-82709de/venv/Scripts/python.exe" -B -X utf8 -m unittest discover -s '.agents/tools/ace' -p test_ace_local.py
```

無効化は本窓口の呼出しをやめればよい。タスクスケジューラ、研究venv、SUMO、研究CLI/入力、ネットワーク常駐サービスは変更していない。既存台帳と履歴は保持する。導入による手戻り削減/成功確率向上は未測定。
