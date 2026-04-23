#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Import/Export Tool for OpenClaw Assistant
.DESCRIPTION
    Import and export data in various formats
#>

$EcosystemRoot = "$env:USERPROFILE\.assistant-ecosystem"
$IEXConfig = "$EcosystemRoot\config\import-export.json"
$IEXLog = "$EcosystemRoot\logs\import-export.log"
$ExportPath = "$EcosystemRoot\exports"
$ImportPath = "$EcosystemRoot\imports"

function Initialize-IEXConfig {
    if (-not (Test-Path $IEXConfig)) {
        $config = @{
            Formats = @("json", "csv", "xml", "yaml")
            DefaultFormat = "json"
            Compression = $true
            Encryption = $false
            MaxExportSize = "100MB"
        }
        $config | ConvertTo-Json -Depth 10 | Set-Content $IEXConfig
    }
    
    if (-not (Test-Path $ExportPath)) {
        New-Item -ItemType Directory -Path $ExportPath -Force | Out-Null
    }
    if (-not (Test-Path $ImportPath)) {
        New-Item -ItemType Directory -Path $ImportPath -Force | Out-Null
    }
}

function Get-IEXConfig {
    Initialize-IEXConfig
    return Get-Content $IEXConfig -Raw | ConvertFrom-Json
}

function Write-IEXLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "o"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $IEXLog -Value $entry
}

function Export-Data {
    param(
        [string]$DataType,
        [string]$Format = "json",
        [string]$OutputFile = $null
    )
    
    $config = Get-IEXConfig
    
    if (-not $OutputFile) {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $OutputFile = "$ExportPath\$DataType-$timestamp.$Format"
    }
    
    Write-Host "Exporting $DataType to $Format format..." -ForegroundColor Cyan
    
    # Simulate data export
    $data = @{
        ExportType = $DataType
        ExportTime = Get-Date -Format "o"
        Version = "1.0"
        Records = Get-Random -Minimum 10 -Maximum 100
        Data = @()
    }
    
    for ($i = 1; $i -le $data.Records; $i++) {
        $data.Data += @{
            Id = $i
            Name = "Record $i"
            Created = (Get-Date).AddDays(-$i).ToString("yyyy-MM-dd")
        }
    }
    
    switch ($Format.ToLower()) {
        "json" {
            $data | ConvertTo-Json -Depth 5 | Set-Content $OutputFile
        }
        "csv" {
            $csv = $data.Data | ConvertTo-Csv -NoTypeInformation
            $csv | Set-Content $OutputFile
        }
        "xml" {
            $xml = $data | ConvertTo-Xml -NoTypeInformation
            $xml.Save($OutputFile)
        }
        default {
            $data | ConvertTo-Json | Set-Content $OutputFile
        }
    }
    
    if ($config.Compression) {
        $zipFile = "$OutputFile.zip"
        Compress-Archive -Path $OutputFile -DestinationPath $zipFile -Force
        Remove-Item $OutputFile
        $OutputFile = $zipFile
    }
    
    $fileInfo = Get-Item $OutputFile
    Write-Host "Export completed: $OutputFile" -ForegroundColor Green
    Write-Host "  Size: $([math]::Round($fileInfo.Length / 1KB, 2)) KB" -ForegroundColor Gray
    Write-Host "  Records: $($data.Records)" -ForegroundColor Gray
    
    Write-IEXLog "Exported $DataType to $OutputFile"
    
    return $OutputFile
}

