---
created: 2026-02-26T09:21:32.449Z
title: 開始 uv 和 Docker 安裝計畫
area: tooling
files:
  - DailyProgress.md:146
  - OpnusPlan.md:1304-1330
---

## Problem

需要規劃並開始安裝 uv (Python 依賴管理) 和 Docker (容器化環境)。這兩個工具是 Phase 0 的關鍵基礎設施，完成後方可：
1. 建立隔離的 Python 開發環境
2. 管理複雜的 AI/ML 依賴鏈
3. 確保環境可重現性
4. 為容器化部署做準備

本任務的目標是制定詳細的安裝計畫和時程表。

## Solution

按照以下步驟規劃和開始安裝：

### 階段 1: 安裝計畫審查（Day 1）

```bash
# 檢查當前系統狀態
echo "=== 系統就緒檢查 ===" > installation_plan.md
echo "日期: $(date)" >> installation_plan.md
echo "" >> installation_plan.md

# 驗證互聯網連線
ping -c 3 github.com >> installation_plan.md

# 檢查可用磁碟空間
df -h >> installation_plan.md

# 驗證 curl 和 wget 可用
which curl wget >> installation_plan.md
```

### 階段 2: 安裝 uv（Day 1 下午）

參考: OpnusPlan.md 第 8️⃣ 章節 - uv 安裝指令

```bash
# 官方推薦安裝方式
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
uv --version
```

### 階段 3: 安裝 Docker（Day 2）

參考: 本 todo 中的 "docker-environment-preparation" 相關文件

```bash
# 基礎 Docker 安裝
sudo apt install -y docker.io docker-compose-plugin

# 配置 GPU 支援
# (參考 OpnusPlan.md 第 10️⃣ 章節部署計畫)
```

### 階段 4: 環境驗證（Day 2 下午）

```bash
# 驗證 uv
uv --version
python3 --version

# 驗證 Docker
docker --version
docker compose version
docker run hello-world

# 驗證 GPU 支援
docker run --rm --gpus all nvidia/cuda:12.1.0-runtime-ubuntu22.04 nvidia-smi
```

驗收標準：
- ✅ uv 已安裝並可執行
- ✅ uv 版本信息正確
- ✅ Docker 已安裝並可執行
- ✅ Docker Compose 已安裝
- ✅ NVIDIA Container Runtime 已配置
- ✅ Docker 可訪問 GPU

時程表：
| 階段 | 任務 | 預估時間 | 負責人 |
|------|------|----------|--------|
| 1 | 安裝計畫審查 | 1h | DevOps |
| 2 | 安裝 uv | 30min | Backend Dev |
| 3 | 安裝 Docker | 1h | DevOps |
| 4 | 環境驗證 | 1h | QA |
| **總計** | | **3.5h** | |

相關檔案：
- OpnusPlan.md 第 5️⃣ 章節：時程與資源分配
- OpnusPlan.md 第 8️⃣ 章節：依賴關係與前置需求
- OpnusPlan.md 第 10️⃣ 章節：部署計畫
