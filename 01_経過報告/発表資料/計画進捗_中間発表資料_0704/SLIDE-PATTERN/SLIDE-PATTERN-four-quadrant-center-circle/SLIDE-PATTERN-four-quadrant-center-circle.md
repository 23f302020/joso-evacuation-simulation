# SLIDE-PATTERN-four-quadrant-center-circle

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** four-quadrant-center-circle
**概要：** スライド中央に大きな円を配置し、四隅（左上・右上・左下・右下）に各1つずつアイコン＋見出し＋説明テキストを配置する4象限レイアウト。中央の円が4つの要素を結びつけるハブの役割を持つ。
**適したシーン：** 1つの中心概念に関連する4要素の説明、4つの観点・視点・アプローチの提示、マトリクス的な情報整理、コアバリューと4つの価値要素の表現

## Structure（構造）

コンテンツエリア全体を4象限グリッドとして使用し、中央に絶対配置の円を重ねる構造。

    structure:
      layout: content-area-four-quadrant-center-circle
      position: relative
      padding: 12px 48px
      center-circle:
        position: absolute
        top: 50%
        left: 50%
        transform: translate(-50%, -50%)
        size: 120px × 120px
        border-radius: 50%
        border: 2px solid #CCCCCC
        background: #F8F8F8
        elements:
          - center-text (font-size: 11px, #888, text-align: center, 1〜2行)
      quadrant-grid:
        display: grid
        grid-template-columns: 1fr 1fr
        grid-template-rows: 1fr 1fr
        width: 100%
        height: 100%
        gap: 8px
      each-quadrant:
        display: flex
        flex-direction: column
        padding: 12px
        gap: 6px
        border: 1px dashed #E8E8E8
        elements:
          - icon-placeholder (40px × 40px, #F0F0F0, border-radius: 50%, border: 1px dashed #CCCCCC)
          - heading (font-size: 13px, bold, #333)
          - description (font-size: 11px, #666, line-height: 1.6, 2〜3行)

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| 中央円 | コンテンツエリア中心 | 4要素を結びつける中心概念・テーマを円形で表現 |
| 中央テキスト | 円の内部 | 中心概念の名称・キーワードを小さく表示 |
| 象限ボーダー | 各象限の外枠 | 破線で各象限を囲み、エリアを視覚的に分離 |
| アイコンプレースホルダー | 各象限上部 | 各要素を表すアイコンを配置する円形エリア |
| 象限見出し | アイコン下 | 各象限の内容を太字で短く表示 |
| 象限説明テキスト | 見出し下 | 各象限の詳細説明を2〜3行で記述 |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-four-quadrant-center-circleのレイアウトで、中央円テキスト「[中心概念]」、左上：見出し「[左上見出し]」説明「[左上説明]」、右上：見出し「[右上見出し]」説明「[右上説明]」、左下：見出し「[左下見出し]」説明「[左下説明]」、右下：見出し「[右下見出し]」説明「[右下説明]」のスライドを作成してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 中央円のテキストは1〜2語程度に簡潔にまとめること。長い文章は中央円に収まらない
- 4象限の説明テキストは2〜3行を目安とし、各象限で文量をそろえるとバランスが良い
- アイコンは各象限の内容を連想できるものを選ぶと視認性が上がる
- 中央円が大きいため、各象限のコンテンツは中央に寄りすぎないよう象限の外寄りに配置することを意識する
