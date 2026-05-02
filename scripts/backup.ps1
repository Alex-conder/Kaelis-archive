# Kaelis 数据备份脚本 (PowerShell)
# 备份 data/*.db、.env 和 ~/.kaelis/vault.json 到 backups/ 目录
# 保留最近 7 天版本

param(
    [string]$BackupDir = "backups",
    [int]$KeepDays = 7
)

$ErrorActionPreference = "Stop"

# 确保备份目录存在
$backupRoot = Resolve-Path $BackupDir -ErrorAction SilentlyContinue
if (-not $backupRoot) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
    $backupRoot = Resolve-Path $BackupDir
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "kaelis_backup_$timestamp"
$backupPath = Join-Path $backupRoot $backupName
New-Item -ItemType Directory -Path $backupPath | Out-Null

Write-Host "🗄️  Starting Kaelis backup to $backupPath ..."

# 1. 备份 SQLite 数据库
$dataDir = "data"
if (Test-Path $dataDir) {
    $dbBackupDir = Join-Path $backupPath "data"
    New-Item -ItemType Directory -Path $dbBackupDir | Out-Null
    Get-ChildItem -Path $dataDir -Filter "*.db" -Recurse | ForEach-Object {
        Copy-Item $_.FullName -Destination $dbBackupDir -Force
        Write-Host "   ✅ DB: $($_.Name)"
    }
}

# 2. 备份 .env（如果存在）
if (Test-Path ".env") {
    Copy-Item ".env" -Destination $backupPath -Force
    Write-Host "   ✅ .env"
}

# 3. 备份 CredentialVault
$vaultPath = Join-Path $env:USERPROFILE ".kaelis\vault.json"
if (Test-Path $vaultPath) {
    Copy-Item $vaultPath -Destination $backupPath -Force
    Write-Host "   ✅ vault.json"
}
$vaultKeyPath = Join-Path $env:USERPROFILE ".kaelis\vault.key"
if (Test-Path $vaultKeyPath) {
    Copy-Item $vaultKeyPath -Destination $backupPath -Force
    Write-Host "   ✅ vault.key"
}

# 4. 备份用户自定义模型配置
$modelDbPath = Join-Path $env:USERPROFILE ".kaelis\llm_models.db"
if (Test-Path $modelDbPath) {
    Copy-Item $modelDbPath -Destination $backupPath -Force
    Write-Host "   ✅ llm_models.db"
}

# 5. 打包为 zip
$zipPath = "$backupPath.zip"
Compress-Archive -Path $backupPath -DestinationPath $zipPath -Force
Remove-Item -Path $backupPath -Recurse -Force
Write-Host "📦 Backup archived: $zipPath"

# 6. 清理过期备份
Get-ChildItem -Path $backupRoot -Filter "kaelis_backup_*.zip" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays)
} | ForEach-Object {
    Remove-Item $_.FullName -Force
    Write-Host "   🗑️  Removed old backup: $($_.Name)"
}

Write-Host "✅ Backup complete."
