# 短道路の通過区間修正：組込前の契約

2026-10-24。候補のみ。研究入力・閉鎖呼出し・物理制御・現共通5は未変更。現在の専用検証session13369が終端となるまで、凍結ソースやconfigを変更しない。

## 守るもの

- 対象地域、人物、要求、目的地D0/D1、全条件とseed、主指標/副指標/分母/除外規則を維持する。
- 予定閉鎖T、呼出しmax(0,T−0.5)、観測phase、移動step0.5秒を維持する。閉鎖時刻や猶予を動かして判定を通さない。
- 車両経路、交通制御、歩行予算、配車・取消・乗降の判断を変えない。観測済みのnative情報だけから遷移の時間区間を記録する。
- 真に閉鎖後/ちょうどTの観測上限で入る場合は引き続き拒否する。誤判定の1行を例外扱い・除外する修正にしない。
- 元run・元CSV・元validation・旧8採用と登録を保全する。全70採用で共通5を統一するゲートを維持し、旧新の混在を許可しない。

## 必要な技術変更の境界

生成側では、下流internal laneに到達した時点で、そのsourceとなる通常道路を通過済みと証明できる。source/targetのconnection、経路内の出現位置、route_versionとnative route_indexを照合して区間を進める。現在と同じCSV列を保ち、from_edgeは直前の通常道路の出現、下限は次の通常道路へまだ入っていないことが分かる最後の観測時刻として明記する。連続時刻の真値は逆算しない。

検証側は、生成関数を呼んで追認せず、元net・route/event・全actor frame・遷移multisetから別に再構成する。同じexternal-onlyの誤りが両側へ残る変異を反例で拒否する。候補observer_candidate.pyをそのまま両側から共有しない。

車両側の観測anchorは物理状態から分離する。歩行の現在位置、pedestrian_closure_actionのfallback、速度積分・距離会計へ影響を与えない。新しいTraCI制御/移動呼出しは追加しない。

初期private_departure_requested、DRT初期配置、private_reroute/drt_route/cancel_wait_route、native arrival、parked/reentry/departure_pendingを確認する。初期観測より前に短道路を飛び越す場合、生成イベントに基づく明示anchorが必要であり、最初の観測位置を無言で始点へ置換しない。経路版の変化を推測でリセットしない。

## 組込前後の証拠

1. 元凍結コードを抽出したREDは保存済み。候補の13人工契約と対象1個体の読取replayは合格したが、研究採用・READYではない。
2. 真の後進入/境界T/閉鎖前、通常道路が1step内に消える場合と複数internal、複数短道路、経路反復、初期挿入・到着・再経路・待機/再出庫・欠損を実SUMOのfixtureと独立改変検査で覆う。
3. 生成と検証が誤った時刻を共有する場合も、独立した接続/物理frame条件により検出する。
4. 版が変わる前のbaselineはrepair_baseline.jsonと内容SHAの原本へ保全した。原専用検証の終端結果と他の失敗成分も診断してから修正範囲を確定する。
5. 共通実装の修正後は現行入力・unit・実SUMO suite・全反例・全14設定smoke・新READYをそろえる。別workspace/技術登録と台帳を準備し、共通版の全登録セルを新IDで実行する。旧8採用を新比較へ混ぜない。

この境界内の修正は観測・独立監査の技術的訂正として扱う。主指標、比較、閉鎖時計、物理制御、除外規則や版混在許容を変える必要が生じた場合は、別途根拠・代替案・影響を提示してユーザーの明示判断を得る。現在それらを変更する案は採用していない。

## 原専用検証の終端とWarning依存の切分け（2026-10-24）

session13369は17:59:39ごろexit1/INVALIDで終端。人物・候補・道路・actor観測・native fixture境界はPASS、movementはno_closed_or_ambiguous_entries1のみINVALIDだった。native_logsの徒歩Warning6行は3key各2件のstage replacement receiptと一致し、採用native版のgetter契約も実照合でsupportedだった。ただしaudit_native_logsはmovement全体がPASSの場合だけexpected_walkを作るので、元movementの未合格から二次的にWarningが未分類となる。これは独立した別のWarning許容不足とは判断しない。

元検証をPASSへ書換えたり、gateを緩めてnativeログだけを採用へ流用したりしていない。最小修正の対象は遷移生成と独立再構成であり、Warning分類器の条件は維持する。terminal_rejection_readback.jsonとwarning_dependency_diagnosis.jsonを参照。

旧CLI/旧READYの表示だけで再開しない。既知の反例を受け、既存checkpointのcurrent_hold/technical_ready=falseを設定し、旧READY原本はhistoricalとして保全した。新たな版整合と全開始前証跡がそろうまで後続開始は禁止する。

## 組込・新登録と到着尾距離の追加診断（2026-10-24）

新登録v3をID/workspace/addendum/record_filesのみの変更で有効化し、研究sections・全70一覧の同一を確認した。新入力11965人の独立28項目PASS。観測生成は前向き、独立再構成は逆向きの接続証明を使う。初期/到着の明示indexを含め、native制御呼出しはAST同一である。

新しい1m人工道路は1step内に消えず、nt261024aは試験条件未再現でFAILED保全した。人工条件を.1mへ限定して新bで短道路/下流internal/閉鎖の境界を収集した。研究入力は変更していない。cの最終短道路では生成・movement境界はPASSだったが、actor距離が「最終frameは終点external上」とする前提で独立INVALIDになった。元報告を保存し、到着尾距離を元lane/接続・route occurrence・arrivalLane/arrivalPosから一意に再構成した。routeLengthを使って尾距離を逆算せず、既存の丸め誤差幅で残差を照合する。未知/循環/長さが異なる複数経路は拒否する。

元c29のactor成分再計算と5改変拒否、関連61unitを確認したが、旧c29を現行全体合格へ書き換えない。共通5を固定し新dの全29 nativeを開始。全反例/全14smoke/新preflight/G6/容量は引き続き必要である。native_tail_primary_diagnosis/recalculation/mutations、full_suite_scope_reviewを参照。
