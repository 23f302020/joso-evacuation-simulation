# SLIDE-PATTERN-action-items-list

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview
**パターン名：** action-items-list
**概要：** アクションアイテム（次のステップ・タスク一覧）を番号付きリストで示すスライド。担当者・期限カラムを持ち、会議の締めや計画発表に使いやすい。
**適したシーン：** 会議のまとめ・プロジェクトキックオフ・次のステップの共有・タスク割り当て

## Structure（構造）

```yaml
layout: action-items-list
content_area:
  display: flex
  flex-direction: column
  padding: "16px 48px"
  gap: 0

action_label:
  text: "ACTION ITEMS"
  style: "area-label（font-size: 11px、color: #999、letter-spacing: 0.08em）"
  margin_bottom: 8px

header_row:
  display: grid
  grid_template_columns: "32px 1fr 100px 100px"
  gap: 16px
  padding: "8px 0"
  border_bottom: "2px solid #CCCCCC"
  font_size: 11px
  color: "#999"
  columns:
    - "No"
    - "アクション"
    - "担当"
    - "期限"

action_rows:
  count: 4〜5
  each:
    display: grid
    grid_template_columns: "32px 1fr 100px 100px"
    gap: 16px
    padding: "10px 0"
    border_bottom: "1px solid #F0F0F0"
    cells:
      number:
        width: 32px
        height: 32px
        background: "#F0F0F0"
        border_radius: 50%
        font_size: 12px
        font_weight: bold
        color: "#555"
        display: flex
        align_items: center
        justify_content: center
      action_text:
        font_size: 14px
        color: "#333"
      assignee:
        font_size: 13px
        color: "#555"
        background: "#F5F5F5"
        padding: "2px 8px"
        border_radius: 4px
        display: inline-block
      deadline:
        font_size: 13px
        color: "#666"
```

## Elements（各要素の役割）

| 要素 | 役割 | 推奨文字数・値 |
|------|------|--------------|
| ACTION ITEMSラベル | アクションアイテム一覧であることを明示 | 固定（"ACTION ITEMS"） |
| ヘッダー行 | 各カラムの列ラベル | 固定（No / アクション / 担当 / 期限） |
| 番号バッジ | タスクの順番・優先順位を示す番号 | 1桁〜2桁の数字 |
| アクション内容 | 実施すべき具体的なタスク・アクション | 25〜50文字 |
| 担当者 | そのタスクの責任者・担当チーム名 | 4〜10文字 |
| 期限 | タスクの完了期日 | 「MM/DD」または「〇月〇日」形式 |

## Usage Guide（AIへの使い方）

### プロンプト例

```
SLIDE.mdのデザインシステムと、以下のSLIDE-PATTERN-action-items-listパターンを使って
スライドを1枚生成してください。

【スライドタイトル】次回ミーティングまでのアクションアイテム

【アクションアイテム一覧】
1. アクション: 要件定義書の最終レビューと承認
   担当: 田中（PM）
   期限: 6/10

2. アクション: デザインモックアップの作成（3画面分）
   担当: 山田（デザイン）
   期限: 6/12

3. アクション: APIエンドポイント仕様書の作成
   担当: 鈴木（開発）
   期限: 6/12

4. アクション: ステークホルダーへの進捗報告メール送付
   担当: 田中（PM）
   期限: 6/14

5. アクション: テスト環境のセットアップ確認
   担当: 開発チーム全員
   期限: 6/15
```

### 注意点
- アクション内容は「〜すること」「〜を行う」など動詞で終わる形式に統一する
- 担当者は個人名またはチーム名で記載し、複数担当の場合は「チーム名 全員」などと表記する
- 期限は短い形式（月/日）を使用してカラム幅を節約する
- 4〜5件が最適。6件以上になる場合は次回以降のアイテムと分けるか、別ページに分割する
