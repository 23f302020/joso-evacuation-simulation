# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** デジタル庁デザインシステム（DADS）β版 — https://design.digital.go.jp/dads/
**マッチするシーン：** 行政・官公庁向けビジネス資料、政策説明資料、組織内の公式プレゼンテーション、DX推進・デジタル化関連の提案資料

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ブルー800（強い官公庁ブルー） | #0031d8 |
| Secondary | ブルー100（ライトブルー） | #d9e6ff |
| Background | ホワイト | #ffffff |
| Accent | ブルー700（インタラクティブブルー） | #264af4 |
| Text | グレー900（ほぼ黒） | #1a1a1a |

```yaml
colors:
  primary: "#0031d8"
  secondary: "#d9e6ff"
  background: "#ffffff"
  accent: "#264af4"
  text: "#1a1a1a"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 48px | Bold |
| 見出し（H2） | Noto Sans JP | 36px | Bold |
| 本文 | Noto Sans JP | 16px | Regular |
| キャプション | Noto Sans JP | 14px | Regular |

```yaml
typography:
  heading_h1:
    font: "Noto Sans JP"
    size: "48px"
    weight: "700"
  heading_h2:
    font: "Noto Sans JP"
    size: "36px"
    weight: "700"
  body:
    font: "Noto Sans JP"
    size: "16px"
    weight: "400"
  caption:
    font: "Noto Sans JP"
    size: "14px"
    weight: "400"
```

## Layout

- **スライドサイズ：** 16:9（幅960px × 高さ540px）
- **余白（上下）：** 48px
- **余白（左右）：** 64px
- **テキスト整列：** 左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "960px"
  height: "540px"
  padding_vertical: "48px"
  padding_horizontal: "64px"
  text_align: "left"
```

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部左寄せ。タイトルテキスト直下に幅48px・高さ4px・Primaryカラー（#0031d8）のアクセントバーを配置。
**ページ番号：** 右下・数字のみ（例：1）・キャプションサイズ（14px）・テキストカラー（#1a1a1a）
**装飾：** スライド左端に幅4px・Primaryカラー（#0031d8）のアクセントバー（高さはコンテンツエリア分）

```yaml
slide_frame:
  title_area:
    position: "top-left"
    text_align: "left"
    decoration: "accent-bar"
  page_number:
    position: "bottom-right"
    format: "1"
  decoration: "accent-bar"
```

## Do / Don't

**Do（やること）**
- 1スライドに伝えるメッセージを1つに絞る（情報の過密を避ける）
- Primaryカラー（#0031d8）とホワイト（#ffffff）のコントラスト比4.5:1以上を常に確保する
- 箇条書きは最大5項目まで。各項目は短く簡潔にまとめる
- 図表・グラフはシンプルなCSSのみで表現し、過度な装飾を避ける

**Don't（やってはいけないこと）**
- グラデーション、影の多用、装飾的なイラストの使用は避ける
- Accentカラー（#264af4）を複数箇所に多用しない（強調の効果が薄れる）
- 文字サイズをキャプション（14px）より小さくしない（アクセシビリティ確保）
- 赤・オレンジなどの色をメインカラーとして使わない（エラー・警告の意味を持つため）
