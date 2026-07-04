# SLIDE-PATTERN: cover-gradient-text-bottom

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

---

## 概要

全面グラデーション背景スライド。タイトル・会社名・日付が左下エリアに縦積み、ロゴが右上に配置される表紙レイアウト。

---

## Structure

```
structure:
  layout: full-bleed
  background: gradient
  title_position: bottom-left
  elements:
    logo: top-right
    main_title: bottom-left (large, bold)
    subtitle_company: bottom-left (below title)
    date: bottom-left (below company)
```

---

## Elements

| 要素 | 配置 | 役割 |
|---|---|---|
| グラデーション背景 | 全面 | ブランドカラーのグラデーション（装飾的背景） |
| ロゴ | 右上 | 会社ロゴ・ブランドマーク |
| メインタイトル | 左下エリア | 資料のタイトル（大きなフォント・太字） |
| 会社名・証券コード | タイトル直下 | 発行元情報 |
| 日付 | 最下 | 資料の作成・発表日 |

---

## Usage Guide

- グラデーション背景はSLIDE.mdのブランドカラーを使用する
- タイトルは2〜3行まで対応。4行以上は文字サイズを下げる
- ロゴは白抜きまたは暗色（グラデーションとのコントラスト確保）
- テキスト色はグラデーション背景との視認性を確保するために白・明色系を推奨
- 左下テキストブロックはpadding-leftをスライド幅の5〜6%程度確保する
- 日付・会社名の文字サイズはタイトルの1/3〜1/2程度を目安にする
