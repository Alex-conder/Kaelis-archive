#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SSL Certificate Manager for OpenClaw Assistant
.DESCRIPTION
    Manage SSL certificates: create, renew, check expiration
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$SSLConfig = "$EcosystemRoot\config\ssl-config.json"
$CertPath = "$EcosystemRoot\certs"
$SSLLog = "$EcosystemRoot\logs\ssl-manager.log"

function Initialize-SSLConfig {
    if (-not (Test-Path $SSLConfig)) {
        $config = @{
            Certificates = @(
                @{
                    Name = "default"
                    Domain = "localhost"
                    Path = "certs\localhost.pfx"
                    Password = "openclaw"
                    ValidDays = 365
                    AutoRenew = $true
                    RenewBeforeDays = 30
                }
            )
            Settings = @{
                KeySize = 2048
                HashAlgorithm = "SHA256"
                Country = "CN"
                Organization = "OpenClaw Assistant"
            }
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $SSLConfig
    }
    
    if (-not (Test-Path $CertPath)) {
        New-Item -ItemType Directory -Path $CertPath -Force | Out-Null
    }
}

function Get-SSLConfig {
    Initialize-SSLConfig
    return Get-Content $SSLConfig -Raw | ConvertFrom-Json
}

function Write-SSLLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $SSLLog -Value $entry
}

function New-SelfSignedCertificate {
    param(
        [string]$Name = "localhost",
        [string]$Domain = "localhost",
        [int]$ValidDays = 365,
        [string]$Password = "openclaw"
    )
    
    Write-Host "Creating self-signed certificate for: $Domain" -ForegroundColor Cyan
    Write-SSLLog "Creating certificate: $Domain"
    
    try {
        # Create certificate
        $cert = New-SelfSignedCertificate `
            -DnsName $Domain `
            -CertStoreLocation "cert:\LocalMachine\My" `
            -NotAfter (Get-Date).AddDays($ValidDays) `
            -KeyAlgorithm RSA `
            -KeyLength 2048 `
            -HashAlgorithm SHA256 `
            -KeyUsage DigitalSignature, KeyEncipherment `
            -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.1")
        
        # Export to PFX
        $pfxPath = "$CertPath\$Name.pfx"
        $securePassword = ConvertTo-SecureString -String $Password -Force -AsPlainText
        Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
        
        # Export public certificate
        $cerPath = "$CertPath\$Name.cer"
        Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
        
        # Remove from store
        Remove-Item -Path "cert:\LocalMachine\My\$($cert.Thumbprint)" -Force
        
        Write-Host "Certificate created successfully" -ForegroundColor Green
        Write-Host "  PFX: $pfxPath" -ForegroundColor Gray
        Write-Host "  CER: $cerPath" -ForegroundColor Gray
        Write-Host "  Thumbprint: $($cert.Thumbprint)" -ForegroundColor Gray
        Write-Host "  Valid until: $($cert.NotAfter)" -ForegroundColor Gray
        
        return @{
            Success = $true
            Thumbprint = $cert.Thumbprint
            Path = $pfxPath
            NotAfter = $cert.NotAfter
        }
    } catch {
        Write-Error "Failed to create certificate: $_"
        Write-SSLLog "Certificate creation failed: $_" "ERROR"
        return @{ Success = $false; Error = $_.Exception.Message }
    }
}

function Get-CertificateInfo {
    param([string]$CertPath)
    
    if (-not (Test-Path $CertPath)) {
        return $null
    }
    
    try {
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
        $cert.Import($CertPath)
        
        return @{
            Subject = $cert.Subject
            Issuer = $cert.Issuer
            NotBefore = $cert.NotBefore
            NotAfter = $cert.NotAfter
            Thumbprint = $cert.Thumbprint
            HasPrivateKey = $cert.HasPrivateKey
            DaysUntilExpiry = ($cert.NotAfter - [datetime]::Now).Days
        }
    } catch {
        return $null
    }
}

