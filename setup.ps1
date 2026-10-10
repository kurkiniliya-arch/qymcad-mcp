param([string]$Python)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
$venvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required. Pass -Python with its full path.' }
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'vendor/qymcad-app/TKernel.dll'))) {
    & $venvPython (Join-Path $PSScriptRoot 'setup_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime installation failed.' }
}
& $venvPython (Join-Path $PSScriptRoot 'make_config.py')
if ($LASTEXITCODE -ne 0) { throw 'Configuration generation failed.' }
Write-Output 'QymCAD MCP is ready. Run install_codex.ps1 to register it in Codex.'
