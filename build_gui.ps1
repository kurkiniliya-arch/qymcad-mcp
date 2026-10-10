$ErrorActionPreference = 'Stop'
$env:OCCT_INCLUDE_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/include/opencascade'
$env:OCCT_LIB_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/lib'
$env:PATH = (Join-Path $PSScriptRoot 'vendor/qymcad-app') + ';' + $env:PATH
$env:CARGO_TARGET_DIR = Join-Path $PSScriptRoot 'gui-target'
$env:CARGO_PROFILE_DEV_DEBUG = '0'
& cargo build --manifest-path (Join-Path $PSScriptRoot '../QymCAD/Cargo.toml') --locked -p qymcad -j 4
if ($LASTEXITCODE -ne 0) { throw 'The QymCAD desktop build failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'gui-target/debug/qymcad.exe') -Destination (Join-Path $PSScriptRoot 'bin/qymcad.exe') -Force
