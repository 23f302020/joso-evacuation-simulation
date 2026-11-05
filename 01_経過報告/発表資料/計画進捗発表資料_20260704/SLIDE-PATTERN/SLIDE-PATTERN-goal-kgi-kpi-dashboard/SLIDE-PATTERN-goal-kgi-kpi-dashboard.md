# SLIDE-PATTERN-goal-kgi-kpi-dashboard

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。スライド生成AIや人間のデザイナーが一貫したレイアウトを再現できるよう、構造・要素・使用方法を定義します。

---

## Overview

| 項目 | 内容 |
|------|------|
| パターン名 | goal-kgi-kpi-dashboard |
| 別名・通称 | 目標KGI KPIダッシュボード |
| 用途 | 組織の目標ビジョンからKGI・KPIまでを4層構造で一覧表示するダッシュボードレイアウト |
| 適したコンテンツ | 年次目標発表、経営方針説明、事業計画スライド、OKR/KPI管理資料 |
| レイアウト種別 | 縦積み4層ダッシュボード |

---

## Structure

コンテンツエリアを上から下へ4層に分割する構造です。

```
┌──────────────────────────────────────────────┐
│ タイトルエリア（スライドタイトル）            │
├──────────────────────────────────────────────┤
│ 第1層：目標（横幅フル・中央配置）             │
├────────────┬────────────┬────────────────────┤
│ KGI①       │ KGI②       │ KGI③               │ ← 第2層：KGI（3列）
├────────────┼────────────┼────────────────────┤
│ KPI①       │ KPI②       │ KPI③               │ ← 第3層：KPI+棒グラフ（3列）
├──────────────────────┬─────────────────────-─┤
│ 重点施策①            │ 重点施策②             │ ← 第4層：施策（2列）
└──────────────────────┴───────────────────────┘
```

---

## Elements

### コンテンツエリア全体
- `display: flex; flex-direction: column; padding: 8px 24px; gap: 8px; flex: 1;`

### 第1層：目標エリア
- 横幅フル、`background: #F0F0F0; border: 1px solid #CCCCCC; padding: 6px 16px; text-align: center;`
- エリアラベル（`.area-label`）: 「目標」
- 目標テキスト: `font-size: 13px; font-weight: bold; color: #333;`

### 第2層：KGIエリア
- コンテナ: `display: flex; gap: 12px; padding: 4px 0;`
- 各KGIセル（3つ）: `flex: 1; border: 1px solid #E0E0E0; padding: 8px 12px; display: flex; flex-direction: column; gap: 4px;`
  - バッジ: `font-size: 10px; background: #E8E8E8; padding: 2px 6px; display: inline-block;` ← 「KGI①」「KGI②」「KGI③」
  - アイコン代替（省略可）
  - 数値: `font-size: 22px; font-weight: bold; color: #333;`
  - 単位: `font-size: 11px; color: #555;`
  - 期限テキスト: `font-size: 10px; color: #999;`

### 第3層：KPIエリア
- コンテナ: `display: flex; gap: 12px; padding: 4px 0;`
- 各KPIセル（3つ）: `flex: 1; border: 1px solid #E0E0E0; padding: 8px 12px;`
  - バッジ: 「KPI①」「KPI②」「KPI③」（KGIバッジと同スタイル）
  - ラベルテキスト: `font-size: 11px; font-weight: bold; color: #333;`
  - 簡易縦棒グラフ: `display: flex; align-items: flex-end; gap: 4px; height: 40px; padding-top: 4px;`
    - 各棒: `width: 12px; background: #CCCCCC;` + 適切な高さ（%で指定）

### 第4層：施策エリア
- コンテナ: `display: flex; gap: 12px;`
- 各施策ボックス（2つ）: `flex: 1; background: #F5F5F5; border: 1px solid #CCCCCC; padding: 8px 12px;`
  - バッジ: 「重点施策①」「重点施策②」
  - テキスト: `font-size: 12px; font-weight: bold; color: #333;`

---

## Usage Guide

### 適した場面
- 経営会議・全社方針発表での目標体系説明
- OKR/KPI設定会議のサマリースライド
- 四半期・年次レビュー資料のダッシュボードページ
- 事業計画書の冒頭ページ

### 入れるべき情報
| 層 | 記載内容 |
|----|--------|
| 第1層（目標） | 単一の目標ビジョン文またはスローガン（20〜40字程度） |
| 第2層（KGI） | 3つの重要目標指標（数値＋単位＋期限） |
| 第3層（KPI） | 各KGIに紐づく3つのKPI（進捗グラフ付き） |
| 第4層（施策） | 2つの重点施策タイトル |

### 注意点
- KGIの数値は大きく目立たせる（22px以上）
- 棒グラフの高さは実際のデータ比率を反映させること
- 各層のラベル（エリアラベル）は `area-label` クラスで統一する
- 施策テキストは1行に収まる短い表現を推奨
