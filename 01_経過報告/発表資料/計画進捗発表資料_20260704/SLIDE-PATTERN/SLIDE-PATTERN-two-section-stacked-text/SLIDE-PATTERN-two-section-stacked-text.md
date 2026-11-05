# SLIDE-PATTERN-two-section-stacked-text

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** two-section-stacked-text
**概要：** コンテンツエリアを上下2セクションに分け、各セクションに見出し＋本文テキスト＋リストを配置する積み重ねテキストレイアウト。上段は見出し＋本文テキスト、下段は見出し＋本文テキスト＋番号付きリストの構成。
**適したシーン：** 背景説明と具体的なステップの組み合わせ、概要と手順の提示、課題と対応策のリスト、2つのトピックを縦に並べて説明する場面

## Structure（構造）

コンテンツエリアを上下2セクションに均等分割する。上段と下段の間に細い区切り線を設ける。各セクションは左端にアクセントボーダー付きの見出しを持つ。

    structure:
      layout: content-area-two-section-stacked
      padding: 20px 48px
      gap: 0
      upper-section:
        flex: 1
        border-bottom: 1px solid #E0E0E0
        padding: 16px 0 16px 0
        elements:
          - heading (font-size: 16px, bold, #333, border-left: 3px solid #CCCCCC, padding-left: 10px)
          - body-text (font-size: 13px, #555, line-height: 1.8, 2〜3行)
      lower-section:
        flex: 1
        padding: 16px 0 0 0
        elements:
          - heading (font-size: 16px, bold, #333, border-left: 3px solid #CCCCCC, padding-left: 10px)
          - body-text (font-size: 13px, #555, line-height: 1.8, 1行)
          - numbered-list (ol, font-size: 13px, #555, line-height: 2, 3項目)

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| 上段見出し | 上セクション上部 | 上段の主題を太字・左アクセントボーダー付きで表示 |
| 上段本文テキスト | 上段見出しの下 | 2〜3行の説明文。背景・概要・問題提起など |
| 区切り線 | 上段と下段の境界 | 2セクションを視覚的に分離する横線 |
| 下段見出し | 下セクション上部 | 下段の主題を太字・左アクセントボーダー付きで表示 |
| 下段本文テキスト | 下段見出しの下 | 1行の補足説明または導入文 |
| 番号付きリスト | 下段本文の下 | 3項目の手順・ポイント・対応策を番号付きで整理 |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-two-section-stacked-textのレイアウトで、上段見出し「[上段見出し]」本文「[上段本文2〜3行]」、下段見出し「[下段見出し]」本文「[導入文1行]」リスト「①[項目1] ②[項目2] ③[項目3]」のスライドを作成してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 上段・下段の縦の高さが均等になるよう、各セクションのテキスト量を調整すること
- 下段のリストは3項目が最適。4項目以上になる場合はフォントサイズを小さくするか別パターンを検討すること
- 番号付きリストは順序に意味がある場合（手順・優先順位）に使用し、順序がない場合は箇条書きに変更してよい
- 見出しの左アクセントボーダーにSLIDE.mdのブランドカラーを適用するとデザインが統一される