function Show-CertificateStatus {
    Initialize-SSLConfig
    $config = Get-SSLConfig
    
    Write-Host "`n[SSL Certificate Status]" -ForegroundColor Cyan
    
    foreach ($certConfig in $config.Certificates) {
        $fullPath = "$EcosystemRoot\$($certConfig.Path)"
        $info = Get-CertificateInfo -CertPath $fullPath
        
        Write-Host "`n$($certConfig.Name):" -ForegroundColor Yellow
        Write-Host "  Domain: $($certConfig.Domain)" -ForegroundColor Gray
        Write-Host "  Path: $fullPath" -ForegroundColor Gray
        
        if ($info) {
            $expiryColor = if ($info.DaysUntilExpiry -lt 30) { "Red" } elseif ($info.DaysUntilExpiry -lt 60) { "Yellow" } else { "Green" }
            Write-Host "  Status: Valid" -ForegroundColor Green
            Write-Host "  Expires: $($info.NotAfter) ($($info.DaysUntilExpiry) days)" -ForegroundColor $expiryColor
            Write-Host "  Thumbprint: $($info.Thumbprint)" -ForegroundColor Gray
        } else {
            Write-Host "  Status: Not found" -ForegroundColor Red
        }
    }
}

function Test-CertificateExpiry {
    Initialize-SSLConfig
    $config = Get-SSLConfig
    
    Write-Host "`n[Certificate Expiry Check]" -ForegroundColor Cyan
    
    $expiringCerts = @()
    
    foreach ($certConfig in $config.Certificates) {
        $fullPath = "$EcosystemRoot\$($certConfig.Path)"
        $info = Get-CertificateInfo -CertPath $fullPath
        
        if ($info -and $info.DaysUntilExpiry -lt $certConfig.RenewBeforeDays) {
            $expiringCerts += @{
                Name = $certConfig.Name
                Domain = $certConfig.Domain
                DaysLeft = $info.DaysUntilExpiry
                AutoRenew = $certConfig.AutoRenew
            }
        }
    }
    
    if ($expiringCerts.Count -eq 0) {
        Write-Host "All certificates are valid" -ForegroundColor Green
    } else {
        Write-Host "Expiring certificates:" -ForegroundColor Yellow
        foreach ($cert in $expiringCerts) {
            Write-Host "  - $($cert.Name) ($($cert.Domain)): $($cert.DaysLeft) days left" -ForegroundColor $(if ($cert.DaysLeft -lt 7) { "Red" } else { "Yellow" })
            if ($cert.AutoRenew) {
                Write-Host "    Auto-renewal enabled" -ForegroundColor Gray
            }
        }
    }
    
    return $expiringCerts
}

function Install-Certificate {
    param(
        [string]$CertPath,
        [string]$Store = "LocalMachine"
    )
    
    if (-not (Test-Path $CertPath)) {
        Write-Error "Certificate not found: $CertPath"
        return $false
    }
    
    try {
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
        $cert.Import($CertPath)
        
        $storePath = "cert:\$Store\Root"
        $store = Get-Item $storePath
        $store.Open("ReadWrite")
        $store.Add($cert)
        $store.Close()
        
        Write-Host "Certificate installed to $Store\Root" -ForegroundColor Green
        return $true
    } catch {
        Write-Error "Failed to install certificate: $_"
        return $false
    }
}

# Main execution
switch ($args[0]) {
    "status" { Show-CertificateStatus }
    "create" {
        $name = if ($args[1]) { $args[1] } else { "localhost" }
        $domain = if ($args[2]) { $args[2] } else { $name }
        New-SelfSignedCertificate -Name $name -Domain $domain
    }
    "check" { Test-CertificateExpiry }
    "install" {
        if ($args[1]) {
            $store = if ($args[2]) { $args[2] } else { "LocalMachine" }
            Install-Certificate -CertPath $args[1] -Store $store
        } else {
            Write-Host "Usage: ssl-manager.ps1 install <cert_path> [store]" -ForegroundColor Yellow
        }
    }
    default {
        Write-Host "SSL Certificate Manager for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  ssl-manager.ps1 status              - Show certificate status" -ForegroundColor Gray
        Write-Host "  ssl-manager.ps1 create [name] [domain]  - Create self-signed certificate" -ForegroundColor Gray
        Write-Host "  ssl-manager.ps1 check               - Check certificate expiry" -ForegroundColor Gray
        Write-Host "  ssl-manager.ps1 install <path>      - Install certificate" -ForegroundColor Gray
    }
}
