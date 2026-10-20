# USACE Joso Validation Dataset：取得・入力化監査

作成：2026-10-15 JST。**原本取得時の監査記録。2026-10-16にBをユーザー採用し、別系列の道路入力を構築・独立検証PASS。最新の準備/進行は[実時間B監査](../../../05_タスク管理/jdrt/JDRT-実時間B_開始準備監査.md)。** これ以前の「公開数値時系列未取得」は過去の監査時点の記録として保持する。

## 出典・取得経路

[USACE Risk Management Center公式ページ](https://www.rmc.usace.army.mil/Software/LifeSim/Joso-Validation-Dataset/)の配布ボタンが示す公開OneDrive ZIPを、ログインなしのブラウザのダウンロードボタンから取得。ローカル保存は`raw/LifeSim_Validation_Joso.zip`、ZIPのSHA/サイズ/日時/URLは同名metadata JSON。69,764,360 bytes、26エントリ、展開ファイル21。公式サイトの説明とZIP同梱文書から、2015年洪水の水理再現に使われた校正計算と位置づける。観測水深そのものではない。

直接curlは公式入口と短縮URLの双方でHTTP403。Firecrawlの公開ページ読取で配布先を確認し、通常ブラウザでは匿名ダウンロードに成功。認証迂回・問い合わせ・メッセージ・共有設定変更・アップロードなし。公開ページの一時的なアプリ内部状態は保存せず、構造化された出典本文/リンク/取得metadataと当該HTMLのSHAを保存。第三者文書にある送信指示等は実行していない。

公式ページの[利用条件リンク](https://www.iwr.usace.army.mil/Library/IWR-Software-Terms-and-Conditions/)は`raw/usace_terms_firecrawl.json`へ保存する。公開ダウンロードできることだけで、無制限再配布や国内研究上の精度保証を意味するとしない。本作業ではローカル調査に使用し、再配布しない。

## 原本に含まれるもの・本研究へ持ち込まないもの

| 内容 | 一次確認・位置づけ |
|---|---|
| Calibrated.hdf | HEC-RAS 5.0.3の計算結果、水位時系列、格子、境界条件、収支。洪水の候補入力 |
| Terrain.kinugawa.tif | EPSG:32654、約5.912m画素の地形。道路水深算定候補。道路/橋の路面標高と同義ではない |
| Max_Depth TIFF | 最大値の検査用候補。時間別閉鎖は最大深から作らない |
| LifeSim .fia/.xml、同梱docx | 元研究の説明とモデル資料。**人口・住民属性・避難率・死亡確率・避難先は本研究へ移植しない** |

原本を`derived/usace_original/`へ安全なパス確認後に展開した。ZIPは不変保管。内容一覧は`derived/USACE_ZIP_inventory.json`、HDFのパス/属性/shape一覧は`derived/USACE_HDF_inventory.json`。元研究の過去のローカル絶対パス属性は来歴であり、本研究の有効な入力先としない。

## 時間・空間・変数の監査

- Base Outputは2015-09-09 00:00〜2015-09-12 00:00の865点、native出力間隔300秒。Time配列の単位Daysを86,400倍した秒と日時文字列を全点一致確認。DSSの10分系列と混同しない。
- 計算内部刻み5SECと出力5MINを分離。15分に対する時間刻みの充足候補ではあるが、実際の洪水到達時刻の誤差が5分以内という証拠ではない。
- HDF水位はMeters、ルートSI Units、投影はWGS84/UTM54N。地形のCRSも一致。一方GeometryのSIフラグはFalseという矛盾を保全し、単に無視せず座標/地形/原文の追加照合対象とする。
- 水位行列は865×8,174、非有限値0。面積のあるセル7,697、面積0・頂点2の境界列477。477列を面へ凸包化せず、元行列には保持し、面GeoJSONからは理由付きで分離した。初回抽出はこの境界列で停止し、0面積を確認して修正。失敗時ディレクトリを再利用せず`usace_candidate_v3/`に保存。
- セル最低高との差0〜約6.59mは監査情報であり、道路水深ではない。最低地盤高を道路全体に適用すると過大判定し得る。道路上地形・橋梁を別に確認する。
- 原日時文字列にtimezoneタグなし。日本の発災イベントとのJST対応・破堤時刻・先行越水を確認後に評価窓を固定する。開始時乾燥でリセットしない。

## 道路との領域照合

参照netはScenario Cの徒歩対応版。49,356全外部edgeを第一lane形状でUTM54Nへ戻し、実面セルのunionと交差させた。完全域内18,939、部分143、域外30,274。**全外部edge母数は常総市の市境内道路母数ではない**。車/歩行class別・全lane・利用経路・市境内のカバー率は後続検査で算出する。1laneの幾何検査を網羅的閉鎖判定としない。

域外は未計算であり乾燥0ではない。高架/橋の路面高、河道1D域、端部、地形欠測、道路立体交差も未解決。候補CSVの`closure_time_sec`は空欄、`road_deck_elevation_status=unverified`を全件保持する。

## 成果物と状態

`extract_usace.py`は候補抽出だけを行い、SUMO・配車器・既存閉鎖入力を変更/起動しない。新出力先の既存時は停止し上書きしない。

`derived/usace_candidate_v3/`：

- `native_water_surface.npz`：全列のnative水位/秒/座標/最低高と面積セル・境界列のID。
- `native_times.csv`：元日時と経過秒。
- `cells_utm54n.geojson`：面積セルの原頂点・セルID。
- `network_domain_coverage.csv`：全外部edgeの領域交差率、未確認路面高、空の閉鎖時刻。
- `audit.json`：入力・成果物SHA、構造検査、未採用項目。

現在は`NATIVE_WATER_SURFACE_ACQUIRED_NOT_RUN_READY`。独立照合は別の検査JSONへ記録する。5分間隔データ取得によりREAL-H2の公開数値データ探索は前進したが、H3道路入力/初期状態、H4照合、H5正式PAP・Registry、新executor/observer/スキル拡張とsmokeは未完了。

具体的な方法と仮定の選択は[開始前判断案](../../../03_研究設計文書/jdrt/常総市JDRT_実時間版_開始前判断案_v1.md)。新データを含む図は[独立図解](../../../03_研究設計文書/図表・UML/JDRT_実時間版_新データフロー_v1.html)。

## 作業環境と保全

HDF/GeoTIFF読取のため既存project venvへh5py3.16.0、rasterio1.5.2と依存affine3.0.1/attrs26.1.0/click8.5.0を追加。numpy等の既存版は変更しなかった。pipログは`derived/pip_hdf_raster.log`。研究コード/旧入力/旧runを編集しない。実行中の正本runはないことを確認した。

Driveは今回再取得せず、前段の読み取り監査を参照。Drive書込、先生/Dropbox/Gmailへの送信、外部問い合わせ、Web公開更新は実施しない。

訂正履歴：v2の領域CSVはfunction=internalだけを除外していたため、crossing/walkingareaを外部edgeへ誤算入した。id先頭コロンを除くv3へ訂正し、v2は未採用の監査履歴として保持する。865点の水位と面形状は同一SHA。元人口起点405中167、21,539人中11,965、Type4は937中544、施設位置点9中4が計算域内。起点内であっても全利用経路が域内という意味ではない。詳細はv3/population_domain_probe.json。

独立照合：`derived/USACE_独立照合.json`、2026-10-16 00:00:32 JSTに15検査PASS。元ZIP21ファイル・全水位/頂点/時刻/旧18SHAを別読取で照合。初回の検証は旧SHA台帳のwrapperを読み違えたため停止し、sha256フィールドの参照へ修正した。候補窓12:50〜18:50はnative73点。

## 追加技術確認・最終検査（2026-10-16）

`audit_structure_tags.py`で既存OSMの構造タグを照合し、49,356外部edge中49,348が元wayへ対応、8件は未対応。bridgeタグあり2,173edge（計算域内929/部分14/域外1,230）、tunnelタグあり308edge。高さは未取得。無タグを地表と証明したとは扱わない。CSV/JSONは候補v3の`structure_tags_audit.*`へ保存し、閉鎖は生成しない。

図解HTMLをローカルHTTP経由のブラウザで表示確認（狭い幅の折返しを確認）。計算域PNGを目視し下端注記と施設ラベルを修正後に再確認した。現状把握2形式/開始前判断案/図解2形式/本監査の6資料は66ローカルリンクの参照先存在・HTML ID重複なしを確認。`git diff --check`は終了0、既存worktreeのEOL警告のみ。旧outputのEOLを変更する操作はしていない。文書検査JSONは`derived/新系列準備_文書照合.json`。
