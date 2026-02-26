---
created: 2026-02-26T09:21:32.449Z
title: 執行硬體環境驗收測試
area: tooling
files:
  - DailyProgress.md:142-146
  - OpnusPlan.md:1440-1494
---

## Problem

需要詳細執行硬體驗收測試，包括 GPU 基準測試 (nvidia-smi)、GPU 效能測試等。此任務是 Phase 0 的第一步，必須在開始任何開發前完成。

驗收需要檢查：
- GPU 是否正確識別且驅動可用
- VRAM 是否達到 44GB
- CUDA 基本功能是否正常
- PyTorch 是否能正確訪問 GPU

## Solution

執行以下驗收測試命令：

```bash
# 1. 基本 GPU 信息
nvidia-smi
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv

# 2. 詳細 GPU 狀態
nvidia-smi dmon -s pucvmet

# 3. CUDA 驗證
nvcc --version
cat /usr/local/cuda/version.txt

# 4. PyTorch GPU 訪問測試
python3 << 'EOF'
import torch
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
print(f"GPU 數量: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
print(f"CUDA 版本: {torch.version.cuda}")
print(f"cuDNN 版本: {torch.backends.cudnn.version()}")
EOF

# 5. GPU 效能基準測試（可選）
# 使用 cuda-memtest 進行記憶體測試
# 或使用 pytorch 內置基準工具

# 6. 生成驗收報告
nvidia-smi > hardware_benchmark_$(date +%Y%m%d_%H%M%S).txt
```

驗收標準：
- ✅ GPU 正確識別（型號、VRAM、驅動版本）
- ✅ VRAM ≥ 44GB
- ✅ 驅動版本 ≥ 535
- ✅ CUDA ≥ 12.1
- ✅ PyTorch `torch.cuda.is_available()` = True
- ✅ GPU 可執行簡單 CUDA 操作

相關工具：
- scripts/verify_environment.sh (from OpnusPlan.md)
