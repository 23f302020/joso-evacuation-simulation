# SLIDE-PATTERN-three-kpi-big-number

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview
**パターン名：** three-kpi-big-number
**概要：** 3つのKPI（重要指標）を大きな数字で横並びに表示する実績・成果報告スライド。インパクトある数字を前面に出すことで成果を印象付ける。
**適したシーン：** 事業実績報告・KPI達成状況の発表・プロジェクト成果報告・投資家向けサマリー

## Structure（構造）

```yaml
layout: three-kpi-big-number
content_area:
  display: flex
  padding: "20px 48px"
  gap: 24px
  align-items: center

kpi_columns:
  count: 3
  each:
    flex: 1
    border: "1px solid #E0E0E0"
    display: flex
    flex-direction: column
    align-items: center
    padding: "28px 16px"
    gap: 8px

each_kpi_structure:
  - area_label: "KPI ラベル（指標名）"
  - big_number:
      font_size: 48px
      font_weight: bold
      color: "#333"
      unit:
        font_size: 20px
        color: "#888"
        layout: "数字と横並び"
  - description:
      font_size: 13px
      color: "#666"
      text_align: center
  - supplement:
      font_size: 11px
      color: "#999"
      content: "前回比 +XX% など"

divider:
  between_columns: true
  style: "1px solid #EEEEEE"
  height: "60%"
  align: center
```

## Elements（各要素の役割）

| 要素 | 役割 | 推奨文字数・値 |
|------|------|--------------|
| エリアラベル（KPIラベル） | どの指標を示しているかの名称 | 6〜12文字（例：「月間売上高」「新規顧客数」） |
| 大きな数字 | 最も訴求したい数値・実績 | 数値のみ（単位は別要素） |
| 単位 | 数値の単位（円・件・%など） | 1〜4文字 |
| 説明テキスト | 数値が何を示すかの補足説明 | 20〜40文字 |
| 補足テキスト | 前回比・目標達成率などの追加情報 | 10〜20文字 |

## Usage Guide（AIへの使い方）

### プロンプト例

```
SLIDE.mdのデザインシステムと、以下のSLIDE-PATTERN-three-kpi-big-numberパターンを使って
スライドを1枚生成してください。

【スライドタイトル】第3四半期 実績サマリー

【KPI 1】
- ラベル: 月間売上高
- 数値: 4.8
- 単位: 億円
- 説明: 前年同期比で過去最高を更新
- 補足: 前回比 +23%

【KPI 2】
- ラベル: 新規顧客数
- 数値: 312
- 単位: 社
- 説明: 3ヶ月連続で月次目標を達成
- 補足: 目標達成率 104%

【KPI 3】
- ラベル: 顧客継続率
- 数値: 96.2
- 単位: %
- 説明: 業界平均を10ポイント上回る
- 補足: 前回比 +1.8pt
```

### 注意点
- 大きな数字は1〜4桁が最も見やすい（5桁以上の場合は万・億などの単位に変換する）
- 3つのKPI間で補足テキストの表現スタイルを統一する（すべて「前回比」または「達成率」など）
- 縦区切り線はカラム間の視覚的な分離のみが目的であり、コンテンツとしては含まない
- デザインシステムのアクセントカラーを数字部分に使うと訴求力が上がる
