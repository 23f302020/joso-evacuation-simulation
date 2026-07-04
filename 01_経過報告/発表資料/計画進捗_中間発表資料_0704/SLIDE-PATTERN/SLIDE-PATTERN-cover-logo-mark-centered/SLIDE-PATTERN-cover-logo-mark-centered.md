# SLIDE-PATTERN: cover-logo-mark-centered

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

---

## 概要

ロゴマーク（シンボル）を上部に置き、その直下にタイトル・会社名・日付・付加情報を縦に積み上げた中央揃えの表紙レイアウト。

---

## Structure

```
structure:
  layout: single-column
  alignment: center
  elements:
    logo_mark: top-center (large symbol)
    main_title: below-logo (large, bold)
    company_name: below-title
    date: below-company
    additional_info: below-date (stock code etc.)
```

---

## Elements

| 要素 | 配置 | 役割 |
|---|---|---|
| ロゴマーク | 中央上部 | シンボルロゴ（円形・モノグラム等） |
| メインタイトル | マーク直下 | 資料の主タイトル（大きなフォント） |
| 会社名 | タイトル下 | 正式会社名（中フォント・太字） |
| 日付 | 会社名下 | 作成・発表年月 |
| 付加情報 | 最下部 | 証券コード・市場区分等 |

---

## Usage Guide

- ロゴマーク（シンボル）がないブランドの場合はロゴ横長タイプに差し替え可能
- タイトルと会社名の間の仕切り線はブランドカラーを適用
- 5〜6要素の縦積みが標準。それ以上増やすと間隔が詰まる
- ロゴマークのサイズはスライド高さの13〜15%程度を目安にする
- 仕切り線の幅は40〜60px程度。ブランドカラーのアクセントラインとして機能する
- 付加情報（証券コード等）はオプション。不要な場合は省略可能
