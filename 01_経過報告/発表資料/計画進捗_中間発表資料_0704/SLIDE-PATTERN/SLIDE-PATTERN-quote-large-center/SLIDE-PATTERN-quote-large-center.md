# SLIDE-PATTERN-quote-large-center

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview
**パターン名：** quote-large-center
**概要：** 大きな引用符と引用テキストを中央に配置する視覚的インパクトのあるスライド。名言・統計・重要メッセージを強調したいときに使用する。
**適したシーン：** 名言・格言の紹介、重要な統計数値の強調、キーメッセージの印象付け、セクション冒頭の導入スライド

## Structure（構造）

```yaml
layout: quote-large-center
title_area: true
content_area:
  direction: column
  align: center
  justify: center
  padding: "32px 80px"
  gap: 16px
  elements:
    - type: quote_mark_open
      symbol: "“"
      font_size: 64px
      color: "#DDDDDD"
      align_self: flex-start
    - type: quote_text
      font_size: 18px
      color: "#333333"
      text_align: center
      line_height: 1.8
      font_style: italic
      lines: 2〜3行
    - type: divider
      width: 60px
      height: 1px
      color: "#CCCCCC"
    - type: attribution
      format: "— 著者名・出典"
      font_size: 13px
      color: "#888888"
      text_align: center
    - type: quote_mark_close
      symbol: "”"
      font_size: 64px
      color: "#DDDDDD"
      align_self: flex-end
```

## Elements（各要素の役割）

| 要素 | 役割 | 推奨テキスト量 |
|------|------|--------------|
| 開き引用符「"」 | 視覚的アクセント・引用の開始を示す | 1文字（装飾） |
| 引用テキスト | メインメッセージ・名言・統計 | 20〜60文字（2〜3行） |
| 区切り線 | 引用本文と出典を視覚的に分離 | 固定幅60px |
| 引用元テキスト | 出典・著者名・データソース | 「— ○○○」形式、15〜30文字 |
| 閉じ引用符「"」 | 視覚的アクセント・引用の終了を示す | 1文字（装飾） |

## Usage Guide（AIへの使い方）

### プロンプト例

```
SLIDE.md と SLIDE-PATTERN-quote-large-center.md を参照して、
以下の内容でスライドを作成してください。

【引用テキスト】
顧客が本当に求めているのは、製品ではなく
その製品がもたらす「体験」と「感情」である。

【引用元】
— マーケティング白書 2024

【スライドタイトル】
顧客理解の本質
```

### 注意点
- 引用テキストは短く力強い文章が効果的（60文字以内を推奨）
- 引用元は「— 著者名」または「— 出典（年）」の形式で統一する
- 統計を使う場合は「顧客の78%が〜と回答」のような断言形式が映える
- イタリック体は日本語フォントでは視覚的効果が薄いため、フォントウェイトで強調してもよい
