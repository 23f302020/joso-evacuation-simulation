# SLIDE-PATTERN-before-after-two-col

このファイルはスライドのコンテンツエリア（タイトル行より下の領域）のレイアウトパターン定義書です。SLIDE.mdと組み合わせてAIツールに渡すことで、このパターンのスライドを生成できます。タイトルエリア・ページ番号・装飾はSLIDE.mdの `Slide Frame` セクションで定義されるため、このファイルには含みません。

## Overview
**パターン名：** before-after-two-col
**概要：** 「Before（課題・現状）」と「After（改善後・目標）」を左右2カラムで対比するパターン。中央の矢印で変化の方向を明示する。
**適したシーン：** ビジネス提案・改善提案・課題解決の提示・現状と目標の比較

## Structure（構造）

```yaml
layout: before-after-two-col
content_area:
  display: flex
  padding: "24px 40px"
  gap: 24px
  align-items: stretch

left_column:
  label: "BEFORE"
  label_style: "背景#F0F0F0、パディング8px 16px、font-size: 13px"
  border: "1px solid #CCCCCC"
  items:
    - type: list
      count: 3〜4
      marker: "×"
      marker_color: "#888"
      content: "現状の課題・問題点"

center_arrow:
  icon: "→"
  font_size: 32px
  color: "#CCCCCC"
  align: center（縦方向も中央揃え）

right_column:
  label: "AFTER"
  label_style: "背景#E8E8E8、border: 1px solid #CCCCCC、パディング8px 16px、font-size: 13px"
  border: "1px solid #CCCCCC"
  items:
    - type: list
      count: 3〜4
      marker: "○"
      marker_color: "#666"
      content: "改善後の状態・目標"
```

## Elements（各要素の役割）

| 要素 | 役割 | 推奨文字数 |
|------|------|-----------|
| BEFORE ラベル | 左カラムが「現状・課題」であることを示すヘッダー | 固定（"BEFORE"） |
| × リストアイテム | 現状の問題点・課題を箇条書きで列挙 | 1項目あたり20〜40文字 |
| 中央矢印（→） | BEFOREからAFTERへの変化・改善の方向を示す | 固定（"→"） |
| AFTER ラベル | 右カラムが「改善後・目標」であることを示すヘッダー | 固定（"AFTER"） |
| ○ リストアイテム | 改善後の状態・達成すべき目標を箇条書きで列挙 | 1項目あたり20〜40文字 |

## Usage Guide（AIへの使い方）

### プロンプト例

```
SLIDE.mdのデザインシステムと、以下のSLIDE-PATTERN-before-after-two-colパターンを使って
スライドを1枚生成してください。

【スライドタイトル】現状と改善後のギャップ

【BEFOREの内容（課題）】
- 手作業によるデータ入力でミスが多発している
- 情報共有が属人化しており引き継ぎが困難
- 承認フローが紙ベースで時間がかかる

【AFTERの内容（改善後）】
- システム連携で自動入力・エラーゼロを実現
- クラウド上で全員がリアルタイムに情報共有
- 電子承認で最短1日での処理が可能
```

### 注意点
- BEFOREとAFTERの項目数は揃えること（3〜4項目が最適）
- 各項目は対応関係が分かるよう順番を揃えると効果的
- 矢印は装飾のため、コンテンツとして変更しない
- カラム幅は左右対称（各約42%）、中央矢印は約8%が目安
