# SLIDE-PATTERN-three-card-icon-with-subheading

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。スライド生成AIや人間のデザイナーが一貫したレイアウトを再現できるよう、構造・要素・使用方法を定義します。

---

## Overview

| 項目 | 内容 |
|------|------|
| パターン名 | three-card-icon-with-subheading |
| 別名・通称 | 区切り見出し付き3カードアイコン |
| 用途 | 上部の区切り付きセクション見出しと、番号バナー・大アイコン・見出し・説明テキストを持つ3カードを横並びにするレイアウト |
| 適したコンテンツ | サービスの特徴説明、3つの強み・メリット提示、導入ステップ紹介、3分野のカテゴリ説明 |
| レイアウト種別 | 上下分割（区切り見出し＋3列カード） |

---

## Structure

コンテンツエリアを上部の区切り見出しと、下部の3カードに分割する構造です。

```
┌──────────────────────────────────────────────┐
│ タイトルエリア（スライドタイトル）            │
├──────────────────────────────────────────────┤
│ ──────── セクション見出しテキスト ──────── │ ← 区切り見出し
├────────────┬────────────┬────────────────────┤
│ ┌──────┐  │ ┌──────┐  │ ┌──────┐          │
│ │  01  │  │ │  02  │  │ │  03  │          │ ← 番号バナー
│ ├──────┤  │ ├──────┤  │ ├──────┤          │
│ │  ○   │  │ │  ○   │  │ │  ○   │          │ ← アイコン円
│ │見出し│  │ │見出し│  │ │見出し│          │
│ │説明  │  │ │説明  │  │ │説明  │          │
│ └──────┘  │ └──────┘  │ └──────┘          │
└────────────┴────────────┴────────────────────┘
```

---

## Elements

### コンテンツエリア全体
- `display: flex; flex-direction: column; padding: 12px 40px; gap: 12px;`

### 区切り見出しエリア
- コンテナ: `display: flex; align-items: center; gap: 16px; text-align: center;`
- 左線: `flex: 1; height: 1px; background: #CCCCCC;`
- 見出しテキスト: `font-size: 14px; font-weight: bold; color: #333; white-space: nowrap;`
- 右線: 左線と同スタイル

### 3カードグリッド
- コンテナ: `display: flex; gap: 16px; flex: 1;`
- 各カード（3つ）: `flex: 1; border: 1px solid #E0E0E0; background: #F8F8F8; display: flex; flex-direction: column;`

#### 番号バナー
- `padding: 4px 12px; background: #E8E8E8; border-bottom: 1px solid #CCCCCC; text-align: center;`
- 番号テキスト: `font-size: 12px; font-weight: bold; color: #555;` ← 「01」「02」「03」

#### カード本体
- `padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 10px; flex: 1;`
- アイコン円: `width: 56px; height: 56px; border-radius: 50%; background: #F0F0F0; border: 1px dashed #CCCCCC; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #AAAAAA;`
- カード見出し: `font-size: 14px; font-weight: bold; color: #333; text-align: center;`
- 説明テキスト: `font-size: 12px; color: #666; text-align: center; line-height: 1.6;`

---

## Usage Guide

### 適した場面
- 3つのサービス・製品の特徴を対等に並べて紹介したい場合
- 「理由」「メリット」「ステップ」など番号付きで説明したい場合
- アイコンでカテゴリを視覚的に区別したい場合
- セクション冒頭の「何を伝えるか」を明示してからカードへ誘導したい場合

### 入れるべき情報
| エリア | 記載内容 |
|--------|--------|
| 区切り見出し | セクションのテーマを端的に表す短いテキスト（10〜20字程度） |
| 番号バナー | 「01」「02」「03」の連番（または「A」「B」「C」など） |
| アイコン円 | カテゴリを表すアイコン（文字・SVG・絵文字等） |
| カード見出し | 各カードのキーワード（10〜20字） |
| 説明テキスト | 2〜4行程度の補足説明 |

### 注意点
- 説明テキストは3カードで文字量を揃えると整って見える
- アイコン円には実際のアイコン画像またはUnicode文字を使用可
- カードの高さは `flex: 1` により自動で揃う
- 区切り見出しが不要な場合は省略し、カードを上から配置してもよい