function Import-Data {
    param(
        [string]$FilePath,
        [string]$Target = "default"
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Error "File not found: $FilePath"
        return
    }
    
    Write-Host "Importing from: $FilePath" -ForegroundColor Cyan
    
    $fileInfo = Get-Item $FilePath
    $extension = $fileInfo.Extension.ToLower()
    
    # Handle compressed files
    if ($extension -eq ".zip") {
        $tempPath = "$env:TEMP\import-$(Get-Random)"
        Expand-Archive -Path $FilePath -DestinationPath $tempPath -Force
        $FilePath = (Get-ChildItem $tempPath -File | Select-Object -First 1).FullName
        $extension = (Get-Item $FilePath).Extension.ToLower()
    }
    
    # Parse based on format
    $data = $null
    switch ($extension) {
        ".json" {
            $data = Get-Content $FilePath -Raw | ConvertFrom-Json
        }
        ".csv" {
            $data = Import-Csv $FilePath
        }
        ".xml" {
            [xml]$data = Get-Content $FilePath
        }
        default {
            Write-Error "Unsupported format: $extension"
            return
        }
    }
    
    # Simulate import
    $recordCount = if ($data.Data) { $data.Data.Count } else { $data.Count }
    
    Write-Host "Import completed" -ForegroundColor Green
    Write-Host "  Records: $recordCount" -ForegroundColor Gray
    
    Write-IEXLog "Imported from $FilePath to $Target"
    
    # Cleanup temp
    if ($tempPath -and (Test-Path $tempPath)) {
        Remove-Item $tempPath -Recurse -Force
    }
}

function Show-IEXStatus {
    $config = Get-IEXConfig
    
    Write-Host "`n[Import/Export Status]" -ForegroundColor Cyan
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Supported formats: $($config.Formats -join ', ')" -ForegroundColor Gray
    Write-Host "  Default format: $($config.DefaultFormat)" -ForegroundColor Gray
    Write-Host "  Compression: $($config.Compression)" -ForegroundColor Gray
    Write-Host "  Encryption: $($config.Encryption)" -ForegroundColor Gray
    Write-Host "  Max export size: $($config.MaxExportSize)" -ForegroundColor Gray
    
    Write-Host "`nExports:" -ForegroundColor Yellow
    if (Test-Path $ExportPath) {
        $exports = Get-ChildItem $ExportPath -File
        Write-Host "  Files: $($exports.Count)" -ForegroundColor Gray
        $totalSize = ($exports | Measure-Object -Property Length -Sum).Sum
        Write-Host "  Total size: $([math]::Round($totalSize / 1MB, 2)) MB" -ForegroundColor Gray
    }
    
    Write-Host "`nImports:" -ForegroundColor Yellow
    if (Test-Path $ImportPath) {
        $imports = Get-ChildItem $ImportPath -File
        Write-Host "  Files: $($imports.Count)" -ForegroundColor Gray
    }
}

function List-Exports {
    Write-Host "`n[Export Files]" -ForegroundColor Cyan
    
    if (Test-Path $ExportPath) {
        $files = Get-ChildItem $ExportPath -File | Sort-Object LastWriteTime -Descending
        
        foreach ($file in $files) {
            Write-Host "  $($file.Name)" -ForegroundColor White
            Write-Host "    Size: $([math]::Round($file.Length / 1KB, 2)) KB" -ForegroundColor Gray
            Write-Host "    Date: $($file.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
        }
    } else {
        Write-Host "No exports found" -ForegroundColor Yellow
    }
}

# Main execution
switch ($args[0]) {
    "export" {
        if ($args[1]) {
            $format = if ($args[2]) { $args[2] } else { "json" }
            Export-Data -DataType $args[1] -Format $format
        } else {
            Write-Host "Usage: import-export.ps1 export <data_type> [format]" -ForegroundColor Yellow
        }
    }
    "import" {
        if ($args[1]) {
            $target = if ($args[2]) { $args[2] } else { "default" }
            Import-Data -FilePath $args[1] -Target $target
        } else {
            Write-Host "Usage: import-export.ps1 import <file_path> [target]" -ForegroundColor Yellow
        }
    }
    "status" { Show-IEXStatus }
    "list" { List-Exports }
    default {
        Write-Host "Import/Export Tool for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  import-export.ps1 export <type> [format]  - Export data" -ForegroundColor Gray
        Write-Host "  import-export.ps1 import <file> [target]  - Import data" -ForegroundColor Gray
        Write-Host "  import-export.ps1 status                  - Show status" -ForegroundColor Gray
        Write-Host "  import-export.ps1 list                    - List exports" -ForegroundColor Gray
    }
}
