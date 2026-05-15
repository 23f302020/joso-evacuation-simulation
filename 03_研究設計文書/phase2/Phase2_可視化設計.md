# Phase 2 可視化設計：SUMO結果のHTML表示

作成日：2026/05/14  
対象：Phase 2 シナリオA（自家用車避難）の走行結果をブラウザ上で確認する

---

## 1. 目的と方針

現在の `output/index.html` はExcelファイルのダウンロードのみ対応している。  
シミュレーション走行結果（車両軌跡・道路閉鎖・避難到着）をHTML上でアニメーション再生できるようにする。

### 採用方針：FCD出力 + Leaflet.js アニメーション

| 項目 | 内容 |
|---|---|
| SUMO出力形式 | FCD（Floating Car Data）XML — 各タイムステップの車両位置を記録 |
| 変換 | Python で FCD XML → JS変数ファイルに変換 |
| フロントエンド | Leaflet.js + カスタムアニメーションループ |
| 対象 | small シナリオ（40台）と10pctシナリオ（120台）。full はファイルサイズ増大のため後続検討 |
| 道路ネットワーク表示 | OSM タイル（背景）+ 道路閉鎖edgeをポリラインで重ね描き |

---

## 2. データフロー

```
p2_traci_closure.py（TraCIで実行）
  └─ --fcd-output → scenario_a_small_fcd.xml / scenario_a_10pct_fcd.xml
        │
        ▼
p2_fcd_to_json.py（新規）
  ├─ fcd.xml → vehicles_small.js / vehicles_10pct.js（車両位置時系列）
  └─ closure_timeline_sumo.json → closures.js（閉鎖エッジ時系列）
        │
        ▼
sumo_viz.html（新規）
  ├─ Leaflet.js（地図タイル）
  ├─ vehicles_small.js / vehicles_10pct.js → 車両アイコンをアニメーション
  ├─ closures.js → 閉鎖道路をポリラインで強調表示
  └─ timeline スライダー → 任意時刻へのシーク
```

---

## 3. FCD出力の設定

### 3-1. sumocfg への追記

`p2_sumo_scenario.py` の `generate_scenario()` で生成する sumocfg に FCD 出力ブロックを追加する。

```xml
<output>
  <tripinfo-output value="../results/scenario_a_small_tripinfo.xml"/>
  <fcd-output value="../results/scenario_a_small_fcd.xml"/>
  <device.fcd.period value="30"/>
  <fcd-output.geo value="true"/>
</output>
```

| オプション | 値 | 説明 |
|---|---|---|
| `fcd-output` | ファイルパス | FCD XMLの出力先 |
| `device.fcd.period` | `30` | 30秒ごとにサンプリング（small: ~720ステップ） |
| `fcd-output.geo` | `true` | 座標を lon/lat（WGS84）で出力 |

注：SUMO 1.26.0では `fcd-output.period` ではなく `device.fcd.period` を使う。初回実行で `fcd-output.period` が未対応オプションとして失敗したため、実行結果に合わせて修正した。

### 3-2. ファイルサイズ見積もり

| シナリオ | 台数 | ステップ数(÷30) | レコード概算 | JSON概算 |
|---|---:|---:|---:|---|
| small | 40 | 720 | 28,800 | ~2 MB |
| 10pct | 120 | 720 | 86,400 | ~6 MB |
| full | 1,001 | 720 | 720,720 | ~50 MB |

実装対象は small と10pctまでとする。full は別途圧縮・タイル化を検討する。

---

## 4. `p2_fcd_to_json.py`（新規スクリプト）仕様

### 4-1. 入力

| ファイル | 内容 |
|---|---|
| `output/sumo/results/scenario_a_small_fcd.xml` | small SUMO FCD出力 |
| `output/sumo/results/scenario_a_10pct_fcd.xml` | 10pct SUMO FCD出力 |
| `output/sumo/derived/closure_timeline_sumo.json` | SUMO秒基準の閉鎖タイムライン |
| `output/sumo/derived/edge_id_mapping.csv` | SUMO edge ID → Phase 1 edge ID |

### 4-2. 出力

| ファイル | 保存先 | 内容 |
|---|---|---|
| `vehicles_small.js` | `output/sumo/viz/` | small車両位置時系列（`window.VIZ_VEHICLES_SMALL`） |
| `vehicles_10pct.js` | `output/sumo/viz/` | 10pct車両位置時系列（`window.VIZ_VEHICLES_10PCT`） |
| `closures.js` | `output/sumo/viz/` | 閉鎖エッジの座標・時系列（`window.VIZ_CLOSURES`） |
| `viz_meta.js` | `output/sumo/viz/` | シナリオ名・時刻範囲・統計サマリ（`window.VIZ_META`） |

### 4-3. `vehicles_small.js` / `vehicles_10pct.js` 構造

```json
{
  "scenario": "small",
  "period_sec": 30,
  "sim_duration_sec": 21600,
  "vehicle_count": 40,
  "vehicles": {
    "veh_small_origin_0001_0001": {
      "frames": [[0, 139.9871, 36.0521, 12.3], [30, 139.9880, 36.0530, 8.1]],
      "status": "arrived"
    }
  }
}
```

