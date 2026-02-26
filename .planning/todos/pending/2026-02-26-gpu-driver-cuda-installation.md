---
created: 2026-02-26T09:21:32.449Z
title: GPU 驅動與 CUDA 安裝
area: tooling
files:
  - OpnusPlan.md:65-66
  - OpnusPlan.md:1213-1220
---

## Problem

需要安裝 NVIDIA GPU 驅動 (≥535) 和 CUDA 12.1+ 以支援深度學習模型推理。此步驟完成後方可進行模型推理測試。

前置條件：
- 硬體環境測試已通過
- Ubuntu 22.04+ 系統已安裝
- 網路連線正常

## Solution

按照以下步驟安裝 GPU 驅動和 CUDA：

```bash
# 1. 更新系統
sudo apt update && sudo apt upgrade -y

# 2. 安裝 NVIDIA Driver (≥535)
ubuntu-drivers install nvidia-driver-535
# 或使用 NVIDIA 官方安裝程序
wget https://us.download.nvidia.com/XFree86/Linux-x86_64/535.xx/NVIDIA-Linux-x86_64-535.xx.run
sudo bash NVIDIA-Linux-x86_64-535.xx.run

# 3. 重開機（驅動安裝後需要）
sudo reboot

# 4. 驗證驅動安裝
nvidia-smi

# 5. 安裝 CUDA 12.1
wget https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda_12.1.0_530.30.02_linux.run
sudo bash cuda_12.1.0_530.30.02_linux.run

# 6. 配置環境變數
echo 'export PATH=/usr/local/cuda-12.1/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# 7. 驗證 CUDA 安裝
nvcc --version
```

驗收標準：
- ✅ `nvidia-smi` 能正常顯示 GPU 信息
- ✅ `nvcc --version` 顯示 CUDA 12.1+
- ✅ GPU 驅動版本 ≥535
