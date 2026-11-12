# USB 転送の展開手順（学校PC）

> 開発PCから USB へ、研究フォルダを **1つの tar** にまとめて運び、学校PCで展開する手順（SP-24）。小さなファイルを約4万個、USB へ直接書くと極端に遅かったため（約3 MB/s で停止）、1ファイルに変更した。**予行演習（開発PCで、ハッシュ確認→展開→外した2フォルダの通常コピー→一覧照合）は成功済み**（40,712ファイルすべて一致、約9分）。**学校PCでの実行は未実施。**

## USB（`JDRT_transfer`）の中身
| 名前 | 内容 |
|---|---|
| `research.tar` | 研究フォルダ（`02_robocopy.ps1` と同じ除外ルール適用後）。約21.7 GiB。**2026-11-12 16:08 時点のスナップショット** |
| `research.tar.sha256` | `research.tar` の SHA-256（壊れていないか確認用） |
| `manifest.csv` | 全40,712ファイルの一覧（path, size, mtime_utc）。展開後の照合用 |
| `extras\4年次本研究\04_プログラム\data\…` | tar から外した2フォルダ（`flood_hazard_a31`、`flood_kml`）。名前が文字化けしたフォルダを含み、`bsdtar` が異常終了するため、通常のコピーで運ぶ |
| `08_verify_manifest.ps1` | 一覧との照合スクリプト（読取のみ） |
| `latest_school_pc\` | 開発PCの `07_監視システム\school_pc` の最新（スナップショット以降に追加・更新した文書とスクリプトを含む） |
| `README_学校PC.md` | この文書 |

## 手順（学校PCの PowerShell。`<…>` は置き換える）
**0. 配置先を決める。** 空きは **30 GiB 以上**。2通りある（どちらも展開後の中身は同じ）。日本語を含むパスで監視タスクが起動するかは学校PCで未確認のため、**B（英数字のパス）を推奨**。
- **A：フォルダ名を残す** → 配置先（ROOT）は `C:\JDRT\4年次本研究`
- **B：英数字のパスにする** → ROOT は `C:\JDRT\research`

```powershell
$usb = '<USBのドライブ文字>:\JDRT_transfer'
$root = 'C:\JDRT\research'          # B の場合。A なら 'C:\JDRT\4年次本研究'
```

**1. ハッシュ値を確認する**（2つが一致すること。読み出しに数分かかる）。

```powershell
(Get-FileHash -Algorithm SHA256 "$usb\research.tar").Hash.ToLower()
(Get-Content "$usb\research.tar.sha256").Split(' ')[0]
```

**2. 展開する**（約8〜10分）。

```powershell
# B（英数字のパス）：先頭の 4年次本研究 フォルダを取り除いて、$root の直下に展開する
New-Item -ItemType Directory -Force $root | Out-Null
tar -xf "$usb\research.tar" -C $root --strip-components=1

# A（フォルダ名を残す）の場合は、次の2行にする
#   New-Item -ItemType Directory -Force 'C:\JDRT' | Out-Null
#   tar -xf "$usb\research.tar" -C 'C:\JDRT'
```

**3. tar から外した2フォルダを加える。**

```powershell
robocopy "$usb\extras\4年次本研究" $root /E /COPY:DAT /DCOPY:DAT /R:1 /W:1
```

終了コードが 0〜7 なら成功。

**4. 一覧と照合する**（スナップショットとの照合。**最新の `school_pc` を重ねる前に行う**）。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$usb\08_verify_manifest.ps1" -Root $root -Manifest "$usb\manifest.csv"
```

期待：`確認: 40712 件 / 欠落: 0 / サイズ不一致: 0 / 更新時刻の不一致: 0` と `OK`。

**5. 最新の `school_pc` を重ねる**（スナップショット以降の更新を反映）。

```powershell
robocopy "$usb\latest_school_pc" "$root\07_監視システム\school_pc" /E /COPY:DAT /R:1 /W:1
```

**6. 次へ。** `$root\07_監視システム\school_pc\05_bootstrap.ps1` を、**確認のみ**（`-Apply` なし）で実行する。引数は [07 最初の依頼文](07_学校PCセッションの最初の依頼文.md) にある。

## 失敗したとき
- **ハッシュ値が違う：** 展開しない。USB から `research.tar` をコピーし直す、または USB の不良を疑う。
- **照合で不一致：** 一覧（最大20件ずつ）を保存して報告する。展開をやり直す前に、`$root` を削除しない（原因が分からなくなる）。
- **展開の途中で止まった：** 空き容量を確認する。`tar -xf` は同じコマンドの再実行で上書きできる。

## 後片付け
学校PCでの照合に通ったら、USB の `JDRT_transfer` を削除する（研究データを、持ち歩きの USB に残さない）。開発PCの `C:\Users\Ko_rr\JDRT_stage`、`JDRT_stage_out`、`JDRT_roundtrip` も、不要になったら削除する（合計約70 GiB）。

## 注意
- tar は **スナップショット**。以降に開発PCで変えたものは、`latest_school_pc` 以外には含まれない。
- 除外したもの：`.git`、開発メモ、アーカイブ、venv、キャッシュ、ログ、監視の `runtime`、`config.json`、`.claude`、`.codex`。秘密情報（アプリパスワード、トークン）は含まれない。
