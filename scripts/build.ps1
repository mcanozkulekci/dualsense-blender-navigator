param([Parameter(Mandatory=$true)][string]$BlenderExe)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $projectRoot 'dist'
$manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'blender_manifest.toml') -Raw
$versionMatch = [regex]::Match($manifest, '(?m)^version\s*=\s*"([^"]+)"')
if (-not $versionMatch.Success) { throw 'Missing extension version' }
$packageName = "dualsense_navigator-$($versionMatch.Groups[1].Value).zip"
New-Item -ItemType Directory -Path $distDir -Force | Out-Null
& $BlenderExe --background --command extension build --source-dir $projectRoot --output-dir $distDir
if ($LASTEXITCODE -ne 0) { throw 'Extension build failed' }
$packagePath = Join-Path $distDir $packageName
& $BlenderExe --background --command extension validate $packagePath
if ($LASTEXITCODE -ne 0) { throw 'Extension validation failed' }
$packagesDir = Join-Path $projectRoot 'packages'
New-Item -ItemType Directory -Path $packagesDir -Force | Out-Null
Copy-Item -LiteralPath $packagePath -Destination (Join-Path $packagesDir $packageName) -Force
Write-Output "Package: $packagePath"
