# SLIDE-PATTERN-numbered-list-with-body

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview

**パターン名：** numbered-list-with-body
**概要：** 3つの項目を縦に並べ、各項目に番号バッジ（または図形アイコン）・見出し・本文を配置する縦リストレイアウト
**適したシーン：** 特徴・メリット・要素の列挙、優先度付きリスト、段階的な説明

## Structure（構造）

コンテンツエリアを3行に分割し、各行が独立した区切り線（または薄いボーダー）で区切られる。各行の左側に番号または図形バッジ、右側に見出しと本文を配置する。

    structure:
      layout: single-column-list
      items: 3
      item:
        left:
          type: badge
          shape: circle or hexagon or square
          elements: [number]
        right:
          elements: [heading-h2, body-text]
      divider: horizontal-line between items

## Elements（各要素の役割）

| 要素 | 配置 | 役割 |
|---|---|---|
| 番号バッジ | 各行左端 | 項目の順番や番号を視覚的に示す |
| 見出し（H2） | バッジ右・上部 | 各項目のキーワードや主張 |
| 本文 | 見出しの下 | 見出しを補足する説明文（1〜3行） |
| 区切り線 | 各行間 | 項目の区切りを明確にする |

## Usage Guide（AIへの使い方）

このパターンをAIに指示する際のプロンプト例：

> 「SLIDE-PATTERN-numbered-list-with-bodyのレイアウトで、[項目1の見出し]・[項目2の見出し]・[項目3の見出し]それぞれの説明を入れてください。デザインはSLIDE.mdに従ってください。」

**注意点：**
- 項目が4つ以上になると縦に詰まりすぎる。4項目以上はfour-card-2x2またはsix-card-two-columnを検討
- 番号バッジは01/02/03形式または1/2/3形式のどちらでも対応可能
- 見出しは短く（10字以内）、本文は2〜4行を目安にする
