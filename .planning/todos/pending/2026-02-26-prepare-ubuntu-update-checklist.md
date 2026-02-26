---
created: 2026-02-26T09:21:32.449Z
title: 準備 Ubuntu 系統更新清單
area: tooling
files:
  - DailyProgress.md:145
  - OpnusPlan.md:1210-1224
---

## Problem

在進行 GPU 驅動和 CUDA 安裝前，需要準備完整的 Ubuntu 系統更新清單。系統應保持最新，以確保：
1. 安全漏洞已修補
2. 核心驅動程序最新
3. 系統庫版本兼容
4. 開發工具鏈完整

## Solution

按照以下步驟準備系統更新清單：

```bash
# 1. 檢查當前系統版本
lsb_release -a
uname -r

# 2. 列出可用更新（不直接安裝）
sudo apt update
sudo apt list --upgradable

# 3. 生成系統更新清單報告
sudo apt dist-upgrade --simulate > apt_upgradable_packages.txt
cat apt_upgradable_packages.txt

# 4. 檢查是否需要核心更新
apt search linux-image-generic | grep -i "^linux-image" | head -5

# 5. 檢查必要開發工具
sudo apt list --installed | grep -E "build-essential|git|curl|wget"

# 6. 建立更新前檢查清單
cat > pre_update_checklist.md << 'EOF'
# Ubuntu 系統更新前檢查清單

## 安全備份
- [ ] 已備份重要資料
- [ ] 已記錄當前系統設定

## 系統資訊
- OS: $(lsb_release -d | cut -f2)
- Kernel: $(uname -r)
- Available updates: $(apt list --upgradable 2>/dev/null | wc -l)

## 開發工具驗證
- [ ] build-essential 已安裝
- [ ] git 已安裝
- [ ] curl 已安裝
- [ ] python3 已安裝

## 更新計畫
- 預計更新包數: (由 apt list --upgradable 決定)
- 預估下載大小: (由 apt dist-upgrade --simulate 決定)
- 預估更新時間: 15-30 分鐘

## 更新後驗證
- [ ] 系統正常啟動
- [ ] 網路連線正常
- [ ] GPU 驅動仍可用
- [ ] 所有核心命令可執行
EOF
```

驗收標準：
- ✅ 已執行 `sudo apt update`
- ✅ 可用更新清單已記錄
- ✅ 核心版本信息已確認
- ✅ 必要開發工具（build-essential, git, curl）已檢查
- ✅ 更新前檢查清單已建立
- ✅ 備份計畫已確認

建議步驟：
1. 審查更新清單
2. 確認沒有會衝突的套件
3. 在更新前建立系統快照（如使用 LVM 或 btrfs）
4. 安排更新時間（避免關鍵任務期間）
