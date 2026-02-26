---
created: 2026-02-26T09:21:32.449Z
title: uv 環境建置
area: tooling
files:
  - OpnusPlan.md:66-67
  - OpnusPlan.md:1220-1324
---

## Problem

需要安裝 uv (Python 依賴管理工具) 並準備專案的 Python 虛擬環境。符合使用者全域設定「使用 uv 進行版本控制」。此步驟完成後方可安裝專案依賴。

## Solution

按照以下步驟建置 uv 環境：

```bash
# 1. 安裝 uv（官方推薦方式）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 驗證安裝
uv --version

# 3. 建立虛擬環境
cd /home/hsu/Desktop/SoapVoice
uv venv

# 4. 激活虛擬環境
source .venv/bin/activate  # Linux/Mac

# 5. 建立或驗證 pyproject.toml（已在 OpnusPlan.md 中提供）
# 將 pyproject.toml 複製到專案根目錄

# 6. 同步專案依賴（生產環境）
uv sync

# 7. 同步開發依賴
uv sync --extra dev

# 8. 鎖定依賴版本
uv lock

# 9. 驗證環境
python --version  # 應顯示 Python 3.11+
pip list | head -5
```

驗收標準：
- ✅ `uv --version` 能正常執行
- ✅ 虛擬環境 `.venv/` 已建立
- ✅ `uv lock` 文件已生成（uv.lock）
- ✅ Python 3.11+ 環境就緒
- ✅ 核心依賴（torch, fastapi, transformers）可正常導入

相關檔案：
- OpnusPlan.md 第 8️⃣ 章節中包含完整 pyproject.toml 範例
