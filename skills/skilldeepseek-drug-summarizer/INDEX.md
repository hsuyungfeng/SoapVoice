# DeepSeek Drug Summarizer 文檔索引

台灣全民健保藥品資料庫季度更新工作流的完整技能文檔套件。

## 📚 文檔結構

### 1. **SKILL.md** (2,069字) - 核心技能文檔
完整的DeepSeek藥品摘要生成技能，包含：
- 類別設計與實作詳解
- API整合 (費率限制、指數退避)
- SQLite快取系統
- 檢查點與故障恢復
- 語義定義 (給付規定 vs AI-note)
- 完整Python實作代碼

**適合:** 從零開始實現或修改系統

### 2. **QUICK-START.md** (500字) - 快速參考
核心概念速查表，包含：
- TL;DR摘要
- 3個關鍵決策點
- 4個非協商模式
- 函數簽名
- 常見錯誤表
- 測試檢查清單
- 完整工作流命令

**適合:** 熟悉系統的開發者快速查閱

### 3. **WORKFLOW.md** (2,500字) - 端到端工作流
季度更新的完整流程文檔，包含：
- 7步驟視覺化流程圖
- 每步驟詳細說明
- 關鍵參數表
- 可執行Python代碼範例
- 快取策略與成本計算
- 常見問題解答
- 故障恢復機制
- 效能指標

**適合:** 執行季度更新或培訓新員工

---

## 🚀 使用場景

### 初次實現 → 讀 SKILL.md
```
學習 DeepSeekAPIClient、DrugCache、ProgressCheckpoint 等類別
→ 理解 API 整合與快取策略
→ 實作 drug_summarizer.py
```

### 季度更新執行 → 讀 WORKFLOW.md
```
參照 7步驟流程
→ 複製可執行代碼
→ 執行完整工作流
→ 驗證輸出品質
```

### 快速查閱 → 讀 QUICK-START.md
```
快速查看 3個關鍵決策
→ 檢視函數簽名
→ 確認測試檢查清單
→ 參照完整工作流命令
```

---

## 📊 2026年Q1 實際結果

| 階段 | 輸入 | 輸出 | 備註 |
|------|------|------|------|
| 清洗新藥 | 221,836 | 12,124 | 95%過濾無效記錄 |
| 合併舊資料 | 13,941 | 17,915 | +3,974新藥 |
| 再清洗 | 17,915 | 12,042 | -5,873過期藥證 |
| DeepSeek豐富 | 3,976 | 3,976 | 0失敗, $7.95成本 |
| **最終輸出** | - | **12,042** | **67%覆蓋率** |

### 成本統計
- **DeepSeek API調用**: 7,952次
- **總成本**: $7.95 (0.001/次)
- **快取節省**: 3,977藥品 (後續季度)
- **執行時間**: ~15分鐘 (含速率限制)

---

## 🔑 快速導航

### 我想...

**...從零開始實現藥品豐富系統**
→ 讀 [SKILL.md](./SKILL.md) 的實作部分

**...執行季度藥品資料庫更新**
→ 讀 [WORKFLOW.md](./WORKFLOW.md) 的 7步驟流程

**...快速查看API函數簽名**
→ 讀 [QUICK-START.md](./QUICK-START.md) 的函數簽名章節

**...理解成本控制策略**
→ 讀 [WORKFLOW.md](./WORKFLOW.md) 的快取策略部分

**...解決故障或恢復進度**
→ 讀 [WORKFLOW.md](./WORKFLOW.md) 的故障恢復章節

**...檢查 SQLite 快取狀態**
→ 執行 `cache/README.md` 的快取檢查命令

**...了解 ROC 日期邏輯**
→ 讀 [QUICK-START.md](./QUICK-START.md) 或 [WORKFLOW.md](./WORKFLOW.md) 的日期參數章節

---

## ⚙️ 技術棧

