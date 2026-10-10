$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$server = Join-Path $PSScriptRoot 'server.py'
$workspace = Join-Path $PSScriptRoot 'models'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run setup.ps1 first.' }
& codex mcp add qymcad --env PYTHONUTF8=1 -- $python -u $server --workspace $workspace --live
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
