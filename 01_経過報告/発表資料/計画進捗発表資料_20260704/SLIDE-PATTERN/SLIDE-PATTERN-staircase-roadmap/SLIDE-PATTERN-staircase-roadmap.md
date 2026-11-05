# SLIDE-PATTERN-staircase-roadmap

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** staircase-roadmap
**概要：** 左から右へ段階的に高くなる階段形状で4つのフェーズ・ステップを表現するロードマップレイアウト
**適したシーン：** 事業の成長フェーズ、プロジェクトのロードマップ、段階的な計画の提示

## Structure（構造）

コンテンツエリアに左下から右上へ向かう階段図形を配置する。各段（ステップ）の上部または内部にステップ番号・見出しを、段の上部に吹き出し/テキストエリアで詳細説明を配置する。X軸下部に期間ラベル（例：1ヶ月、3ヶ月など）を追加できる。

    structure:
      layout: staircase
      steps: 4
      direction: left-to-right (ascending)
      step:
        shape: filled-rectangle (progressive height)
        label_position: above or inside
        elements: [step-number, step-title, description-text]
      timeline_bar:
        position: bottom
        elements: [period-labels]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| 階段図形 | コンテンツエリア全体 | 左から右へ段階的成長を視覚化 |
| ステップ番号 | 各段上部または内部 | フェーズ番号（Step01等） |
| ステップ見出し | 番号下 | フェーズのキーワード |
| 説明テキスト | 各段の吹き出しエリア | そのフェーズの主な内容（2〜3行） |
| 期間ラベル | 下部X軸エリア | 各ステップの期間（例：1ヶ月、5ヶ月） |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-staircase-roadmapのレイアウトで、4つのフェーズ（[フェーズ1]〜[フェーズ4]）を階段形式で表現し、各フェーズの期間と主な内容を入れてください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 各段の幅は均等でなくても良い（期間に応じて調整可）
- 最後の段（最右）を最も強調色にすることで「到達目標」を明示できる
- 段の高さが低い段（左端）はテキストが入らない場合があるため、吹き出し形式で上部に配置する
