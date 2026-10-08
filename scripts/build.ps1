param([Parameter(Mandatory=$true)][string]$BlenderExe)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $projectRoot 'dist'
New-Item -ItemType Directory -Path $distDir -Force | Out-Null
& $BlenderExe --background --command extension build --source-dir $projectRoot --output-dir $distDir
if ($LASTEXITCODE -ne 0) { throw 'Extension build failed' }
$packagePath = Join-Path $distDir 'dualsense_navigator-1.0.0.zip'
& $BlenderExe --background --command extension validate $packagePath
if ($LASTEXITCODE -ne 0) { throw 'Extension validation failed' }
Write-Output "Package: $packagePath"
