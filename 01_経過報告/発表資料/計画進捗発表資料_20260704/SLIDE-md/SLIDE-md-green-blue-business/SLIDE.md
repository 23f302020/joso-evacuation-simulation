# SLIDE.md

このファイルはスライドデザインシステムの定義書です。AIツール（Claude Design、NotebookLM、Google Slides等）にこのファイルを渡すことで、一貫したデザインのスライドを生成できます。

## Overview

**参照ソース：** 緑・青を基調としたビジネス向けプレゼンテーションデザイン（人材・採用業界向け営業・提案資料）
**マッチするシーン：** 顧客向けサービス提案、営業資料、BtoBビジネスのプレゼンテーション、フォーマルな社外向け発表資料

## Colors

| 役割 | カラー名 | HEXコード |
|---|---|---|
| Primary | ティールグリーン | #2BB5A0 |
| Secondary | スチールブルー | #3D9BC8 |
| Background | ホワイト | #FFFFFF |
| Accent | ディープティール | #17A899 |
| Text | ダークネイビー | #1A1A2E |

```yaml
colors:
  primary: "#2BB5A0"
  secondary: "#3D9BC8"
  background: "#FFFFFF"
  accent: "#17A899"
  text: "#1A1A2E"
  light_card: "#E8F7F5"
```

## Typography

| 役割 | フォント | サイズ | ウェイト |
|---|---|---|---|
| 見出し（H1） | Noto Sans JP | 48px | Bold |
| 見出し（H2） | Noto Sans JP | 32px | Bold |
| 本文 | Noto Sans JP | 18px | Regular |
| キャプション | Noto Sans JP | 14px | Regular |

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

**タイトルエリア：** 上部左寄せ。スライドタイトルの左に幅6px・タイトルと同じ高さのティールグリーン（#2BB5A0）縦アクセントバーを配置。サブタイトル（例：セクション番号や補足）はアクセントカラー（#17A899）で表示。
**ページ番号：** なし
**ロゴエリア：** 右上にロゴ画像または社名テキストを配置（ティールカラー推奨）
**フッター装飾：** 下部全幅に渡るグラデーションバー（#2BB5A0 → #3D9BC8、高さ36px）

```yaml
slide_frame:
  title_area:
    position: "top-left"
    text_align: "left"
    decoration: "accent-bar"
    accent_bar:
      width: "6px"
      color: "#2BB5A0"
  page_number:
    position: "none"
    format: "none"
  logo:
    position: "top-right"
    note: "ロゴ画像または社名テキストを配置（ティールカラー推奨）"
  footer:
    type: "gradient-bar"
    height: "36px"
    gradient: "linear-gradient(to right, #2BB5A0, #3D9BC8)"
```

## Do / Don't

**Do（やること）**
- ティールグリーン（#2BB5A0）とスチールブルー（#3D9BC8）のグラデーションで統一感を出す
- タイトル左のアクセントバーを必ず配置し、セクションの区切りを明確にする
- 強調ポイントはティールカラーのバッジ・枠・太字で視覚的に際立たせる
- 1スライドに1メインメッセージを配置し、見出し文でそのスライドの結論を伝える
- カードやボックスは薄いティール（#E8F7F5）またはホワイトで統一する

**Don't（やってはいけないこと）**
- 赤・オレンジ・紫など、ティール系と相反する派手な原色を使わない
- フッターのグラデーションバーを省略したり変色させない
- テキストを詰め込みすぎず、1スライドあたりの箇条書きは5項目以内に抑える
- 背景に柄・テクスチャ・写真を使用しない（白背景を維持する）
