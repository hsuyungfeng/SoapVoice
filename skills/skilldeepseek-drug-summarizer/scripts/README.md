# Scripts 目錄 - 可執行腳本

台灣全民健保藥品資料庫季度更新的完整可執行腳本套件。

## 📋 腳本列表

### 主要工作流

| # | 腳本 | 功能 | 輸入 | 輸出 |
|---|------|------|------|------|
| **一鍵** | `00-run-all.sh` | 執行完整工作流 | 1150316.csv + 251215.csv | 260316.csv |
| 1 | `01-wash-new-drugs.py` | 清洗新藥CSV | 1150316.csv | 1150316.csv (覆蓋) |
| 2-3 | `02-merge-datasets.py` | 比較找新藥並合併 | 1150316.csv + 251215.csv | temp_merged.csv |
| 4 | `03-rewash-merged.py` | 第二次清洗 | temp_merged.csv | temp_merged.csv (覆蓋) |
| 5 | `04-deepseek-enrich.py` | DeepSeek豐富 | temp_merged.csv | cache/enrichment.csv |
| 6-7 | `05-finalize-260316.py` | 合併並保存 | enrichment.csv + temp_merged.csv | 260316.csv |

## 🚀 快速開始

### 選項 A: 一鍵執行 (推薦)
```bash
# 進入項目目錄
cd /home/hsu/Desktop/DrtoolBox/UpdateList/DrugUpdate

# 載入環境設定 (會詢問您的 DeepSeek API 密鑰)
source scripts/setup-env.sh

# 執行完整工作流
bash scripts/00-run-all.sh
```

**預期交互:**
```
🔧 環境設定工具
================================================================================

📝 需要輸入 DeepSeek API 密鑰

   如何取得密鑰:
   1. 訪問: https://platform.deepseek.com/api_keys
   2. 登入您的 DeepSeek 帳號
   3. 複製您的 API 密鑰 (格式: sk-xxxxxxxx)

   請貼上您的 DeepSeek API 密鑰: sk-xxxxxxxx (隱藏輸入)

   💾 是否保存到 .env 檔案? (y/n, 預設: n): n
```

### 選項 B: 逐步執行 (除錯時使用)
```bash
# 首先載入環境
source scripts/setup-env.sh

# 步驟 1: 清洗新藥
python3 scripts/01-wash-new-drugs.py

# 步驟 2-3: 比較並合併
python3 scripts/02-merge-datasets.py

# 步驟 4: 第二次清洗
python3 scripts/03-rewash-merged.py

# 步驟 5: DeepSeek豐富
python3 scripts/04-deepseek-enrich.py

# 步驟 6-7: 最終化
python3 scripts/05-finalize-260316.py
```

### 選項 C: 提前保存密鑰 (可選)
```bash
# 如果想省去每次輸入，可提前建立 .env 檔案
cp .env.example .env

# 編輯 .env，填入您的 API 密鑰
nano .env  # 或使用您喜歡的編輯器

# 設定權限 (只有您可讀)
chmod 600 .env

# 之後執行時就不需要重新輸入
source scripts/setup-env.sh
bash scripts/00-run-all.sh
```

## 📊 工作流程圖

```
┌─────────────────────────────────────────────────────────┐
│ 01-wash-new-drugs.py                                   │
│ 清洗 1150316.csv (支付價、過期、去重)                 │
│ 輸入: 221,836行 → 輸出: 12,124行                       │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│ 02-merge-datasets.py                                   │
│ 比較舊版251215，找新藥，合併資料集                    │
│ 新藥: 3,974個 → 合併後: 17,915行                      │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│ 03-rewash-merged.py                                    │
│ 第二次清洗合併檔 (移除過期藥品)                      │
│ 清洗後: 12,042行 (移除5,873個過期)                   │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│ 04-deepseek-enrich.py                                  │
│ 使用DeepSeek API生成給付規定 + AI-note               │
│ 已處理: 3,976行 | 成本: $7.95 | 失敗: 0              │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│ 05-finalize-260316.py                                  │
│ 合併豐富資料，帶YYMMDD日期標注保存                    │
│ 輸出: 藥品項查詢項目檔260316 AI 摘要...             │
│ AI覆蓋: 67% (8,067/12,042)                            │
└──────────────────┬──────────────────────────────────────┘
                   ↓
             ✅ 完成
```

## 🔧 依賴與環境

### Python 3.6+
```bash
python3 --version  # 確認版本
```

### 必要模塊 (應已包含)
- `csv` (標準庫)
- `sqlite3` (標準庫)
- `datetime` (標準庫)
- `requests` (用於API調用)

### 環境變數
```bash
# DeepSeek API密鑰 (必要)
export DEEPSEEK_API_KEY='sk-xxxxxxxx'

# 可選: 設定工作目錄
cd /home/hsu/Desktop/DrtoolBox/UpdateList/DrugUpdate
```

## 📝 使用示例

