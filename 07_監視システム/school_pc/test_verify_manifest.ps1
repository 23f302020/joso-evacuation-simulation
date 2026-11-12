# 08_verify_manifest.ps1 の試験（一時ディレクトリの合成ファイルだけを使う）
# 実行: powershell -NoProfile -File test_verify_manifest.ps1   （失敗があれば終了コード1）
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '08_verify_manifest.ps1')

$script:failed = 0
function Assert-Equal($Actual, $Expected, $Name) {
    if (($Actual | ConvertTo-Json -Compress -Depth 5) -ceq ($Expected | ConvertTo-Json -Compress -Depth 5)) { "PASS  $Name" }
    else { "FAIL  $Name : expected=$($Expected | ConvertTo-Json -Compress) actual=$($Actual | ConvertTo-Json -Compress)"; $script:failed++ }
}

$tmp = Join-Path $env:TEMP ('verify_manifest_test_' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force (Join-Path $tmp 'root\sub') | Out-Null
$a = Join-Path $tmp 'root\a.txt'; $b = Join-Path $tmp 'root\sub\日本語.txt'
Set-Content $a 'hello' -Encoding ASCII -NoNewline; Set-Content $b 'world!!' -Encoding ASCII -NoNewline
(Get-Item $a).LastWriteTimeUtc = [datetime]::new(2026,01,02,03,04,05,[DateTimeKind]::Utc); (Get-Item $b).LastWriteTimeUtc = [datetime]::new(2026,02,03,04,05,06,[DateTimeKind]::Utc)
$csv = Join-Path $tmp 'manifest.csv'
@([pscustomobject]@{ path = 'a.txt'; size = 5; mtime_utc = '2026-01-02T03:04:05Z' },
  [pscustomobject]@{ path = 'sub/日本語.txt'; size = 7; mtime_utc = '2026-02-03T04:05:06Z' }) | Export-Csv $csv -NoTypeInformation -Encoding UTF8

$r = Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv
Assert-Equal $r.Checked 2 '2件を確認'
Assert-Equal $r.Missing.Count 0 '欠落なし'
Assert-Equal $r.SizeMismatch.Count 0 'サイズ不一致なし'
Assert-Equal $r.TimeMismatch.Count 0 '更新時刻の不一致なし'
Assert-Equal $r.Ok $true '全件OK'

# 欠落
Remove-Item $b
$r = Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv
Assert-Equal $r.Missing $(@('sub/日本語.txt')) '欠落したファイルを報告'
Assert-Equal $r.Ok $false '欠落があればNG'

# サイズ違い
Set-Content $b 'world' -Encoding ASCII -NoNewline; (Get-Item $b).LastWriteTimeUtc = [datetime]::new(2026,02,03,04,05,06,[DateTimeKind]::Utc)
$r = Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv
Assert-Equal $r.SizeMismatch $(@('sub/日本語.txt')) 'サイズ違いを報告'

# 更新時刻の許容（2秒以内はOK、それ以外はNG）
Set-Content $b 'world!!' -Encoding ASCII -NoNewline; (Get-Item $b).LastWriteTimeUtc = [datetime]::new(2026,02,03,04,05,07,[DateTimeKind]::Utc)
Assert-Equal (Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv).Ok $true '1秒のずれは許容（FAT系の精度）'
(Get-Item $b).LastWriteTimeUtc = [datetime]::new(2026,02,03,04,06,06,[DateTimeKind]::Utc)
$r = Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv
Assert-Equal $r.TimeMismatch $(@('sub/日本語.txt')) '1分のずれを報告'

# 余分なファイルは数えるだけ（NGにしない。ログやvenvが後から増えるため）
Set-Content (Join-Path $tmp 'root\extra.txt') 'x' -Encoding ASCII
(Get-Item $b).LastWriteTimeUtc = [datetime]::new(2026,02,03,04,05,06,[DateTimeKind]::Utc)
$r = Test-Manifest -Root (Join-Path $tmp 'root') -ManifestPath $csv
Assert-Equal $r.Ok $true '余分なファイルはNGにしない'

Remove-Item $tmp -Recurse -Force
if ($script:failed) { "`n$($script:failed) 件失敗"; exit 1 } else { "`n全件PASS" }
