# Codex AGENTS.md運用調査（2026-09-11）

## 目的

常総市JDRT v2の長期作業で、エージェントが古いPhase履歴を毎回読み込まず、現在地・禁止事項・逐次run手順を正しく取得できる構成へ直す。

## 公式情報

- OpenAI「Custom instructions with AGENTS.md」  
  https://learn.chatgpt.com/docs/agent-configuration/agents-md
- OpenAI「Model guidance」  
  https://developers.openai.com/api/docs/guides/latest-model

確認日：2026-09-11

## 公式仕様から確認した点

1. Codexは作業開始前に`AGENTS.md`を読む。
2. グローバル指示の後、プロジェクトルートから現在の作業ディレクトリまでを順に探索する。
3. 各ディレクトリでは`AGENTS.override.md`、`AGENTS.md`、設定済みfallback名の順で最大1ファイルを採用する。
4. ルートから近い順に結合されるため、作業ディレクトリに近い指示が後勝ちになる。
5. 結合サイズは既定32 KiBで、上限到達後は追加されない。
6. 指示チェーンはrunまたはTUIセッション開始時に再構築される。変更後に古い指示が見える場合は新しいセッションで確認する。
7. コードレビュー規則は、対象範囲、問題となる挙動、安全な代替または例外を簡潔に書く。
8. モデルは`AGENTS.md`やスキル内の指示へ敏感なため、重複・競合・不要な詳細を監査する必要がある。

## 本研究への適用判断

- 旧`AGENTS.md`内のPhase 1〜2作業ログ、データ一覧、旧タスク表、長いパス一覧を除外し、既存の専門文書へ委譲する。
- ルート`AGENTS.md`は、読込順、正本の役割、現在の研究境界、JDRT逐次run、安全規則、完了時記録だけを持つ。
- 変動値は`context.md`に一本化し、エージェントは`AGENT_CURRENT_END`までを通常読込範囲とする。
- JDRTの決定的処理は`.agents/skills/joso-jdrt-runner/`へ委譲し、詳細を必要時だけ開く。
- `CLAUDE.md`は他エージェントも共有する恒久ルールとして、`AGENTS.md`と矛盾しない研究境界へ更新する。
- 旧Phaseの履歴は削除せず、決定ログ、経過報告、Phase別文書、Git履歴に残す。

## 採用しなかった案

- `AGENTS.override.md`の追加：恒常的な現行方針であり一時上書きではないため不採用。
- 多数の入れ子`AGENTS.md`追加：現在の作業ディレクトリがルートであり、読込元を増やすと競合監査が難しくなるため不採用。
- `context.md`の履歴削除：履歴参照を維持しつつ読了マーカーで通常読込を短縮できるため不採用。

## 検証条件

- `AGENTS.md`が32 KiBを十分下回る。
- `context.md`のマーカーより上だけで現在の次タスクを特定できる。
- JDRT v2の対象、1セル制約、検証後記録、次セル解禁条件が`AGENTS.md`とスキルで一致する。
- `AGENTS.md`、`CLAUDE.md`、モデル運用基準、INDEX、JDRTタスクに矛盾するセル数を固定しない。
- Markdownリンクと参照パスが存在する。

