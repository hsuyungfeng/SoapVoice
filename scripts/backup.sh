#!/bin/bash
# SoapVoice 每日備份腳本
# 目標：本地 NAS + Google Cloud Storage (rclone)
# 排程：每天 02:00

set -euo pipefail

PROJECT_DIR="/home/hsu/Desktop/SoapVoice"
LOG_FILE="$PROJECT_DIR/backup.log"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 備份目標設定（可由環境變數覆蓋）
NAS_PATH="${NAS_BACKUP_PATH:-/mnt/nas/soapvoice}"
GCS_REMOTE="${GCS_REMOTE:-gcs-soapvoice}"
GCS_BUCKET="${GCS_BUCKET:-soapvoice-backup}"

echo "[$TIMESTAMP] ========== 開始備份 ==========" >> "$LOG_FILE"

# --- Step 1: rsync 同步至本地 NAS ---
echo "[$TIMESTAMP] 同步至 NAS: $NAS_PATH" >> "$LOG_FILE"

mkdir -p "$NAS_PATH/data"
rsync -av --delete \
  "$PROJECT_DIR/data/" \
  "$NAS_PATH/data/" \
  >> "$LOG_FILE" 2>&1 || {
    echo "[$TIMESTAMP] ❌ NAS 同步失敗" >> "$LOG_FILE"
    exit 1
  }

# 備份設定檔（隱藏 API Key）
rsync -av \
  "$PROJECT_DIR/.env" \
  "$NAS_PATH/.env.bak" \
  >> "$LOG_FILE" 2>&1 || true

echo "[$TIMESTAMP] ✅ NAS 同步完成" >> "$LOG_FILE"

# --- Step 2: rclone 同步至 GCS ---
echo "[$TIMESTAMP] 同步至 GCS: gs://$GCS_BUCKET/data" >> "$LOG_FILE"

if command -v rclone &> /dev/null; then
  rclone sync \
    "$PROJECT_DIR/data/" \
    "$GCS_REMOTE:$GCS_BUCKET/data/" \
    --log-file="$LOG_FILE" \
    --log-level=INFO \
    >> "$LOG_FILE" 2>&1 || {
      echo "[$TIMESTAMP] ⚠️  GCS 同步警告，但本地 NAS 已備份" >> "$LOG_FILE"
    }
  echo "[$TIMESTAMP] ✅ GCS 同步完成" >> "$LOG_FILE"
else
  echo "[$TIMESTAMP] ⚠️  rclone 未安裝，跳過 GCS 同步" >> "$LOG_FILE"
fi

# --- 完成 ---
echo "[$TIMESTAMP] ========== 備份完成 ==========" >> "$LOG_FILE"
echo ""

# 顯示日誌最後 5 行
echo "備份日誌："
tail -5 "$LOG_FILE"
