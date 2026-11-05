# SLIDE-PATTERN-summary-three-points

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview
**パターン名：** summary-three-points
**概要：** 「まとめ」スライド用のシンプルな3点ポイントリスト。チェックマーク付きで視認性が高く、プレゼンのクロージングに最適。
**適したシーン：** プレゼンのまとめ・要点の整理・議論の結論提示・次のアクションへの導入

## Structure（構造）

```yaml
layout: summary-three-points
content_area:
  display: flex
  flex-direction: column
  justify-content: center
  padding: "24px 80px"
  gap: 16px

summary_label:
  text: "SUMMARY"
  style: "area-label（font-size: 11px、color: #999、letter-spacing: 0.08em）"
  margin_bottom: 4px

point_items:
  count: 3
  each:
    display: flex
    align-items: flex-start
    gap: 20px
    padding: "14px 0"
    border-bottom: "1px solid #F0F0F0"
    check_icon:
      width: 28px
      height: 28px
      border: "2px solid #CCCCCC"
      display: flex
      align-items: center
      justify-content: center
      font_size: 14px
      color: "#888"
      flex_shrink: 0
      content: "✓"
    text_block:
      heading:
        font_size: 15px
        font_weight: bold
        color: "#333"
      body:
        font_size: 13px
        color: "#666"
        margin_top: 4px
```

## Elements（各要素の役割）

| 要素 | 役割 | 推奨文字数 |
|------|------|-----------|
| SUMMARYラベル | まとめスライドであることを明示するセクション識別子 | 固定（"SUMMARY"） |
| チェックボックスアイコン（✓） | 各ポイントが達成・確認済みの事項であることを視覚的に示す | 固定（"✓"） |
| ポイント見出し | まとめの要点・結論を簡潔に記述 | 20〜35文字 |
| ポイント補足テキスト | 見出しを補完する詳細説明や根拠 | 30〜60文字 |

## Usage Guide（AIへの使い方）

### プロンプト例

```
SLIDE.mdのデザインシステムと、以下のSLIDE-PATTERN-summary-three-pointsパターンを使って
スライドを1枚生成してください。

【スライドタイトル】本日のまとめ

【ポイント 1】
- 見出し: 顧客体験の向上が売上増加の最大要因
- 補足: NPS改善により既存顧客の継続率が前年比+8%向上し、売上にも直結した

【ポイント 2】
- 見出し: デジタル化により業務効率が大幅に改善
- 補足: 手作業の80%をシステムに移行し、1人あたりの処理件数が2.3倍に増加

【ポイント 3】
- 見出し: 次四半期は新市場開拓を最優先課題とする
- 補足: 東南アジア3カ国での展開準備を進め、来期Q1中のローンチを目指す
```

### 注意点
- 3つのポイントは重要度順または論理的な順序で並べること
- 見出しは体言止めか短文で統一し、補足テキストと文体を揃える
- チェックマークは完了・確認済みの印象を与えるため、今後の展望より達成済みの事実に使うと効果的
- 4点以上ある場合はポイントを絞るか、別パターン（numbered-list-with-body等）を検討する
