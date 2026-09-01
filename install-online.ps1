[CmdletBinding()]
param(
    [string]$Ref = $(if ($env:AI_REVIEW_REF) { $env:AI_REVIEW_REF } else { "main" }),
    [string]$Token = $(
        if ($env:GITHUB_TOKEN) {
            $env:GITHUB_TOKEN
        } elseif ($env:GH_TOKEN) {
            $env:GH_TOKEN
        } else {
            ""
        }
    ),
    [string]$InstallDir,
    [string]$BinDir,
    [switch]$AddToPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Repository = "oomheap/ai-code-review-kit"
$TempRoot = $null

if ($Ref -notmatch "^[A-Za-z0-9._-]+$") {
    throw "Invalid ref: $Ref"
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("ai-review-online-" + [Guid]::NewGuid())
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
    $RawBase = "https://raw.githubusercontent.com/$Repository/$Ref"
    $Payload = @(
        "install.ps1",
        "src/ai_review.py",
        "prompts/review.md",
        "config/default.json",
        "bin/ai-review.cmd",
        "bin/ai-review.ps1"
    )

    foreach ($RelativePath in $Payload) {
        $Destination = Join-Path $TempRoot $RelativePath
        $Parent = Split-Path -Parent $Destination
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
        $UrlPath = $RelativePath.Replace("\", "/")
        $RequestArguments = @{
            UseBasicParsing = $true
            OutFile = $Destination
        }
        if ($Token) {
            $RequestArguments["Uri"] = "https://api.github.com/repos/$Repository/contents/${UrlPath}?ref=$Ref"
            $RequestArguments["Headers"] = @{
                Authorization = "Bearer $Token"
                Accept = "application/vnd.github.raw+json"
                "X-GitHub-Api-Version" = "2022-11-28"
            }
        } else {
            $RequestArguments["Uri"] = "$RawBase/$UrlPath"
        }
        Invoke-WebRequest @RequestArguments
        if (-not (Test-Path -LiteralPath $Destination -PathType Leaf)) {
            throw "Download failed: $RelativePath"
        }
        if ((Get-Item -LiteralPath $Destination).Length -eq 0) {
            throw "Downloaded an empty file: $RelativePath"
        }
    }

    $InstallArguments = @{}
    if ($PSBoundParameters.ContainsKey("InstallDir")) {
        $InstallArguments["InstallDir"] = $InstallDir
    }
    if ($PSBoundParameters.ContainsKey("BinDir")) {
        $InstallArguments["BinDir"] = $BinDir
    }
    if ($AddToPath) {
        $InstallArguments["AddToPath"] = $true
    }

    Write-Host "Installing ai-review from GitHub ref $Ref..."
    & (Join-Path $TempRoot "install.ps1") @InstallArguments
} finally {
    if ($TempRoot -and (Test-Path -LiteralPath $TempRoot)) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
    }
}
