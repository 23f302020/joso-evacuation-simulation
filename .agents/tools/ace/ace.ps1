$ErrorActionPreference = 'Stop'
$acePython = Join-Path $env:LOCALAPPDATA 'JDRT/tools/ace-runtime-82709de/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $acePython)) { throw 'ACE isolated runtime is missing. See the installation README.' }
& $acePython -I -B -X utf8 (Join-Path $PSScriptRoot 'ace_local.py') @args
exit $LASTEXITCODE
