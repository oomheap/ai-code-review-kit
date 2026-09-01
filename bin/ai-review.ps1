$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "ai-review.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $ScriptPath @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $ScriptPath @args
} else {
    Write-Error "Python 3.9 or later was not found in PATH."
    exit 2
}

exit $LASTEXITCODE
