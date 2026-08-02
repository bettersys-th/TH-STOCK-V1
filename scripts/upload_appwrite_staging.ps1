param([switch]$UpdateFirst)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$sessionDir = Join-Path $repoRoot ("data\.cloud-upload-" + [Guid]::NewGuid().ToString("N"))

function Read-WithDefault {
    param([string]$Prompt, [string]$Default)
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

Write-Host "TH Stock -> Appwrite staging upload" -ForegroundColor Cyan
Write-Host "Credentials remain in this process only and are not written to a file."
Write-Host ""

if ($UpdateFirst) {
    Write-Host "This mode downloads fresh Yahoo data, runs quality checks, rebuilds the website, then offers an Appwrite upload." -ForegroundColor Yellow
    $updateAnswer = Read-Host "Type UPDATE to start the local market update"
    if ($updateAnswer -cne "UPDATE") {
        Write-Host "Canceled before downloading market data." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Installing pinned update dependencies..." -ForegroundColor Yellow
    & python -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Update dependency installation failed." }

    Write-Host "Running security checks and tests..." -ForegroundColor Yellow
    & python scripts/security_guard.py
    if ($LASTEXITCODE -ne 0) { throw "Security guard failed." }
    & python -m unittest discover -s scripts -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; market update was not started." }

    Write-Host "Downloading prices and rebuilding verified summaries. This can take a while..." -ForegroundColor Yellow
    & python scripts/update_and_build.py
    if ($LASTEXITCODE -ne 0) { throw "Update or quality gate failed; Appwrite upload was not started." }

    $qualityPath = Join-Path $repoRoot "data\data_quality.json"
    if (Test-Path -LiteralPath $qualityPath) {
        $quality = Get-Content -LiteralPath $qualityPath -Raw | ConvertFrom-Json
        Write-Host ("Verified local data: {0} | {1} price tickers | status {2}" -f $quality.latestDate, $quality.priceTickers, $quality.status) -ForegroundColor Green
    }
    Write-Host "Local update passed. Appwrite credentials will be requested now." -ForegroundColor Green
    Write-Host ""
}

$endpoint = Read-WithDefault "Appwrite endpoint" "https://sgp.cloud.appwrite.io/v1"
$projectId = Read-Host "Appwrite Project ID"
$bucketId = Read-WithDefault "Storage bucket ID" "market-data"
$secureKey = Read-Host "Appwrite API key (input is hidden)" -AsSecureString

if ([string]::IsNullOrWhiteSpace($projectId)) {
    throw "Project ID is required."
}

$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) { throw "API key is required." }

    $env:APPWRITE_ENDPOINT = $endpoint
    $env:APPWRITE_PROJECT_ID = $projectId.Trim()
    $env:APPWRITE_API_KEY = $plainKey
    $env:APPWRITE_MARKET_BUCKET_ID = $bucketId

    Write-Host ""
    Write-Host "Installing pinned uploader dependencies..." -ForegroundColor Yellow
    & python -m pip install --disable-pip-version-check -r requirements-appwrite.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

    Write-Host "Building and verifying local market objects..." -ForegroundColor Yellow
    & python scripts/cloud_export.py --output-dir $sessionDir
    if ($LASTEXITCODE -ne 0) { throw "Cloud export failed." }

    & python scripts/upload_appwrite.py --export-dir $sessionDir
    if ($LASTEXITCODE -ne 0) { throw "Upload dry-run failed." }

    $answer = Read-Host "Upload these verified objects to STAGING now? Type UPLOAD to continue"
    if ($answer -cne "UPLOAD") {
        Write-Host "Canceled before network upload; no remote data was changed." -ForegroundColor Yellow
        exit 0
    }

    & python scripts/upload_appwrite.py --export-dir $sessionDir --apply
    if ($LASTEXITCODE -ne 0) { throw "Appwrite upload failed." }
    Write-Host "Staging upload completed." -ForegroundColor Green
}
finally {
    $env:APPWRITE_ENDPOINT = $null
    $env:APPWRITE_PROJECT_ID = $null
    $env:APPWRITE_API_KEY = $null
    $env:APPWRITE_MARKET_BUCKET_ID = $null
    $plainKey = $null
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    if ((Test-Path -LiteralPath $sessionDir) -and $sessionDir.StartsWith((Join-Path $repoRoot "data\.cloud-upload-"))) {
        Remove-Item -LiteralPath $sessionDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