### 1. 執行完整工作流
```bash
cd /home/hsu/Desktop/DrtoolBox/UpdateList/DrugUpdate
export DEEPSEEK_API_KEY='sk-xxxxxxxx'
bash scripts/00-run-all.sh
```

**預期輸出:**
```
✓ 輸入檔案: 已找到
✓ API密鑰: 已設定

步驟 1/5: 清洗新藥CSV
✅ 清洗完成!
   原始行數: 221,836
   保留行數: 12,124
   移除行數: 209,712

步驟 2-3/5: 比較找新藥並合併
✅ 步驟 2-3 完成
   舊版: 13,941 行
   新藥: 3,974 行
   合併後: 17,915 行

... (步驟 4, 5, 6-7)

✅ 工作流完成!
   最終檔案: 藥品項查詢項目檔260316 AI  摘要支付價大於0.csv
   準備就緒: 可供臨床系統或政策分析使用
```

### 2. 逐步除錯
```bash
# 只執行清洗步驟
python3 scripts/01-wash-new-drugs.py

# 檢查臨時檔案
wc -l temp_merged_for_deepseek.csv

# 只執行豐富 (跳過前面步驟)
python3 scripts/04-deepseek-enrich.py
```

### 3. 監控進度
```bash
# 檢查快取狀態
ls -lh cache/drug_summaries.db

# 查看檢查點
ls -la cache/checkpoints/

# 檢查最終檔案
ls -lh 藥品項查詢項目檔*.csv
```

## ⚠️ 常見問題

### Q: "找不到 DEEPSEEK_API_KEY"
```bash
# 確認設定
echo $DEEPSEEK_API_KEY

# 如果為空，重新設定
export DEEPSEEK_API_KEY='sk-xxxxxxxx'
```

### Q: "找不到輸入檔案"
```bash
# 確認檔案位置
ls -la *.csv

# 確認檔案名完全相同 (包括空格)
# - 健保用藥品項查詢項目檔_1150316.csv
# - 藥品項查詢項目檔251215 AI  摘要支付價大於0.csv
```

### Q: "步驟5耗時過長"
```bash
# 正常情況下 10-20 分鐘
# 因為有 60 req/min 速率限制
# 不要中斷! 會自動從檢查點恢復
```

### Q: "中途中斷了怎麼辦"
```bash
# 重新執行相同腳本
# 會自動從檢查點恢復，不重複調用API
python3 scripts/04-deepseek-enrich.py
```

## 📊 預期結果

完整工作流的預期統計：

| 階段 | 行數 | 變化 | 備註 |
|------|------|------|------|
| 原始 1150316 | 221,836 | - | 初始資料 |
| 清洗 | 12,124 | -95% | 移除無效記錄 |
| 合併 | 17,915 | +3,974 | 添加新藥 |
| 再清洗 | 12,042 | -33% | 移除過期 |
| **最終** | **12,042** | **67%** | AI覆蓋率 |

## 🎯 輸出檔案

### 主要輸出
```
藥品項查詢項目檔260316 AI  摘要支付價大於0.csv
└─ 12,042 行藥品資料，67% AI-note覆蓋
```

### 中間檔案
```
cache/
├─ enrichment_new_drugs.csv  (DeepSeek結果)
├─ drug_summaries.db         (SQLite快取)
├─ checkpoints/              (進度恢復點)
└─ ...
```

### 暫存檔
```
temp_merged_for_deepseek.csv  (中間合併檔，可刪除)
```

## 🔒 安全建議

1. **API密鑰**: 不要提交到版本控制
   ```bash
   echo "DEEPSEEK_API_KEY" >> .gitignore
   ```

2. **檔案備份**: 執行前備份原始檔案
   ```bash
   cp 健保用藥品項查詢項目檔_1150316.csv 健保用藥品項查詢項目檔_1150316.backup.csv
   ```

3. **成本監控**: 設定成本上限防止超支
   ```python
   # 在 scripts/04-deepseek-enrich.py 中
   cost_limit=100  # $100上限
   ```

## 📞 故障排查

### 執行權限問題
```bash
# 賦予執行權限
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

### 編碼問題
```bash
# 確認檔案編碼 UTF-8 (無BOM)
file *.csv

# 轉換編碼 (如需要)
iconv -f GBK -t UTF-8 input.csv > output.csv
```

### 快取問題
```bash
# 清除快取（如需重新生成）
rm cache/drug_summaries.db
rm -rf cache/checkpoints/

# 再次執行腳本會重新生成
```

## 📞 聯絡與支援

- **完整文檔**: 見 `../deepseek-drug-summarizer/`
- **快取說明**: 見 `../cache/README.md`
- **項目指南**: 見 `../CLAUDE.md`

---

**準備狀態**: ✅ 生產就緒
**最後測試**: 2026-03-17 (3,976筆實際資料)
**下次預定**: 2026-06-16 (Q2季度更新)
