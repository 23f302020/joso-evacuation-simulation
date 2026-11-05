# SLIDE-PATTERN-pdca-cycle-diagram

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** pdca-cycle-diagram
**概要：** 中央に円形の回転サイクル図を配置し、四隅（左上・右上・左下・右下）に各フェーズの見出しと説明文を配置するダイアグラムレイアウト。
**適したシーン：** PDCAサイクル・4段階のプロセスサイクル・改善ループの説明・フレームワーク解説スライド

## Structure（構造）

コンテンツエリアは上下2行・左右2列の2×2グリッドと、中央に重なる円形ダイアグラムで構成される。上部には概要テキストエリア（リード文）を配置し、その下の2×2グリッドの中央に円形サイクル図をオーバーレイする。各グリッドセルには、アクセントカラーのフェーズ名と本文説明テキストが入る。

    structure:
      layout: center-diagram-with-four-corners
      top:
        content: lead-text
      center:
        diagram: circular-cycle
        segments: 4
        direction: clockwise
      corners:
        top-left: phase-block
        top-right: phase-block
        bottom-left: phase-block
        bottom-right: phase-block
      phase-block:
        elements: [phase-title, description-text]

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| リード文エリア | コンテンツ上部（全幅） | スライドの主旨や概要を1〜2行で説明するテキストブロック |
| 円形サイクル図 | 中央（グリッド中心） | 4つのフェーズが円環状に矢印でつながれた回転サイクルを表す図形 |
| フェーズタイトル | 各コーナー・上部 | フェーズ名（Plan/Do/Check/Action）をアクセントカラーで強調表示 |
| フェーズ説明テキスト | 各コーナー・タイトル下 | そのフェーズの概要を2〜4文程度で記述 |
| 上部右コーナー（Plan） | 右上 | 計画フェーズの説明 |
| 上部左コーナー（Action） | 左上 | 改善フェーズの説明 |
| 下部右コーナー（Do） | 右下 | 実行フェーズの説明 |
| 下部左コーナー（Check） | 左下 | 評価フェーズの説明 |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-pdca-cycle-diagramのレイアウトで、業務改善のPDCAサイクルを説明するスライドを作成してください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 中央の円形ダイアグラムはSVGまたはCSSで実装し、4分割の扇形（もしくはドーナツ型）を時計回りに配置する
- Plan（右上）→ Do（右下）→ Check（左下）→ Action（左上）の順が標準的な配置
- フェーズタイトルはSLIDE.mdのアクセントカラー（同色または濃淡違い）で表示する
- リード文は1〜2文に収め、詳細は各フェーズ説明テキストに委ねる
- このパターンはPDCA以外の4フェーズサイクル（例：発散・収束・実行・検証）にも応用可能
