---
created: 2026-02-26T09:21:32.449Z
title: Docker 環境準備
area: tooling
files:
  - OpnusPlan.md:68-69
  - OpnusPlan.md:361-413
---

## Problem

需要安裝並配置 Docker 和 Docker Compose，為後續容器化部署做準備。Docker 將用於隔離開發環境、確保可重現性，並為部署階段提供基礎。

前置條件：
- Ubuntu 22.04+ 已安裝
- CUDA 12.1+ 已安裝
- NVIDIA Container Runtime 可用

## Solution

按照以下步驟準備 Docker 環境：

```bash
# 1. 安裝 Docker
sudo apt update
sudo apt install -y docker.io docker-compose-plugin

# 2. 啟動 Docker 服務
sudo systemctl start docker
sudo systemctl enable docker

# 3. 將使用者加入 docker 組（避免 sudo）
sudo usermod -aG docker $USER
newgrp docker

# 4. 驗證 Docker 安裝
docker --version
docker compose version

# 5. 安裝 NVIDIA Container Runtime（GPU 支援）
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update && sudo apt install -y nvidia-container-runtime

# 6. 配置 Docker daemon（支援 GPU）
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
EOF
sudo systemctl restart docker

# 7. 驗證 GPU 在 Docker 中可用
docker run --rm --gpus all nvidia/cuda:12.1.0-runtime-ubuntu22.04 nvidia-smi
```

驗收標準：
- ✅ `docker --version` 正常顯示版本
- ✅ `docker compose version` 正常顯示版本
- ✅ NVIDIA Container Runtime 已安裝
- ✅ Docker 容器可訪問 GPU（nvidia-smi 在容器內可執行）
- ✅ 當前使用者無需 sudo 執行 docker 命令

可交付成果：
- ✅ Docker base images 已下載（官方 Ubuntu 22.04、CUDA 12.1）
- ✅ docker-compose.yml 範例配置已建立
