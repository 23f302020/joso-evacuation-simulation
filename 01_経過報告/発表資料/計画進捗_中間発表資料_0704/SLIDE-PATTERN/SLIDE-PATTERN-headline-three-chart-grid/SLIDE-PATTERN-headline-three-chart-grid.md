# SLIDE-PATTERN-headline-three-chart-grid

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。スライド生成AIや人間のデザイナーが一貫したレイアウトを再現できるよう、構造・要素・使用方法を定義します。

---

## Overview

| 項目 | 内容 |
|------|------|
| パターン名 | headline-three-chart-grid |
| 別名・通称 | 見出し＋3グラフグリッド |
| 用途 | 上部の大きな見出し（キーメッセージ）と説明文、下部に3種類のグラフを並べてデータを多角的に解説するレイアウト |
| 適したコンテンツ | 市場分析報告、データドリブンな洞察提示、業績サマリー、調査結果発表 |
| レイアウト種別 | 上下分割（見出し＋3列グラフ） |

---

## Structure

コンテンツエリアを上部見出しゾーンと下部グラフゾーンに分割する構造です。

```
┌──────────────────────────────────────────────┐
│ タイトルエリア（スライドタイトル）            │
├──────────────────────────────────────────────┤
│ 大見出し（キーメッセージ・1〜2行）            │ ← 上部見出しゾーン
│ ─────────────────────────────────────── │
│ 説明テキスト（2行）                          │
├────────────┬────────────┬────────────────────┤
│ 横棒グラフ  │ 縦棒グラフ  │ 折れ線グラフ        │ ← 下部グラフゾーン（3列）
│ （パネル1） │ （パネル2） │ （パネル3）         │
└────────────┴────────────┴────────────────────┘
```

---

## Elements

### コンテンツエリア全体
- `display: flex; flex-direction: column; padding: 12px 40px; gap: 12px;`

### 上部見出しエリア
- `flex-shrink: 0;`
- 大見出し: `font-size: 18px; font-weight: bold; color: #333; line-height: 1.5;` — 1〜2行
- 区切り線: `border: none; border-top: 1px solid #CCCCCC; margin: 6px 0;`
- 説明テキスト: `font-size: 12px; color: #555; line-height: 1.7;` — 2行

### 下部グラフエリア（3列）
- コンテナ: `flex: 1; display: flex; gap: 16px; padding-top: 4px;`
- 各グラフパネル（3つ）: `flex: 1; border: 1px solid #E0E0E0; padding: 12px;`
  - パネル見出し: `font-size: 12px; font-weight: bold; color: #333;`
  - サブテキスト: `font-size: 10px; color: #888; margin-bottom: 6px;`

#### パネル1：横棒グラフ
- 5〜7本の横棒: `display: flex; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 10px; color: #555;`
- 棒部分: `height: 8px; background: #CCCCCC;` + 幅でデータ比率を表現

#### パネル2：縦棒グラフ
- グラフコンテナ: `display: flex; align-items: flex-end; gap: 3px; height: 80px;`
- 各棒: `width: 14px; background: #CCCCCC;` + 高さでデータ比率を表現

#### パネル3：折れ線グラフ（SVG）
```html
<svg width="100%" height="80" viewBox="0 0 160 80" preserveAspectRatio="none">
  <polyline points="10,60 40,45 70,55 100,25 130,20 150,30"
    fill="none" stroke="#CCCCCC" stroke-width="2"/>
  <line x1="0" y1="70" x2="160" y2="70" stroke="#EEEEEE" stroke-width="1"/>
</svg>
```

### 凡例・出典テキスト
- 凡例: `font-size: 10px; color: #888; margin-top: 6px;`
- 出典: `font-size: 10px; color: #AAAAAA; text-align: right; margin-top: 4px;`

---

## Usage Guide

### 適した場面
- 複数の指標を一画面で比較したいデータ分析スライド
- 市場動向・競合比較・業績推移を同時に見せたい場合
- プレゼンのデータパートの冒頭サマリーページ

### 入れるべき情報
| エリア | 記載内容 |
|--------|--------|
| 大見出し | 最も伝えたいキーメッセージ（30〜50字程度） |
| 説明テキスト | 見出しの根拠・補足説明（2行以内） |
| パネル1 | カテゴリ別の比較データ（横棒グラフ） |
| パネル2 | 期間別の量的変化（縦棒グラフ） |
| パネル3 | 時系列トレンド（折れ線グラフ） |

### 注意点
- 大見出しは1〜2行に収める（3行以上になるとグラフ領域が狭くなる）
- 各パネルのサブテキストにデータ期間・単位を明記すること
- 3つのグラフは互いに補完し合う関係にする（同一データを3種類で見せない）
- 出典テキストは全パネル共通で1行まとめて表示してもよい
