$ErrorActionPreference = 'Stop'
$env:OCCT_INCLUDE_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/include/opencascade'
$env:OCCT_LIB_DIR = Join-Path $PSScriptRoot 'vendor/occt/Library/lib'
$env:PATH = (Join-Path $PSScriptRoot 'vendor/qymcad-app') + ';' + $env:PATH
$env:CARGO_TARGET_DIR = Join-Path $PSScriptRoot 'gui-target'
$env:CARGO_PROFILE_DEV_DEBUG = '0'
$output = Join-Path $PSScriptRoot 'tests-output'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$manifest = Join-Path $PSScriptRoot '../QymCAD/Cargo.toml'
$results = @{}
& cargo check --manifest-path $manifest --workspace --all-targets --locked -j 4 *> (Join-Path $output 'workspace-check.log')
$results.check = $LASTEXITCODE
Write-Output "Workspace check exit: $LASTEXITCODE"
& cargo clippy --manifest-path $manifest --workspace --all-targets --locked -j 4 -- -D warnings *> (Join-Path $output 'workspace-clippy.log')
$results.clippy = $LASTEXITCODE
Write-Output "Workspace clippy exit: $LASTEXITCODE"
& cargo test --manifest-path $manifest --workspace --locked -j 4 -- --test-threads=4 *> (Join-Path $output 'workspace-test.log')
$results.test = $LASTEXITCODE
Write-Output "Workspace test exit: $LASTEXITCODE"
$results | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'workspace-results.json') -Encoding utf8
