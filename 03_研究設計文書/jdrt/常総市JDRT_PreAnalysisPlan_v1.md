# 常総市JDRT Pre-Analysis Plan v1

> 固定日：2026-08-11  
> 対象：常総市（08211）  
> 状態：正式固定・実験未実施  
> 判断記録：`開発メモ/方針判断_codex/01_JDRT/常総市JDRT_研究条件正式判断_codex.md`

## 1. Primary Research Question

> 待ち時間と支援必要度を使う動的配車に、将来の道路閉鎖時刻予測を加えることで、Type4住民の避難成功率はどのように変わるか。

## 2. Primary Comparison

`JDRT-B3 Waiting + Vulnerability`対`JDRT-P2-L15 Flood-risk-aware Late 15 min`。

両条件で人口、request、private car、DRT fleet、True closure、避難所、seedを同一にし、P2-L15だけが予測閉鎖情報とFeasibility Gateを利用する。

## 3. Supporting Comparisons

- `JDRT-B2 Dynamic Travel-Time`：現在の旅行時間だけを使う強Baseline
- `JDRT-P1 Perfect Forecast`：予測誤差0秒の理論上限
- `JDRT-B1 Nearest`：smokeと説明用。主たる優位性主張には使わない

## 4. Population and Demand

- 人口正本：405 origin、21,539人
- Type3：2,320人
- Type4：935人
- DRT eligible/requesting：Type3/4全3,255人
- private car：既存8,164台を全JDRT条件で維持
- rescue car：JDRT条件では既存1,405台を生成しない
- DRT利用率100%は上限需要ケースであり、実利用率の推定ではない
- 全requestは0秒に発生する。一斉避難は比較用仮定であり実行動再現ではない

### Request生成

同一originのType3/4を、既存`rescue_vehicle_count`を基準に定員内へ分割する。

```text
group_count = min(
  type34_people,
  max(1, rescue_vehicle_count, ceil(type34_people / 8))
)
```

人物を各groupの人数差が1人以内になるよう決定的に配分する。Type4、Type3 mobility-limited、その他Type3もgroup間の差が最小となるよう順に配分する。結果は1,440 requests、party size 1〜8人、人物合計3,255人とする。

## 5. Fleet and Operation

- fleet：5台
- standard：4台、capacity 8
- welfare：1台、capacity 4
- 初期edge：`bus_plan.csv`の5台のpickup edge
- boarding：300秒/request
- alighting：300秒/request
- dispatch interval：60秒
- travel-time refresh：60秒
- assignment lock：ASSIGNED後の再割当なし
- pooling：なし。1 pickupから固定避難所へ直行後、次requestを選ぶ
- simulation end：21,600秒

## 6. Shelter Rule

`shelters_sumo.csv`の安全判定済み9施設だけを使用する。各originは`rescue_od.csv`で既に対応付けられた避難所へ向かう。避難所選択最適化は行わない。

capacity=0は収容人数0ではなく既存データ上の不明値と解釈し、主分析では容量制約を使用しない。全施設のactive期間は0〜21,600秒とする。

## 7. True and Perceived Closure

- True World：`closure_timeline_sumo.json`をSUMOへ適用
- B2/B3：予測閉鎖情報を受け取らない
- P1：predicted closure = true closure
- P2-L15：predicted closure = true closure + 900秒
- 予測時刻が0秒未満になる感度条件では0秒に下限処理する
- True closureをDispatcher公開APIへ渡さない

Feasibility Gateは次の厳密不等式を使用する。

```text
pickup travel
+ boarding
+ shelter travel
+ safety margin 300 sec
< earliest predicted closure margin on route
```

alightingは安全な避難所edge到着後のため、道路閉鎖前到着判定の所要時間には含めず、避難完了時刻には含める。

## 8. Dispatch Score

候補集合内でwaiting、pickup、flood urgencyを0〜1へ正規化する。

- B3：waiting 1.0、vulnerability 1.0、pickup 1.0
- P1/P2：waiting 1.0、flood 1.0、vulnerability 1.0、pickup 1.0
- vulnerability：Type4=1.0、Type3 mobility-limited=0.5、その他Type3=0.0
- request vulnerability：構成人物の平均
- 同点：request_id、vehicle_idの順

## 9. Primary Outcome

Type4 evacuation success rate。

```text
21,600秒までに安全な避難所で降車完了したType4人数 / 935人
```

## 10. Secondary Outcomes

- Type3/4全体避難成功率
- Type3避難成功率
- Type4到着人数、追加到着人数
- stranded人数と理由
- 避難完了時間P95（成功者）
- request待ち時間
- pickup成功率
- 空車VKT、総VKT、1台あたり輸送人数
- network速度、halting数、teleport、閉鎖後進入
- Feasibility Gate rejection数と理由

## 11. Seeds and Runs

paired seeds：`23423, 42, 1, 7, 101`。

中核はB2、B3、P1、P2-L15の4方式×5seed＝20runとする。各seedで同一request、private car、True closureを使用する。

## 12. Analysis

- seed別値、中央値、最小、最大を保存
- Primary Comparisonは同一seedの`P2-L15 − B3`を算出
- 効果方向、効果量、5seed間の符号、Type4と全体の差、追加交通負荷を併記
- 5seedのため、単一のp値で成功・失敗を判定しない
- 差なし、符号混在、逆効果も結果として採用

## 13. Inclusion and Exclusion

採用には正常終了、manifest、入力SHA一致、設定一致、人物・request・車両会計、capacity、最終状態保存、True/Predicted分離、SUMO Errorなし、teleportなしを要求する。

> **2026-08-11 技術的明確化：** 「SUMO Errorなし」は、処理されないSUMO Errorが0件であることを指す。TraCIが個別バスのroute変更を拒否し、controllerがその例外を捕捉して当該バスとrequestを理由付き終端状態へ移した場合は、`handled_route_rejection_count`として総Error数とは別に保持する。捕捉済み件数を削除・非表示にはせず、`unhandled_error_count=0`、人物保存則、teleport 0を同時に要求する。この明確化は配車方式、評価指標、seed、需要、fleet、結果値を変更しない。

低完了、高完了、gridlock、seed 42、仮説と反対の結果は除外理由にしない。invalid runは削除せず理由とともに保存する。同一セルに複数のvalid runがある場合は自動選択せず停止する。

## 14. Staged Robustness

中核20runの技術成立後、必要な軸だけを一因子ずつ追加する。

1. Temporal Forecast Error：Early/Late 30分、Early/Late 60分
2. fleet：3台、10台
3. safety margin：180秒、600秒

15分Late以外は副次的Robustnessとする。全因子直積、Spatial Forecast Error、Pooling、DEGRADED道路、基地最適化は中核研究へ含めない。

## 15. Claim Limits

- P1を現実の政策効果として扱わない。
- P2の結果は道路閉鎖時刻予測誤差についてだけ述べる。
- 利用率100%、一斉避難、避難所容量無制約を実態値として扱わない。
- 常総市で実際に同人数を救えるとは主張しない。
- 他地域へ効果量を直接一般化しない。
- 既存Phase 3 A/Bのヌル結論を変更しない。
