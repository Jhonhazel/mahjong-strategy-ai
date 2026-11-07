param(
    [Parameter(Mandatory=$true)][string]$PostgresArchive,
    [Parameter(Mandatory=$true)][string]$Provenance,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Build on actual Windows x64. No cross compilation.' }
$buildPython = Join-Path (Get-Location) '.local\windows-build\venv\Scripts\python.exe'
if (-not (Test-Path $buildPython)) {
    & py -3.12 -m venv '.local\windows-build\venv'
    if ($LASTEXITCODE -ne 0) { throw 'Install CPython3.12 x64 for the build machine.' }
}
& $buildPython -m pip install 'torch==2.15.0' --index-url https://download.pytorch.org/whl/cpu --no-deps
if ($LASTEXITCODE -ne 0) { throw 'Official CPU PyTorch installation failed.' }
& $buildPython -m pip install -r windows/requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements failed; inspect PyMahjongGB C++ toolchain/DLL prerequisites.' }
& $buildPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility failed.' }
& $buildPython -m scripts.build_windows_package --postgres-archive $PostgresArchive --provenance $Provenance --output $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Candidate build failed; do not distribute an incomplete package.' }
Write-Host 'Candidate built. Complete the clean-Windows offline acceptance checklist before claiming support.'
