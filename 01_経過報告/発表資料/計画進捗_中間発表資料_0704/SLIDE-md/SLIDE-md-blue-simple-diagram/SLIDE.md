# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 青　シンプル　グラフ　図解のプレゼンテーション.pdf（日本語プレゼンテーション）
**マッチするシーン：** 教育・研修資料、ビジネス発表・提案資料、グラフや図解を多用した情報整理型プレゼン

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | スカイブルー | #29ABE2 |
| Secondary | ライトブルー | #A8DCF0 |
| Background | 白 | #FFFFFF |
| Accent | ほぼ黒 | #111111 |
| Text | ほぼ黒（本文） | #1A1A1A |

```yaml
colors:
  primary: "#29ABE2"
  secondary: "#A8DCF0"
  background: "#FFFFFF"
  accent: "#111111"
  text: "#1A1A1A"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 60px | Bold |
| 見出し（H2） | Noto Sans JP | 28px | Bold |
| 本文 | Noto Sans JP | 18px | Regular |
| キャプション | Noto Sans JP | 13px | Regular |

```yaml
typography:
  heading_h1:
    font: "Noto Sans JP"
    size: "60px"
    weight: "700"
  heading_h2:
    font: "Noto Sans JP"
    size: "28px"
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
- **余白（上下）：** 48px
- **余白（左右）：** 60px
- **テキスト整列：** セクションタイトルは中央寄せ、本文は左寄せ

```yaml
layout:
  slide_size: "16:9"
  width: "960px"
  height: "540px"
  padding_vertical: "48px"
  padding_horizontal: "60px"
  text_align: "left"
```

## Slide Frame

スライドの全ページに共通して適用される「枠」の要素を定義します。SLIDE-PATTERN-{name}.mdはコンテンツエリアの構造のみを定義するため、タイトルエリア・ページ番号・装飾はすべてここで一括管理します。これにより、どのパターンを使っても枠の見た目が統一されます。

**タイトルエリア：** 上部中央配置。点線（`·····`）で両側を挟んだブラケット形式で表示。例：`·············· [ グラフと図の効果的な使用法 ] ··············`。コンテンツパネルの外側・上部に配置し、パネル内には含めない。
**ページ番号：** なし
**装飾：** 左上と右サイドに有機的なウェーブ形状（ブロブ）を Primary（#29ABE2）と Secondary（#A8DCF0）のグラデーションで配置。コンテンツスライドでは白いインナーパネル（border: 1.5px solid #CDD8E3）をブロブの前面に配置する。

```yaml
slide_frame:
  title_area:
    position: "top-center"
    text_align: "center"
    decoration: "dotted-bracket"
    format: "·· [ タイトル ] ··"
  page_number:
    position: "none"
    format: "none"
  decoration: "gradient-blob-top-left-and-right"
  inner_panel:
    border: "1.5px solid #CDD8E3"
    border_radius: "3px"
    padding: "24px 32px"
    margin: "0 60px 16px"
```

## Do / Don't

**Do（やること）**
- 左上と右サイドにウェーブ形状のブルーグラデーションブロブ装飾を配置する
- セクションタイトルは `[ タイトル ]` 形式で両側に点線を添え、上部中央に配置する
- コンテンツは白いインナーパネル（細いボーダー付き）の中に整理して表示する
- グラフ・表・アイコンカードなど視覚要素を積極的に活用する
- 数字付き黒丸バッジ（セクション番号）でコンテンツ間の階層を明示する

**Don't（やってはいけないこと）**
- テキストのみのスライドを作らず、必ず図解・グラフ・アイコン等の視覚要素を使う
- ブロブ以外の派手な装飾要素を追加して画面を混雑させない
- 原色や高彩度の色を追加してブルー系の統一感を損なわない
- フォント種類を増やしてタイポグラフィの統一感を壊さない
