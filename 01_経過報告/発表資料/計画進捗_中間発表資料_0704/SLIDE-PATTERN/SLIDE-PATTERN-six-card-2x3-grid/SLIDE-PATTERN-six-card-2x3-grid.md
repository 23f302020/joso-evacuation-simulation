# SLIDE-PATTERN-six-card-2x3-grid

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。スライド生成AIや人間のデザイナーが一貫したレイアウトを再現できるよう、構造・要素・使用方法を定義します。

---

## Overview

| 項目 | 内容 |
|------|------|
| パターン名 | six-card-2x3-grid |
| 別名・通称 | 縦書きサイドバー付き2×3グリッド |
| 用途 | 左端の縦書きカテゴリラベルと右側の2行×3列グリッド（各カード：アイコン＋見出し＋説明）を組み合わせたコンパクトグリッドレイアウト |
| 適したコンテンツ | 6つのサービス/機能/特徴の一覧、製品ラインナップ、チームメンバー紹介、6段階プロセスの説明 |
| レイアウト種別 | 左サイドバー＋2×3グリッド |

---

## Structure

コンテンツエリアを左の縦書きサイドバーと右の2×3グリッドに分割する構造です。

```
┌──────────────────────────────────────────────┐
│ タイトルエリア（スライドタイトル）            │
├────┬─────────┬─────────┬──────────────────────┤
│    │ Card①   │ Card②   │ Card③               │ ← 上段
│ラ  ├─────────┼─────────┼──────────────────────┤
│ベ  │ Card④   │ Card⑤   │ Card⑥               │ ← 下段
│ル  │         │         │                      │
└────┴─────────┴─────────┴──────────────────────┘
  ↑
縦書きサイドバー（カテゴリ名）
```

---

## Elements

### コンテンツエリア全体
- `display: flex; flex: 1; padding: 12px 16px; gap: 16px;`

### 左サイドバー
- `width: 40px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;`
- サイドバーラベル: `font-size: 11px; color: #888; writing-mode: vertical-rl; text-orientation: mixed; letter-spacing: 0.1em;`

### 右グリッドエリア
- `flex: 1; display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(2, 1fr); gap: 12px; height: 100%;`

### 各カード（6つ）
- `border: 1px solid #EEEEEE; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px;`
  - アイコン円: `width: 44px; height: 44px; border-radius: 50%; border: 1px solid #CCCCCC; background: #F5F5F5; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #AAAAAA;`
  - 見出し: `font-size: 13px; font-weight: bold; color: #333;`
  - 説明テキスト: `font-size: 11px; color: #666; line-height: 1.6;` — 2行程度

---

## Usage Guide

### 適した場面
- 6つの項目を同一カテゴリとして整理して見せたい場合
- 情報量が多く4カード（2×2）では収まらない場合
- カテゴリ名を縦書きで強調したい場合
- アイコンで各項目を視覚的に識別させたい場合

### 入れるべき情報
| エリア | 記載内容 |
|--------|--------|
| サイドバーラベル | カテゴリ名またはセクション名（4〜8字程度） |
| アイコン円 | 各カードの内容を示すアイコン（文字・SVG・絵文字） |
| カード見出し | 項目タイトル（8〜15字程度） |
| 説明テキスト | 2行以内の補足説明 |

### 注意点
- 1カードの説明テキストは2行以内に収める（グリッドセルの高さが均等に保たれる）
- 見出しが長い場合は `font-size: 12px` に縮小して対応する
- アイコン円のサイズは44pxを基準とし、グリッド密度に応じて36〜48pxの範囲で調整可
- サイドバーラベルが不要な場合は左サイドバーを省略して `padding: 12px 40px` を使用する
