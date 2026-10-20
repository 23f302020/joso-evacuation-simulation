# Native回帰手順（未実行）

全項目は予定であり、実行やPASSを示さない。今回の作業ではソースコピーと未適用差分の整合だけを確認した。新binaryのビルド・pin・fixture起動は別Gateの承認後に限る。

## 事前条件

- 固定baseは公式v1_26_0。元ソースSHA、提案patch SHA、compiler/flags、依存DLL、binary SHA/versionを記録する。old global SUMOはそのまま保存する。
- 同じソースから作った未patch対照binaryとpatch binaryをworkspace内で分離し、共通の依存・build設定を固定する。対照buildが既存installerと異なる可能性を明記する。
- choice用binary pinを明示し、実際の起動先とSHAをmanifestに記録する。PATHや共有resolverを暗黙変更しない。新technical IDを各実行に使い、旧runは上書きしない。
- 全SUMO/Pythonの停止を確認する。実行中にscripts/input/native sourceを編集しない。測定値はrawから求め、期待した移動量や成功値をコードへ固定しない。

## 最小native試験

| 試験 | 具体的操作 | 合格を確認する一次証拠 |
|---|---|---|
| 既存の失敗を再現 | 未patch対照で専用CLIのselected `walk_short_repeated`（校正→反復）を新IDで実行 | 原版同様にold_remainingで位置差を保存。差の大きさを0.64mへ固定せず、before/after rawを保存する |
| 現在失敗するcaseの修復 | patch binaryで同じ校正→反復を別新IDで実行 | Type3/4の全old_remaining/new_route receiptでroad/縦位置/XYがexact一致、両者の2回rerouteとterminal到達、native errors/teleports/collisions 0 |
| 同方向の残距離再plan | 実SUMOの進行中外部edgeで同じ残routeへreplaceStage（rawlatが初期stripeから異なるnative frameを原CSVから選ぶ） | 置換前後road/位置/XYexact、旧stageとの同一person/lane条件。次stepの縦位置増分の符号が元方向と同じ |
| forwardからreverse／reverseからforward | 既存forward/reverse人工網を利用し、実native位置に対して反対端へ通る合法経路へ置換 | 置換時XYexact、次stepの縦位置差の符号が新routeの出発端に整合。旧方向をコピーしていない。閉鎖辺進入0 |
| 連続2回置換 | 1制御時刻でold_remaining→new_routeを現在runtimeの順に行う | 2呼出しそれぞれのexact before/after、新stage長の有限・非負、独立予算recurrence |
| 複数人の相互作用 | 同一lane上で横stripeが異なるType3/4を歩かせ、順序を入れ替えて各personをreplanする | 各person自身のrawlatだけ保持。操作対象外personの位置は同時刻で不変。各次stepの速度上限、会計、衝突・teleportゼロ |
| 新規departの対照 | previousなし、waiting→walking、明示横位置、random横位置、legacyオプションの各合法入力を対照binaryと同じseed/入力で実行 | 提案guardを通らず、native初期位置・横stripeが対照と一致する。random入力の乱数消費を増やさない |
| 自然なwalk-stage境界 | 到達によるwalk→walk（同edgeと別edge）、walk→wait→walk、初回walkingを対照と比較 | 自然終了時のold lane=nullをnativeデバッグで確認。次stageの既存desired横位置と位置系列が対照と一致する |
| 非対象native lane | 別lane、internal/walkingarea、明示lat、legacy、縦位置不一致のケース | patchの継承guardに入らない。既存の成功/拒否を維持する。runtimeの位置拒否条件は変えない |

## 独立検算

失敗caseで新branchが実際に選ばれたことを、native debuggerまたは別SHAを記録した診断buildで確認する。constructor入力の`myPosLat == UNSPECIFIED_POS_LAT`、`myLegacyPosLat == false`、旧person/lane/edge/縦位置・時刻の各guard、コピー前後のraw横位置を保存する。Python側の成功receiptだけでguard成立を推定しない。最終binaryと診断binaryは区別する。

各replacement receiptのroad・lane_position・XYは元値どうしのexact比較で判定する。位置移動を許容するtolerance、`moveTo`/`moveToXY`補正、fixtureの干渉除去だけでの成功化は行わない。歩行速度はnative actor CSVと登録boundを突合し、縦位置は該当native lane長の範囲内であることを確認する。方向は次stepの座標差と新routeの出発側endpointから判断する。合法的に一時停止した場合はrawを残し、既存fixture受入を勝手に緩和しない。

stage budgetは`previous_plan_m - old_remaining_m`からの再帰、model_passedとnative speed積分、new native stage長をそれぞれ再計算し、既存検証器と一致することを確認する。論文値や観測された期待長をハードコードしない。native stateのcopyはlatのみのため、距離・速度の未解決失敗があれば次工程へ進まない。

## 全体の完了条件

最小native試験に合格した場合だけsource/binaryをfreezeする。全26ケースを新IDで通し、独立counterexample audit、全14設定smoke、unit/input検査、新preflightの順に進む。変更されたruntime SHAでG6 source proofも再監査する。70正式セルはすべて同じ最終toolchainを用いる。技術PASSのみでcoreを開始したり、旧invalid runを再採用したりしない。