各フレームは `[sim_time_sec, lon, lat, speed_mps]` の配列。車両が存在しないタイムステップはスキップ。

### 4-4. `closures.js` 構造

```json
{
  "events": [
    {
      "sim_time_sec": 789,
      "time_id": "t0",
      "new_edge_ids": ["12345"]
    }
  ]
}
```

エッジ座標は `joso.net.xml` の shape 属性から取得し、`edge_coords` にまとめる。

---

## 5. `sumo_viz.html`（新規）構成

### 5-1. ライブラリ

| ライブラリ | 役割 | 導入方法 |
|---|---|---|
| Leaflet.js 1.9.x | 地図・ポリライン描画 | CDN |
| なし（バニラJS） | アニメーションループ | — |

外部依存は Leaflet.js のみとし、フレームワーク不使用でシンプルに保つ。

### 5-2. UI要素

```
┌────────────────────────────────────────────┐
│  [凡例] 走行中 ○  到着 ●  逃げ遅れ ✕  閉鎖道路 ━  │
├────────────────────────────────────────────┤
│                                            │
│        Leaflet 地図（OSM タイル）            │
│   車両アイコン + 道路閉鎖ポリライン             │
│                                            │
├────────────────────────────────────────────┤
│  ◀◀  ▶  ▶▶   [████████░░░░░░░░]   00:13:09  │
│  シナリオ: [small/10pct]  速度: [×1] [×5] [×10] │
│  台数: 走行中 28 / 到着 8 / 逃げ遅れ 4        │
└────────────────────────────────────────────┘
```

### 5-3. アニメーションロジック

```javascript
// 30秒ごとのフレームを requestAnimationFrame で補間
// 速度倍率（×1/×5/×10）はフレームスキップで実現
// 閉鎖イベント時刻に達したら closure ポリラインを追加
```

---

## 6. ネットワーク座標の取得

道路閉鎖ポリラインの描画には SUMO edge の座標が必要。

| 方法 | 説明 |
|---|---|
| `p2_fcd_to_json.py` 内で `sumolib.net.readNet()` → `edge.getShape()` | 最もシンプル。`fcd-output.geo=true` と組み合わせると座標系が合う |
| `polyconvert` コマンドで net.xml → GeoJSON | 別ツール呼び出しが必要だが汎用的 |

採用：`sumolib.net.readNet()` で `getShape(includeJunctions=True)` → lon/lat 変換を `p2_fcd_to_json.py` 内で行う。

---

## 7. 実装タスク一覧（P2-IMPL-VIZ）

| ID | タスク | 依存 | 成果物 |
|---|---|---|---|
| P2-IMPL-VIZ-1 | sumocfg に FCD 出力設定を追加する | P2-IMPL-5 | sumocfg 更新 |
| P2-IMPL-VIZ-2 | small シナリオを FCD 出力付きで再実行する | VIZ-1 | `scenario_a_small_fcd.xml` |
| P2-IMPL-VIZ-3 | `p2_fcd_to_json.py` を作成する | VIZ-2 | `vehicles_small.js`, `closures.js`, `viz_meta.js` |
| P2-IMPL-VIZ-4 | `sumo_viz.html` を作成する（地図 + 車両アニメーション） | VIZ-3 | `output/sumo/viz/sumo_viz.html` |
| P2-IMPL-VIZ-5 | タイムラインスライダー・速度倍率・台数表示を実装する | VIZ-4 | 同上（機能追加） |
| P2-IMPL-VIZ-6 | 道路閉鎖ポリラインのアニメーションを実装する | VIZ-5, VIZ-3 | 同上（機能追加） |
| P2-IMPL-VIZ-7 | `gen_index.py` に Phase 2 可視化リンクを追加する | VIZ-4 | `output/index.html` 更新 |
| P2-IMPL-VIZ-8 | 10pct シナリオへ拡張する（ファイルサイズ確認） | VIZ-4 | `vehicles_10pct.js` |

---

## 8. 停止条件

| 条件 | 理由 |
|---|---|
| `fcd-output.geo=true` で lon/lat が返らない | Leaflet の座標系と合わない。`sumolib` の変換関数でフォールバック |
| `vehicles_*.js` が 10 MB を超える | ブラウザ読み込みが重くなる。period を 60 秒に変更するか、delta 形式（差分のみ）に変更 |
| TraCI 実行中に FCD 出力が抑制される | TraCI 起動時の `traci.start()` オプションに FCD 設定を追加する必要がある |

---

## 9. TraCI実行時のFCD出力について

`p2_traci_closure.py` では `traci.start()` で SUMO を起動するため、`sumocfg` に FCD 設定を書いておけばFCDが出力される。
TraCI起動時にも `--fcd-output.geo true` と `--device.fcd.period` を渡し、FCDの座標系と周期を明示する。

確認方法：

```python
# TraCI実行後にFCDファイルが存在するか確認
assert fcd_path.exists(), f"FCD output not found: {fcd_path}"
```
