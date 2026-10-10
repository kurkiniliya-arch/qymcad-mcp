$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'open_gui.py')
if ($LASTEXITCODE -ne 0) { throw 'The desktop did not connect. Check .live for its log.' }
