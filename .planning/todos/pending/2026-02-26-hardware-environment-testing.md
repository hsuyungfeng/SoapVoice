---
created: 2026-02-26T09:21:32.449Z
title: 硬體環境測試
area: tooling
files:
  - OpnusPlan.md:62-65
  - DailyProgress.md:143-145
---

## Problem

Phase 0 的第一步是進行硬體環境驗收測試，確保伺服器的 CPU、RAM、GPU VRAM 和 SSD 容量符合專案要求。此任務未完成會阻擋後續所有開發工作。

需要驗證：
- CPU: Ryzen 9 5950X (16C/32T)
- RAM: 48GB DDR4
- GPU VRAM: 44GB (total) ✅ 待驗證
- SSD: ≥1TB NVMe ⏳ 待確認

## Solution

執行以下驗收命令：
```bash
# 檢查 CPU
cat /proc/cpuinfo | grep "model name" | head -1
cat /proc/cpuinfo | grep "processor" | wc -l

# 檢查 RAM
free -h

# 檢查 GPU
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# 檢查 SSD
df -h /home

# GPU 效能基準測試
python3 -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}'); print(f'CUDA: {torch.version.cuda}')"
```

預期輸出：
- CPU: 16 cores, 32 threads
- RAM: 48GB 可用
- GPU: 44GB VRAM
- SSD: ≥1TB 可用空間
- CUDA: 12.1+
