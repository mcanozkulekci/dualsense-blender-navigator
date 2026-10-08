param([Parameter(Mandatory=$true)][string]$BlenderExe)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$profileDir = Join-Path $projectRoot '.test-profile'
$configDir = Join-Path $profileDir 'config'
$extensionsDir = Join-Path $profileDir 'extensions'
New-Item -ItemType Directory -Path $configDir,$extensionsDir -Force | Out-Null
$originalConfig = $env:BLENDER_USER_CONFIG
$originalExtensions = $env:BLENDER_USER_EXTENSIONS
try {
    $env:BLENDER_USER_CONFIG = $configDir
    $env:BLENDER_USER_EXTENSIONS = $extensionsDir
    & $BlenderExe --background --factory-startup --python-exit-code 1 --python (Join-Path $projectRoot 'tests\verify_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime checks failed' }
    & $BlenderExe --background --factory-startup --python-exit-code 1 --python (Join-Path $projectRoot 'tests\verify_install.py')
    if ($LASTEXITCODE -ne 0) { throw 'Extension install checks failed' }
    & $BlenderExe --background --python-exit-code 1 --python (Join-Path $projectRoot 'tests\verify_reload.py')
    if ($LASTEXITCODE -ne 0) { throw 'Extension reload checks failed' }
} finally {
    $env:BLENDER_USER_CONFIG = $originalConfig
    $env:BLENDER_USER_EXTENSIONS = $originalExtensions
}
