# SLIDE-PATTERN-cycle-diagram-with-labels

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** cycle-diagram-with-labels
**概要：** 中央に回転サイクル図形（円形の矢印フロー）を配置し、四隅に各フェーズの詳細テキストを配置するレイアウト
**適したシーン：** PDCAサイクル、業務改善サイクル、循環プロセスの説明

## Structure（構造）

コンテンツエリア中央に大きなサイクル図形（円形または円弧型の矢印を持つ4分割構成）を配置する。図形の四隅（左上・右上・左下・右下）にそれぞれのフェーズ名と説明文ボックスを配置する。図形の中心にはコアコンセプト名を置く。

    structure:
      layout: center-diagram-with-corner-labels
      center:
        type: circular-cycle-diagram
        segments: 4
        center-label: [core-concept-text]
      corners:
        top-left: [phase-name, description]
        top-right: [phase-name, description]
        bottom-left: [phase-name, description]
        bottom-right: [phase-name, description]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| サイクル図形 | コンテンツエリア中央 | 4フェーズの循環・繰り返しを視覚化 |
| 中心ラベル | 図形の中心 | プロセス全体のコアコンセプト名 |
| フェーズ名（H3） | 四隅各エリア上部 | そのフェーズ（Plan/Do/Check/Action等）の名称 |
| フェーズ説明 | フェーズ名の下 | そのフェーズの概要説明（2〜4行） |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-cycle-diagram-with-labelsのレイアウトで、PDCAサイクルを表現し、四隅にPlan/Do/Check/Actionの説明を記述してください。中心に「継続改善」と表示してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 4フェーズ固定のパターン。3フェーズや5フェーズのサイクルには向かない
- 四隅の説明文は各100字程度（3〜4行）に収めるとバランスが良い
- サイクル図形のセグメントカラーはフェーズごとに濃淡を変えると見やすい
