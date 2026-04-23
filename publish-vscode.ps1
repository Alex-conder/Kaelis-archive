# Kaelis VSCode Extension Publish Helper
param(
    [Parameter(Mandatory=$true)]
    [string]$Pat
)

$ErrorActionPreference = "Stop"

Write-Host "Publishing Kaelis VSCode Extension..." -ForegroundColor Cyan

Set-Location $PSScriptRoot\vscode-kaelis

# Login with PAT
Write-Host "Step 1/3: Logging in to marketplace..."
npx vsce login kaelis --pat $Pat

# Package (verify)
Write-Host "Step 2/3: Packaging..."
npx vsce package

# Publish
Write-Host "Step 3/3: Publishing..."
npx vsce publish -p $Pat

Write-Host "Done! Extension published." -ForegroundColor Green
