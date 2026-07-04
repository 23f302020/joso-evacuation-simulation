# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** Anthropic公式サイト（https://www.anthropic.com/）
**マッチするシーン：** テクノロジー・AI関連のカンファレンス発表、企業向けプレゼン、研究発表、製品紹介、信頼性と先進性を訴求するフォーマルな資料

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | テラコッタ / コーラル | #CC785C |
| Secondary | ウォームクリーム | #EFE9DF |
| Background | オフホワイト / クリーム | #F5F0E8 |
| Accent | コーラルオレンジ | #CC785C |
| Text | ほぼ黒 | #1A1A1A |

```yaml
colors:
  primary: "#CC785C"
  secondary: "#EFE9DF"
  background: "#F5F0E8"
  accent: "#CC785C"
  text: "#1A1A1A"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 48px | Bold |
| 見出し（H2） | Noto Sans JP | 32px | Bold |
| 本文 | Noto Sans JP | 18px | Regular |
| キャプション | Noto Sans JP | 13px | Regular |

```yaml
typography:
  heading_h1:
    font: "Noto Sans JP"
    size: "48px"
    weight: "700"
  heading_h2:
    font: "Noto Sans JP"
    size: "32px"
    weight: "700"
  body:
    font: "Noto Sans JP"
    size: "18px"
    weight: "400"
  caption:
    font: "Noto Sans JP"
    size: "13px"
    weight: "400"
```

## Layout

- **スライドサイズ：** 16:9（幅960px × 高さ540px）
- **余白（上下）：** 64px
- **余白（左右）：** 80px
- **テキスト整列：** 左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "960px"
  height: "540px"
  padding_vertical: "64px"
  padding_horizontal: "80px"
  text_align: "left"
```

## Do / Don't

**Do（やること）**
- 1スライド1メッセージを徹底し、余白を広く取る
- コーラル（#CC785C）はアクセントとして控えめに使う
- テキストは少量に絞り、視覚的なヒエラルキーを明確にする
- クリーム〜オフホワイトの暖色系背景でぬくもりを演出する

**Don't（やってはいけないこと）**
- 原色・蛍光色・派手なグラデーションを使わない
- 1スライドに情報を詰め込みすぎない
- 複数のフォントファミリーを混在させない
- 黒（#000000）の純粋な黒を使わず、ソフトな #1A1A1A を使う
