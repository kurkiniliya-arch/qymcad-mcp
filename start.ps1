$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -u (Join-Path $PSScriptRoot 'server.py') --workspace (Join-Path $PSScriptRoot 'models') --live
exit $LASTEXITCODE
