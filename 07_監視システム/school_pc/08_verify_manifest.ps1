<#
.SYNOPSIS
  展開・コピーした研究フォルダを manifest.csv と照合する（読取のみ。何も変更しない）。

.DESCRIPTION
  manifest.csv の各行（path, size, mtime_utc）について、<Root> 側に同じファイルがあるか、
  サイズが同じか、更新時刻が許容（既定2秒。FAT系・tarの精度差）以内かを確かめる。
  余分なファイルは数えるだけで NG にしない（ログや venv が後から増えるため）。
  終了コード: 0 = 全件一致、1 = 不一致あり。

.EXAMPLE
  .\08_verify_manifest.ps1 -Root C:\JDRT\research\4年次本研究 -Manifest E:\JDRT_transfer\manifest.csv
#>
[CmdletBinding()]
param(
    [string]$Root,
    [string]$Manifest
)

function Test-Manifest([string]$Root, [string]$ManifestPath, [int]$ToleranceSec = 2) {
    $rows = Import-Csv -LiteralPath $ManifestPath -Encoding UTF8
    $missing = @(); $size = @(); $time = @()
    $styles = [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal
    foreach ($row in $rows) {
        $item = Get-Item -LiteralPath (Join-Path $Root ($row.path -replace '/', '\')) -Force -ErrorAction SilentlyContinue
        if ($null -eq $item -or $item.PSIsContainer) { $missing += $row.path; continue }
        if ($item.Length -ne [int64]$row.size) { $size += $row.path; continue }
        $expected = [datetime]::ParseExact($row.mtime_utc, "yyyy-MM-dd'T'HH:mm:ss'Z'", [Globalization.CultureInfo]::InvariantCulture, $styles)
        if ([math]::Abs(($item.LastWriteTimeUtc - $expected).TotalSeconds) -gt $ToleranceSec) { $time += $row.path }
    }
    return [pscustomobject]@{
        Checked = @($rows).Count; Missing = $missing; SizeMismatch = $size; TimeMismatch = $time
        Ok = (-not $missing -and -not $size -and -not $time)
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        if (-not $Root -or -not $Manifest) { Write-Host '使い方: -Root <配置先の4年次本研究> -Manifest <manifest.csv>'; exit 2 }
        $r = Test-Manifest -Root $Root -ManifestPath $Manifest
        Write-Host ("確認: {0} 件 / 欠落: {1} / サイズ不一致: {2} / 更新時刻の不一致: {3}" -f $r.Checked, @($r.Missing).Count, @($r.SizeMismatch).Count, @($r.TimeMismatch).Count)
        foreach ($group in @(@('欠落', $r.Missing), @('サイズ不一致', $r.SizeMismatch), @('更新時刻の不一致', $r.TimeMismatch))) {
            foreach ($p in @($group[1]) | Select-Object -First 20) { Write-Host ("  [{0}] {1}" -f $group[0], $p) }
        }
        if ($r.Ok) { Write-Host 'OK: manifest の全ファイルが、サイズ・更新時刻とも一致しています（内容のSHAは別に確認）。'; exit 0 }
        Write-Host 'NG: 不一致があります。上の一覧（最大20件ずつ）を確認してください。'; exit 1
    } catch {
        Write-Host ('[STOP] 予期しない例外: ' + $_.Exception.GetType().Name + ' / ' + $_.Exception.Message); exit 2
    }
}
