# Kaelis Landing Page Deploy Helper
param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

$ErrorActionPreference = "Stop"

Write-Host "Deploying Kaelis Landing Page to Vercel..." -ForegroundColor Cyan

Set-Location $PSScriptRoot\web\landing

# Deploy with token
npx vercel --prod --token $Token --yes

Write-Host "Done! Landing page deployed." -ForegroundColor Green
