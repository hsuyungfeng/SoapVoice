---
created: 2026-02-26T09:21:32.449Z
title: Git Repository 初始化與設定
area: tooling
files:
  - OpnusPlan.md:67
  - DailyProgress.md:250-256
---

## Problem

需要初始化 Git repository 並建立初始提交，納入 OpnusPlan.md、DailyProgress.md 和 clinic-promot.md。此步驟確保：
1. 專案版本控制就緒
2. 建立清晰的開發分支策略
3. 為後續開發提供版本管理基礎

## Solution

按照以下步驟初始化 Git 並建立初始提交：

```bash
cd /home/hsu/Desktop/SoapVoice

# 1. 檢查 Git 狀態
git status

# 2. 建立 .gitignore 檔案（排除不必要的文件）
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
.venv/
venv/
.uv-cache/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# 模型和資料
*.bin
*.safetensors
models/
data/
*.db

# 系統檔案
.DS_Store
*.log
.env
.env.local
EOF

# 3. 建立初始 commit
git add OpnusPlan.md DailyProgress.md clinic-promot.md .gitignore

git commit -m "docs: add project planning and technical specification

- Add OpnusPlan.md: comprehensive 16-week development plan with 11 chapters
- Add DailyProgress.md: daily/weekly progress tracking system
- Include clinic-promot.md: core technical specifications and medical terminology
- Configure .gitignore for Python, IDE, and sensitive data

Co-Authored-By: Claude Code <noreply@anthropic.com>"

# 4. 建立開發分支策略
git branch develop
git branch feature/phase0-setup

# 5. 驗證
git log --oneline
git branch -a
```

驗收標準：
- ✅ Git repository 已初始化（.git/ 目錄存在）
- ✅ .gitignore 已建立並包含必要規則
- ✅ 初始 commit 已建立，包含三份核心文件
- ✅ 分支結構已建立（main, develop, feature/*）
- ✅ `git log` 能顯示 commit history

相關檔案：
- OpnusPlan.md: 5000+ 行，11 章節的專案執行計畫
- DailyProgress.md: 475 行，每日進度追蹤框架
- clinic-promot.md: 737 行，核心技術規格
