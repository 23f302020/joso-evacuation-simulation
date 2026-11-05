# SLIDE-PATTERN-pricing-plan-cards

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** pricing-plan-cards
**概要：** 3つの料金プランを横3列のカードで並べ、中央プランを「おすすめ」として強調表示する料金比較レイアウト
**適したシーン：** SaaSや教育サービスの料金プラン説明、オプション比較、グレード別提供内容の説明

## Structure（構造）

コンテンツエリアを3等分した横並びカードで構成する。各カードはプラン名ヘッダー・価格・特徴行（複数）で構成される。中央カードは「おすすめ」バッジ付きで上部に突出させるか、背景色を強調色にして目立たせる。左端に行ラベル列を設けることもある。

    structure:
      layout: three-column-cards
      left-col (optional):
        width: 120px
        elements: [row-label list]
      cards:
        count: 3
        middle_card: highlighted (recommended)
        card:
          header: [plan-name, recommended-badge (middle only)]
          price: [large-price-text]
          feature-rows: [label-value pairs or checkbox-list]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| 行ラベル列 | 最左（任意） | 各行が何の比較項目かを示す |
| プラン名 | 各カード上部ヘッダー | プラン名称 |
| おすすめバッジ | 中央カード上部 | 推奨プランであることを示す |
| 価格 | 各カード内（大フォント） | 月額料金・費用 |
| 機能行 | 価格下 | プランが持つ機能・特徴のリスト |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-pricing-plan-cardsのレイアウトで、[プランA/B/C]の3つのプランを比較し、[中央プラン]をおすすめとして強調してください。各プランに価格と[N]つの特徴行を入れてください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 中央の「おすすめ」プランは他と異なる背景色や枠線色を使い視覚的に際立たせる
- 機能行は左ラベル列を設けるか、各カード内に同じラベルを繰り返すかのどちらかで統一する
- 価格は大きなフォントサイズで表示し、料金単位（/月など）も必ず表示する
