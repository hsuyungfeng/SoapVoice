---
created: 2026-02-26T09:21:32.449Z
title: 檢查 SSD 容量和可用空間
area: tooling
files:
  - DailyProgress.md:144
  - OpnusPlan.md:1200-1207
---

## Problem

需要確認 SSD 容量是否 ≥1TB，並評估可用空間是否足以容納：
- AI 模型（Qwen3-32B ~65GB、Faster-Whisper ~3GB、GLM-4.7-Flash ~10GB）
- 開發環境和依賴（~50-100GB）
- 資料庫和日誌（~50GB）
- 緩存和臨時檔案（~20GB）

總計需求約 200+ GB，因此 SSD 應至少有 1TB，建議 2TB 以上。

## Solution

執行以下檢查命令：

```bash
# 1. 檢查所有磁碟和分區
df -h
lsblk
fdisk -l

# 2. 詳細檢查根分區和 /home
df -h /
df -h /home

# 3. 檢查檔案系統類型
df -T

# 4. 檢查 SSD 型號和容量
sudo nvme list  # 如果是 NVMe SSD
sudo smartctl -a /dev/nvme0n1  # 詳細信息（需安裝 smartmontools）

# 5. 估算已用空間分布
du -sh /*
du -sh ~/.cache
du -sh /tmp

# 6. 生成容量報告
echo "=== SSD 容量驗收報告 ===" > ssd_capacity_check.txt
date >> ssd_capacity_check.txt
echo "" >> ssd_capacity_check.txt
df -h >> ssd_capacity_check.txt
echo "" >> ssd_capacity_check.txt
lsblk >> ssd_capacity_check.txt
```

驗收標準：
- ✅ SSD 總容量 ≥ 1TB
- ✅ 可用空間 ≥ 500GB（用於模型、依賴、資料）
- ✅ 根分區有充足空間（≥ 100GB 可用）
- ✅ /home 或資料目錄有充足空間（≥ 200GB 可用）
- ✅ 檔案系統為 ext4 或 btrfs（不推薦 ntfs 或 fat32）

期望結果：
- 若可用空間不足，需考慮：
  - 清理不必要檔案
  - 擴展儲存容量
  - 使用外部 SSD（USB 3.1 Gen 2，≥ 4TB）