### 核心依賴
- `csv` (Python 標準庫)
- `sqlite3` (Python 標準庫)
- `requests` (HTTP API調用)
- `datetime` (日期處理)
- `json` (API回應解析)

### 外部服務
- **DeepSeek API** (藥品摘要生成)
- **速率限制**: 60 req/min
- **費用模型**: $0.001 per API call

### 本地檔案系統
- `cache/drug_summaries.db` - SQLite快取 (~5MB)
- `cache/enrichment_*.csv` - 豐富結果
- `cache/checkpoints/` - 進度恢復點

---

## 📋 檔案清單

```
deepseek-drug-summarizer/
├── SKILL.md              # ← 核心技能文檔 (2,069字)
├── QUICK-START.md        # ← 快速參考 (500字)
├── WORKFLOW.md           # ← 工作流程 (2,500字)
├── INDEX.md              # ← 本文件 (導航)
└── 實作檔案
    ├── drug_summarizer.py           # 模塊實現 (690行)
    ├── test_drug_summarizer.py      # 測試 (30個單元測試)
    ├── finalize_260316.py           # 最終化腳本
    └── run_deepseek_enrichment.py   # 完整工作流編排
```

---

## 🎓 學習路徑

### 路徑A: 完整系統學習
1. 讀 QUICK-START.md (10分鐘) - 掌握概念
2. 讀 SKILL.md (30分鐘) - 深入實作細節
3. 閱讀 `drug_summarizer.py` (20分鐘) - 查看實際代碼
4. 執行 `test_drug_summarizer.py` (5分鐘) - 驗證理解

### 路徑B: 快速執行工作流
1. 讀 WORKFLOW.md (20分鐘) - 理解 7步驟
2. 複製可執行代碼 (10分鐘) - 準備腳本
3. 執行完整流程 (15分鐘) - 執行更新
4. 驗證輸出品質 (5分鐘) - 檢查結果

### 路徑C: 快速查閱
1. 讀 QUICK-START.md (10分鐘)
2. 需要時參照其他文檔

---

## 💡 常見問題

**Q: 三份文檔有什麼區別？**
A:
- SKILL.md = 完整教材 (給實現者)
- QUICK-START.md = 速查表 (給經驗者)
- WORKFLOW.md = 執行指南 (給使用者)

**Q: 應該從哪份文檔開始？**
A: 根據您的角色：
- 首次實現 → SKILL.md
- 執行季度更新 → WORKFLOW.md
- 快速查閱 → QUICK-START.md

**Q: 代碼在哪裡？**
A:
- SKILL.md 包含核心類別的完整代碼
- QUICK-START.md 包含使用示例
- WORKFLOW.md 包含可直接執行的腳本
- `drug_summarizer.py` 是實際實現 (690行)

**Q: 如何追蹤版本？**
A: 所有輸出檔案自動帶 YYMMDD 日期標注：
```
藥品項查詢項目檔260316 AI 摘要支付價大於0.csv
```
260316 = 2026年3月16日，每季度自動更新

---

## 🔗 相關文檔

- **項目指南**: `../CLAUDE.md`
- **快取說明**: `../cache/README.md`
- **測試覆蓋**: `../test_drug_summarizer.py`
- **全局技能**: `/home/hsu/.claude/skills/deepseek-drug-summarizer/`

---

## ✅ 生產就緒狀態

- ✅ 核心模塊: `drug_summarizer.py` (690行)
- ✅ 測試覆蓋: 30個單元測試 (100%通過)
- ✅ E2E驗證: 3,976筆實際資料
- ✅ 文檔完整: 3份文檔 (5,069字)
- ✅ 成本控制: SQLite快取 + 電路斷路器
- ✅ 故障恢復: 檢查點系統
- ✅ 日期追蹤: 自動版本戳記

---

**最後更新**: 2026-03-17
**狀態**: ✅ 生產就緒
**下次季度**: 2026-06-16 (Q2)
