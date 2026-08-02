$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

function Read-WithDefault {
    param([string]$Prompt, [string]$Default)
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

Write-Host "TH Stock -> Appwrite staging orphan cleanup" -ForegroundColor Cyan
Write-Host "Dry-run is mandatory before deletion. Unknown/manual files are never deleted."
$endpoint = Read-WithDefault "Appwrite endpoint" "https://sgp.cloud.appwrite.io/v1"
$projectId = Read-Host "Appwrite Project ID"
$bucketId = Read-WithDefault "Storage bucket ID" "market-data"
$secureKey = Read-Host "Appwrite API key (input is hidden)" -AsSecureString
if ([string]::IsNullOrWhiteSpace($projectId)) { throw "Project ID is required." }

$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) { throw "API key is required." }
    $env:APPWRITE_ENDPOINT = $endpoint
    $env:APPWRITE_PROJECT_ID = $projectId.Trim()
    $env:APPWRITE_API_KEY = $plainKey
    $env:APPWRITE_MARKET_BUCKET_ID = $bucketId

    & python scripts/cleanup_appwrite.py
    if ($LASTEXITCODE -ne 0) { throw "Cleanup dry-run failed; nothing was deleted." }
    $answer = Read-Host "Type DELETE ORPHANS to delete only the reported orphan objects"
    if ($answer -cne "DELETE ORPHANS") {
        Write-Host "Canceled; no remote files were deleted." -ForegroundColor Yellow
        exit 0
    }
    & python scripts/cleanup_appwrite.py --apply
    if ($LASTEXITCODE -ne 0) { throw "Cleanup failed." }
    Write-Host "Orphan cleanup completed." -ForegroundColor Green
}
finally {
    $env:APPWRITE_ENDPOINT = $null
    $env:APPWRITE_PROJECT_ID = $null
    $env:APPWRITE_API_KEY = $null
    $env:APPWRITE_MARKET_BUCKET_ID = $null
    $plainKey = $null
    if ($keyPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
}
