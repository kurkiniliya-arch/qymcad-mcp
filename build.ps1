$ErrorActionPreference = 'Stop'
$env:OCCT_INCLUDE_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/include/opencascade'
$env:OCCT_LIB_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/lib'
$env:PATH = (Join-Path $PSScriptRoot 'vendor/occt/Library/bin') + ';' + $env:PATH
$env:CARGO_TARGET_DIR = Join-Path $PSScriptRoot 'backend/target'
& cargo build --manifest-path (Join-Path $PSScriptRoot 'backend/Cargo.toml') --locked -j 4
if ($LASTEXITCODE -ne 0) { throw 'The QymCAD backend build failed.' }
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'bin') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend/target/debug/qymcad-mcp-backend.exe') -Destination (Join-Path $PSScriptRoot 'bin/qymcad-mcp-backend.exe') -Force
