# SLIDE-PATTERN-bar-chart-full

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** bar-chart-full
**概要：** コンテンツエリアの大半を棒グラフ（または棒＋折れ線の複合グラフ）が占め、右上にKPI数値バッジを配置する全幅グラフレイアウト
**適したシーン：** 売上・ARR・ユーザー数などの時系列推移を示す場面、数値の成長を強調したい場面

## Structure（構造）

コンテンツエリアはグラフエリアが大部分を占める単一レイアウト。上部に注釈行（凡例・単位）、中央に大型グラフ（棒グラフ＋オプションで折れ線オーバーレイ）、右上にKPI強調バッジ（最新値・成長率など）を配置する。

    structure:
      layout: single
      main:
        type: bar-chart
        overlay: line-chart (optional)
        position: full-width
      annotation_row:
        position: top-left of chart
        elements: [unit-label, legend-dots]
      kpi_badge:
        position: top-right of chart
        elements: [primary-value, secondary-value, growth-rate-badge]
      x_axis:
        elements: [period-labels]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| グラフエリア | コンテンツエリア中央〜全幅 | 棒グラフ（時系列）を大きく表示しデータを視覚化 |
| 凡例・単位ラベル | グラフ左上 | グラフの単位や複数系列の凡例を補足 |
| KPI強調バッジ | グラフ右上 | 最新期の主要数値と成長率を強調表示 |
| X軸ラベル | グラフ下部 | 期間（年・月・四半期など）を示す |
| データラベル | 棒グラフ上部（主要データ点） | 代表的な数値を棒グラフ上に直接表示 |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-bar-chart-fullのレイアウトで、[期間]の[指標名]推移を棒グラフで示し、右上に最新値[数値]・成長率[%]をバッジ表示してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- X軸のラベルが多い場合（12期以上）は斜め表示や省略を検討する
- 折れ線オーバーレイは比率指標（比率・率）を棒グラフの絶対値と同時に見せる際に効果的
- KPIバッジの最新期の棒は強調色（ブランドカラー）にすると視認性が上がる
