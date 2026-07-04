このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

---

# SLIDE-PATTERN: two-circle-bilateral-flow

## Overview

左右に大きな円を配置し、中央に双方向の水平矢印を通したサイクル図。左右の円の中にサブ要素（小円・タグ等）を含め、矢印の上下にフロー名ラベルを配置する。

## 適したシーン

2つの主体・組織・概念が互いに交流・影響しあうサイクル（社会還元サイクル、エコシステム、Win-Win関係等）を示すとき。

## Structure

```yaml
structure:
  layout: bilateral-flow
  left_circle:
    size: large
    content: [entity-name, sub-items]
  center:
    elements: [arrow-right, arrow-left, flow-labels]
  right_circle:
    size: large
    content: [entity-name, sub-items]
  bottom_labels: [left-entity-name, right-entity-name]
```

## Elements

| 要素 | 配置 | 役割 |
|---|---|---|
| 左大円 | 左寄り中央 | 主体Aを表す大きな円形。内部にサブ要素を含む |
| 右大円 | 右寄り中央 | 主体Bを表す大きな円形。内部にサブ要素を含む |
| 右向き矢印ブロック | 中央上部 | 左→右へのフロー（公益活用・データ提供等） |
| 左向き矢印ブロック | 中央下部 | 右→左へのフロー（社会還元・対価等） |
| フロー名ラベル | 矢印の上下 | 各フローの名称・内容を示すテキスト |
| ボトムラベル | 各円の直下 | 主体の呼称（「生活者」「企業」等） |

## Usage Guide

- 左右の円は同じサイズで配置するのが原則。大きさに差をつけると主従関係が生まれる
- 矢印は太めの帯状（シェブロン形）にするとフロー感が強調される
- 円の中のサブ要素は3〜5個が最適
- ボトムラベルは円の下に大きめのテキストで配置
