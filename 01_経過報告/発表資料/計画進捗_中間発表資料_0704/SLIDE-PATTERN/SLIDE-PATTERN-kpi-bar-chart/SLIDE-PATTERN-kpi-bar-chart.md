# SLIDE-PATTERN-kpi-bar-chart

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** kpi-bar-chart
**概要：** 左側に大きなKPI数値と補足テキストを配置し、右側に棒グラフ（成長推移）を並べる2カラムレイアウト
**適したシーン：** ARR・売上・ユーザー数など単一の主要指標を大きく打ち出しながら、その推移グラフも同時に見せたい場面

## Structure（構造）

コンテンツエリアを左右に分割し、左側（約35%）に主要KPI数値を大きなフォントで表示、右側（約65%）に棒グラフを配置する。グラフ下部にオプションでサマリーテーブル（前年比・トピック等）を追加できる。

    structure:
      layout: two-column
      left:
        width: 35%
        type: kpi-text
        elements:
          - metric-name
          - primary-value (large)
          - secondary-metric-name
          - secondary-value (large)
          - period-note
      right:
        width: 65%
        type: bar-chart
        elements:
          - bar-chart
          - data-labels
          - growth-arrow (optional)
      bottom:
        type: summary-table (optional)
        elements: [yoy-row, topic-row]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| KPI指標名 | 左カラム上部 | 指標の名称（例：ARR、売上高） |
| 主要数値 | 左カラム中央（大文字） | 最新期の実績値を大きく強調 |
| サブ指標 | 左カラム下部 | 成長率など補助指標 |
| 棒グラフ | 右カラム全体 | 複数期の推移を時系列で視覚化 |
| 成長矢印 | グラフ上部オーバーレイ | 右肩上がりの成長トレンドを強調 |
| サマリーテーブル | 下部全幅（任意） | 各期のYoY成長率・トピックを一覧 |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-kpi-bar-chartのレイアウトで、左にARR[数値]億円・YoY[%]を大きく表示し、右に[年度]からの推移グラフを配置してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 左のKPI数値は60px以上の大きなフォントサイズで目立たせる
- 棒グラフの最新期のみ強調色を使い、他期は淡色にすると視点が定まる
- サマリーテーブルはグラフのデータ密度が高い場合に補足として有効
