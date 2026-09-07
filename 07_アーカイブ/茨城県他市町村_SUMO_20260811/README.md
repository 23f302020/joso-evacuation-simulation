# 茨城県他市町村 SUMO出力アーカイブ

> 作成日：2026-08-11  
> 目的：常総市JDRTのアクティブ領域から、常総市以外の地域別SUMO出力を分離する

## 実施結果

- 移動自治体数：40
- ファイル数：1,415
- 容量：3,918,072,159 bytes（約3.74GB）
- アクティブ側に残した地域フォルダー：`08211`、`_management`
- 移動前後の全ファイルSHA-256：一致
- 復元スクリプト検査モード：PASS
- 地域一覧HTML：アーカイブ先へリンク変換済み、リンク切れ0
- unit test：137件PASS

データは削除されていない。`regions/`以下に自治体コード単位で保存している。

> **GitHub公開範囲：** このREADMEだけを追跡する。約3.74GBの実体、端末固有の絶対パスを含む`manifest.json`、そのパスを使う`restore_regions.ps1`はローカル保全とし、GitHubへは掲載しない。

## 対象

移動元：

`04_プログラム/output/sumo/regions/`

残すフォルダー：

- `08211`（常総市）
- `_management`

アーカイブ対象：上記以外の自治体コードフォルダー。

## 構成

```text
茨城県他市町村_SUMO_20260811/
  README.md
  manifest.json
  restore_regions.ps1
  regions/
    08201/
    08202/
    ...
```

`manifest.json`には自治体ごとの元パス、アーカイブ先、ファイル数、容量、全ファイルのSHA-256を保存する。移動は削除ではなく同一研究フォルダー内の`Move-Item`で行う。

## 復元

まず検査のみ実行する。

```powershell
powershell -ExecutionPolicy Bypass -File .\restore_regions.ps1
```

SHA、容量、復元先の重複がないことを確認後、実際に復元する。

```powershell
powershell -ExecutionPolicy Bypass -File .\restore_regions.ps1 -Apply
```

復元先はmanifestに記録された元の`04_プログラム/output/sumo/regions/{自治体コード}/`である。

## 注意

- 常総市JDRTは`08211/experiments/jdrt/`だけを参照する。
- Phase 2の他市町村別ページは、アーカイブ中は元の地域フォルダーを直接開けない。
- `scenario_cities/`、`unified/`、`data/`は本アーカイブの対象外。
- 常総市の既存Phase 2/3・Scenario C出力は移動しない。
- 常総市の過去runは既存評価スクリプトが参照するため据え置く。JDRTは専用workspaceによりこれらを列挙しない。
