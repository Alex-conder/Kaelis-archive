#!/usr/bin/env bash
# Kaelis 数据备份脚本 (Bash)
# 备份 data/*.db、.env 和 ~/.kaelis/vault.json 到 backups/ 目录
# 保留最近 7 天版本

set -euo pipefail

BACKUP_DIR="${1:-backups}"
KEEP_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="kaelis_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "$BACKUP_PATH"
echo "🗄️  Starting Kaelis backup to $BACKUP_PATH ..."

# 1. 备份 SQLite 数据库
if [ -d "data" ]; then
    mkdir -p "$BACKUP_PATH/data"
    find data -name "*.db" -exec cp {} "$BACKUP_PATH/data/" \;
    echo "   ✅ DB files backed up"
fi

# 2. 备份 .env
if [ -f ".env" ]; then
    cp ".env" "$BACKUP_PATH/"
    echo "   ✅ .env"
fi

# 3. 备份 CredentialVault
VAULT_PATH="$HOME/.kaelis/vault.json"
if [ -f "$VAULT_PATH" ]; then
    cp "$VAULT_PATH" "$BACKUP_PATH/"
    echo "   ✅ vault.json"
fi

# 4. 备份用户自定义模型配置
MODEL_DB_PATH="$HOME/.kaelis/llm_models.db"
if [ -f "$MODEL_DB_PATH" ]; then
    cp "$MODEL_DB_PATH" "$BACKUP_PATH/"
    echo "   ✅ llm_models.db"
fi

# 5. 打包为 tar.gz
TAR_PATH="${BACKUP_PATH}.tar.gz"
tar -czf "$TAR_PATH" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_PATH"
echo "📦 Backup archived: $TAR_PATH"

# 6. 清理过期备份
find "$BACKUP_DIR" -name "kaelis_backup_*.tar.gz" -mtime +$KEEP_DAYS -delete
echo "   🗑️  Old backups cleaned (>$KEEP_DAYS days)"

echo "✅ Backup complete."
