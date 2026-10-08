param([Parameter(Mandatory=$true)][string]$BlenderExe)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configDir = Join-Path $projectRoot '.test-profile\config'
$extensionsDir = Join-Path $projectRoot '.test-profile\extensions'
if (-not (Test-Path -LiteralPath (Join-Path $configDir 'userpref.blend'))) {
    throw 'Run build.ps1 and test.ps1 first to install the extension into isolated preferences'
}
$outputDir = Join-Path $projectRoot 'test-output'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$resultPath = Join-Path $outputDir 'gui_verification.json'
if (Test-Path -LiteralPath $resultPath) { Remove-Item -LiteralPath $resultPath }
$runId = [guid]::NewGuid().ToString('N').Substring(0,8)
$stdoutPath = Join-Path $outputDir "gui-$runId-stdout.log"
$stderrPath = Join-Path $outputDir "gui-$runId-stderr.log"
$originalConfig = $env:BLENDER_USER_CONFIG
$originalExtensions = $env:BLENDER_USER_EXTENSIONS
try {
    $env:BLENDER_USER_CONFIG = $configDir
    $env:BLENDER_USER_EXTENSIONS = $extensionsDir
    $guiScript = Join-Path $projectRoot 'tests\verify_gui.py'
    # Visible on purpose: this separate interactive window is also the user demo.
    $testProcess = Start-Process -FilePath $BlenderExe -ArgumentList @('--python', ('"' + $guiScript + '"')) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
} finally {
    $env:BLENDER_USER_CONFIG = $originalConfig
    $env:BLENDER_USER_EXTENSIONS = $originalExtensions
}
$testProcess.Id | Set-Content (Join-Path $outputDir 'gui.pid')
$deadline = (Get-Date).AddSeconds(30)
while (-not (Test-Path -LiteralPath $resultPath) -and (Get-Date) -lt $deadline -and -not $testProcess.HasExited) {
    Start-Sleep -Milliseconds 250
}
if (-not (Test-Path -LiteralPath $resultPath)) { throw "GUI test did not finish. See $stderrPath" }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if (-not $result.ok) { throw "GUI checks failed: $($result.errors -join '; ')" }
$stderrText = Get-Content -LiteralPath $stderrPath -Raw
if ($stderrText -match 'Traceback|Error:') { throw "GUI reported an error. See $stderrPath" }
Write-Output "GUI checks passed: $($result.checks.Count). Demo Blender PID: $($testProcess.Id)"
Write-Output "Test scene: $(Join-Path $outputDir 'DualSense_Cinematic_Test.blend')"
