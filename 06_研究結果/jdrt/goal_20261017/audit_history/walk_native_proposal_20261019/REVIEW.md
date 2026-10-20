# 徒歩stage置換時のraw横位置保持：未適用native修正案

状態は **PROPOSAL_ONLY_NOT_APPLIED_NOT_BUILT_NOT_RUN**。このディレクトリの`proposed/`はレビュー用コピーであり、実行器やglobal SUMOへ適用していない。コンパイルやnative実証もしていない。研究正式0/70、READY=false。

対象は公式`v1_26_0`の`src/microsim/transportables/MSPModel_Striping.cpp`だけ。差分は`preserve_aborted_walk_raw_lateral.patch`、原本コピーは`before/`、変更案は`proposed/`。`proposal_manifest.json`に各SHAと静的確認結果を保存した。原本SHA一致、パッチの`git apply --no-index --check`はPASS。これはビルド・挙動のPASSではない。

## 旧stateの寿命を追った証拠

引用行は保存した公式raw sourceの物理行番号。全文と各版SHAは兄弟`walk_source_review_20261019/sources.json`、根拠行抜粋は`lifetime_source_trace.json`にある。

1. `Person.cpp:751`の`replaceStage`は新stageを現在stageの直後へ挿入し、`removeStage(0)`を同期呼出しする。旧stageそのものはここで削除されない。[公式ソース](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/libsumo/Person.cpp#L751)
2. `MSTransportable.cpp:331`の`removeStage`は未来stage (`next>0`) にだけdelete/plan eraseを行う。現在stage (`next==0`) は`abort`→`proceed`へ進み、旧stageをplanに残す。[公式ソース](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSTransportable.cpp#L331)
3. `MSStageWalking.cpp:153`のabortはmovement modelのremoveだけを呼ぶ。stripingが継承する`MSPModel_Interacting.cpp:57`のremoveは、active-lane配列からpointerを外し人数を減らす処理で、PStateのdelete、lane/縦位置/raw横位置の初期化はない。[abort](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSStageWalking.cpp#L153)、[remove](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSPModel_Interacting.cpp#L57)
4. `MSTransportable.cpp:102`のproceedは旧stage pointerを`prior`として保持する。`setArrived`は到着時刻だけを設定し (`MSStage.cpp:160`)、edge側のremoveは所属pointerを集合から外すだけ (`MSEdge.cpp:1233`)。`myStep++`後、priorを新stageのproceedへ渡す。[proceed](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSTransportable.cpp#L102)、[setArrived](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSStage.cpp#L160)、[edge所属解除](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/MSEdge.cpp#L1233)
5. `MSStageWalking.cpp:114`は新stageの出発時刻と縦位置を設定してから、`MSPModel_Striping.cpp:161`のaddを呼ぶ。addは同期的に新PStateを生成する。constructor中の`getNextStage(-1)`は旧stageを指す。`MSTransportable.h:253`はplan内pointerを返すだけで、総stage数から残stage数を引いた値が正のときだけ参照すれば範囲内である。[walking proceed](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSStageWalking.cpp#L114)、[add](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSPModel_Striping.cpp#L161)、[stage参照](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSTransportable.h#L253)
6. `MSStageMoving.cpp:38`のdestructorがPStateをdeleteするが、上記の現在stage置換から新constructorまでにそのdestructorは呼ばれない。旧PStateへのpointerを新stateのメンバへ保存せず、constructor内でraw数値をコピーするだけにする。[destructor](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSStageMoving.cpp#L38)

この同期経路について、旧stateのuse-after-freeや値消失を示す処理はない。これは固定ソースの静的寿命確認であり、未定義動作がないことやnative動作を実行で証明したとの主張ではない。

## 通常のstage境界との区別

自然な歩行終了ではstripingの`moveToNextLane`が旧PStateのlaneを先にnullへ変更する (`MSPModel_Striping.cpp:1808`)。movement処理はその状態を見てstage終端へ進む (`1037`)。提案の`oldState->getLane() == lane`は必ず不成立となるため、同じedgeで次のwalk stageが始まる自然境界にも旧横位置を強制しない。[自然な終端](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSPModel_Striping.cpp#L1808)

初回departはprevious stageがwaiting等でありwalking条件に不一致。明示値・random横開始位置は`UNSPECIFIED_POS_LAT`条件に不一致。legacy開始位置オプション有効時も提案を通らない。internal/walkingarea、別lane・別edge・異なる縦位置も対象外とする。既存のdesired departure positionや通常のstage境界は既存branchへ戻す。

## 変更内容と範囲

PState constructorの既存方向判定の後、横stripe初期化の直前だけにguardを加える。横位置未指定・非legacy・normal外部edge・直前walking・同person/lane/edge・縦位置exact一致・旧到着時刻と新出発時刻の一致を確認し、`getPosLat()`のraw数値を新`myPosLat`へコピーする。他のケースは元の横位置初期化へ進む。

コピー対象はlane中心offsetではない。`MSPModel_Striping.h:351`のraw stripe値であり、符号変換や往復計算をしない。新routeからの方向判定は既存コードのまま、next-lane計算もコピー後に既存コードで行う。逆行であっても横位置を反転しない。新stateが持つ速度・待機・相互作用ロジック、stage長・予算会計、TraCI送信形式を追加変更しない。[raw getterと変換](https://github.com/eclipse-sumo/sumo/blob/v1_26_0/src/microsim/transportables/MSPModel_Striping.h#L347)

## 公式版との比較と未解決事項

公式`v1_26_0`、`v1_28_0`、main commit `6cc2da1964718a94d44eb3fc9ff56c5d2c43982c`の対象walking proceed部分は同一SHA `fa13cf5175e00d768d19a01e5c795c07f043885da84215ac2cf44cd89b81141a`。1.28.0やmainへ更新するだけで直る根拠はない。各sourceファイルのSHAはsource inventoryが正本。

この案はStage.departPosをnativeが利用しない警告を解消しない。今回確定した失敗は横stripe再初期化であり、関係しない変更は加えない。nativeのexact XY、再進行の向きと速度、複数人相互作用、予算recurrenceは、別紙`NATIVE_REGRESSION.md`の実証前には未解決である。

適用する場合もworkspace専用binaryへ固定し、共有resolver・旧global SUMO・完了済み系列を変更しない。全70セルは最終toolchainを共通にする。compiler・DLL・build flags・source/patch/binary SHAの固定と、全26suite→独立audit→全14smoke→新preflightが必要である。
