[CmdletBinding()]
param(
    [string]$InstallDir = $(
        if ($env:LOCALAPPDATA) {
            Join-Path $env:LOCALAPPDATA "AiCodeReview"
        } else {
            Join-Path $env:USERPROFILE ".local\share\AiCodeReview"
        }
    ),
    [string]$BinDir = $(Join-Path $env:USERPROFILE ".local\bin"),
    [switch]$AddToPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
} else {
    throw "Python 3.9 or later is required."
}

if ($LASTEXITCODE -ne 0) {
    throw "Python 3.9 or later is required."
}

$Payload = @(
    "src\ai_review.py",
    "prompts\review.md",
    "config\default.json",
    "bin\ai-review.cmd",
    "bin\ai-review.ps1"
)

foreach ($RelativePath in $Payload) {
    if (-not (Test-Path -LiteralPath (Join-Path $ScriptDir $RelativePath) -PathType Leaf)) {
        throw "Installer payload is incomplete: $RelativePath"
    }
}

$Directories = @(
    $InstallDir,
    (Join-Path $InstallDir "src"),
    (Join-Path $InstallDir "prompts"),
    (Join-Path $InstallDir "config"),
    (Join-Path $BinDir "ai-review-data\prompts"),
    $BinDir
)

foreach ($Directory in $Directories) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
}

Copy-Item -LiteralPath (Join-Path $ScriptDir "src\ai_review.py") -Destination (Join-Path $InstallDir "src\ai_review.py") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "prompts\review.md") -Destination (Join-Path $InstallDir "prompts\review.md") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "config\default.json") -Destination (Join-Path $InstallDir "config\default.json") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "src\ai_review.py") -Destination (Join-Path $BinDir "ai-review.py") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "prompts\review.md") -Destination (Join-Path $BinDir "ai-review-data\prompts\review.md") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "bin\ai-review.cmd") -Destination (Join-Path $BinDir "ai-review.cmd") -Force
Copy-Item -LiteralPath (Join-Path $ScriptDir "bin\ai-review.ps1") -Destination (Join-Path $BinDir "ai-review.ps1") -Force

if ($AddToPath) {
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $PathEntries = @($UserPath -split ";" | Where-Object { $_ })
    if (-not ($PathEntries | Where-Object { $_.TrimEnd("\") -ieq $BinDir.TrimEnd("\") })) {
        $NewPath = (($PathEntries + $BinDir) -join ";")
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    }
    if (-not (($env:Path -split ";") | Where-Object { $_.TrimEnd("\") -ieq $BinDir.TrimEnd("\") })) {
        $env:Path = "$env:Path;$BinDir"
    }
}

Write-Host "Installed ai-review 1.0.0 to $(Join-Path $BinDir 'ai-review.cmd')"
if (-not $AddToPath) {
    Write-Host "Add $BinDir to PATH, or reinstall with -AddToPath."
}
Write-Host "Run: ai-review --doctor"
