# 受付・代替行動：残経路APIの技術再登録 v4

登録日：2026-10-28。protocol=realtime_choice_v1、registration_id=choice_route_control_v4_20261028。技術準備中、READY=false。本実験は未開始。

旧v3の正式9件とFAILED nv26102810、旧READY、一次CSV・manifest・検証・記録を保全し、新主比較へ混ぜない。原本はroute_replacement_failure_20261028/preservation.jsonとproduction_repair_20261028/baseline.jsonでSHAを追跡する。旧登録の短道路・到着観測訂正はnative観測監査_技術再登録_v3.mdの契約を全て継承する。

## 修正する技術的動作

SUMOのsetRouteは走行済み区間を前置して経路全体の現在の通行権限を再検査する。施設優先の乗車後配送で、要求した残経路にはない走行済み道路が閉鎖されたためnv26102810が停止した。同じ凍結native binaryで独立再現し、sourceと要求残経路・既走行indexを原本から確認した。

DRTのset_vehicle_routeは現在の外部道路から始まる残経路を一意route IDとして登録し、setRouteIDで設定する。stopの解除・再設定と駐車位置/乗降時間/経路選択・費用計算は維持する。停止済み取消は現在位置で待機し不要なresumeをしない。native binary/patchは変更しない。

制御中のgetterがnative再出庫待ちのINVALID値を返す場合、元の値を保持してpendingとして記録し、既存の次step観測で位置・累積距離・source/index/versionを検証する。位置補完、隠れsimulationStep、future閉鎖の無視、経路エラーの握り潰しを行わない。未来区間の閉鎖はnativeでも引き続き拒否する。

## 維持する研究条件

全70セルと登録順・seed23423,42,1,7,101、D0/D1、人物・需要意思/受付・供給・施設/退出・初期/目的地位置・全入力を維持する。予定閉鎖T・呼出しmax(0,T−0.5)・観測上限T/phase、0.5秒step、配車・取消・300秒乗降、主要/副指標・分母・比較式・除外規則は既存PAP/Registryと同一。APIの実装訂正であり科学的な条件変更ではない。設定の科学部分を旧原本と完全比較し、新入力の物理/人物/共通実現/施設/危険表もSHA照合する。

新workspaceはjdrt_realtime_choice_routeaudit_v4、新実験記録とJSONL台帳は経路監査v4専用とする。旧採用の移記・旧runの再利用/上書き/削除は禁止。

## 未完の開始条件

個別API試験の合格と117unitは全体READYではない。乗車・配送・過去閉鎖を含む全controller回帰、現行全実SUMO fixture、独立全成分監査と改変反例、全14設定smoke、入力/unit/依存SHA、新preflight READY、G6現行登録照合、容量と07監視対象をそろえる。全70で同一common5を維持し、独立PASS→専用record7→一意台帳/status後のみ次1セルを開始する。施設受入と退出は別計上、全70前の方式方向解釈は禁止。外部送信/公開なし。
