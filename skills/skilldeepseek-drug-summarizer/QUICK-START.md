# DeepSeek Drug Summarizer - Quick Start

## TL;DR

Use this skill when generating NHI drug summaries with DeepSeek API for enrichment (給付規定 + AI-note fields).

**File location:** `/home/hsu/.claude/skills/deepseek-drug-summarizer/SKILL.md`

## What Gets Built

A `drug_summarizer.py` module that:
- Generates clinical summaries for 706k+ drugs using DeepSeek API
- Caches results in SQLite to avoid re-calling API (cost control)
- Saves checkpoints every 1k rows for crash recovery
- Enforces rate limits (60 req/min) and exponential backoff
- Circuit breaker stops if cost exceeds limit

## Before You Code

Make these 3 decisions:

### 1. Update Mode (impacts cost)
```python
summarize_drugs(..., update_mode="fill_missing")  # Default: only fill empty cells
# OR
summarize_drugs(..., update_mode="regenerate_all")  # Regenerate everything (highest cost)
# OR
summarize_drugs(..., update_mode="selective")  # Fill when both fields missing
```

### 2. Cost Limit (prevent runaway bills)
```python
summarize_drugs(..., cost_limit=300)  # Default: stop at $300
```

### 3. Semantic Definition (non-negotiable)
- **給付規定** (50-150 chars): Health insurance coverage conditions ONLY
  - Example: "限用於經診斷確認為類風濕性關節炎患者"
- **AI-note** (100-300 chars): Clinical info ONLY
  - Example: "用於治療成人抑鬱症，初始劑量 20mg/日，副作用為頭暈"

Hardcode these in your prompt templates before coding.

## Implementation Overview

**4 Classes:**
1. `DeepSeekAPIClient` - API calls with rate limiting + exponential backoff
2. `DrugCache` - SQLite cache (avoid re-calling API)
3. `ProgressCheckpoint` - Save/resume progress every 1k rows
4. Main function: `summarize_drugs()` - Orchestrate pipeline

**4 Helpers:**
- `_filter_rows_by_mode()` - Select rows based on update strategy
- `_build_prompt()` - Create prompt from drug info
- `_parse_result()` - Extract JSON from API response
- `_save_enrichment_csv()` - Write enrichment file

**2 Directories:**
- `cache/drug_summaries.db` - SQLite cache
- `cache/checkpoints/` - Recovery checkpoints

## Non-Negotiable Patterns

### Cache-First (Cost Control)
```python
# ALWAYS check cache BEFORE calling API
cached = cache.get(drug_code)
if cached:
    enrichment_data.append(cached)
    continue
# Only call API if not cached
result = api_client.call(prompt)
```

### Rate Limiting (60 req/min)
```python
def _wait_for_rate_limit(self):
    # Remove requests older than 60s
    self.request_times = [t for t in self.request_times if now - t < 60]

    # If limit reached, sleep
    if len(self.request_times) >= self.rpm_limit:
        sleep_time = 60 - (now - self.request_times[0]) + 0.1
        time.sleep(sleep_time)
```

### Cost Circuit Breaker
```python
total_cost = 0
for row in rows:
    # ... process ...
    total_cost += 0.001
    if total_cost > cost_limit:
        print(f"⚠ Cost limit ${cost_limit} exceeded. Stopping.")
        break
```

### Checkpoint Every 1k Rows
```python
if i % checkpoint_interval == 0:
    checkpoint.save(i, failed_count, total_cost)
    print(f"Progress: {i}/{total} rows, ${total_cost:.2f}")
```

## Function Signatures

```python
# Main entry point
summarize_drugs(
    csv_path: str,
    output_path: str = None,  # Default: "cache/enrichment.csv"
    update_mode: str = "fill_missing",  # "fill_missing", "regenerate_all", "selective"
    cost_limit: float = 300,  # Stop at this USD amount
    checkpoint_interval: int = 1000  # Save every N rows
) -> Dict

# API Client
class DeepSeekAPIClient:
    def __init__(self, api_key: str, max_retries: int = 3, rpm_limit: int = 60)
    def call(self, prompt: str, max_tokens: int = 500) -> Optional[str]

# Cache
class DrugCache:
    def get(self, drug_code: str) -> Optional[Dict]
    def set(self, drug_code: str, reimbursement: str, ai_note: str, cost: float = 0)
    def stats(self) -> Dict

# Checkpoint
class ProgressCheckpoint:
    def save(self, processed_rows: int, failed_count: int, total_cost: float)
    def latest(self) -> Optional[Dict]
```

## Common Mistakes (Don't Do These)

| ❌ Mistake | ✅ Fix |
|-----------|-------|
| Call API before cache check | Always check cache FIRST |
| No rate limiting | Implement 60 RPM with sleep |
| No checkpoints | Save every 1k rows |
| Mix 給付規定 and AI-note | Define semantics in prompt |
| Process all 706k at once | Batch with checkpoints |
| Hardcode cost model | Use parameter |
| Ignore API errors | Fill with "無資訊" and continue |

## After You Build

1. Generate enrichment CSV:
   ```python
   result = summarize_drugs("cleaned.csv", cost_limit=300)
   # Output: cache/enrichment.csv
   ```

2. Merge with cleaned data:
   ```python
   from drug_enricher import enrich_drug_data

   result = enrich_drug_data(
       cleaned_filepath="cleaned_drugs.csv",
       enrichment_filepath="cache/enrichment.csv",
       output_filepath="final_enriched_drugs.csv"
   )
   ```

3. Done! Final CSV is ready for use.

## Testing Checklist

- [ ] Cache returns correct data for repeated calls
- [ ] API respects 60 req/min rate limit
- [ ] Checkpoint saves and resumes correctly
- [ ] Cost circuit breaker triggers before overflow
- [ ] Output CSV merges with drug_enricher.py
- [ ] 給付規定 ≠ AI-note (semantically distinct)
- [ ] Failures filled with "無資訊" (not empty)
- [ ] UTF-8 encoding preserved throughout

## 完整工作流 (Full Workflow)

季度藥品資料庫更新的端到端流程：

```bash
# 步驟 1-4: 清洗、合併、再清洗
python3 << 'EOF'
from drug_cleaner import clean_drug_data
import csv

# 清洗新藥
result = clean_drug_data("健保用藥品項查詢項目檔_1150316.csv", today_roc_year=114)
# 合併舊資料 + 再清洗
# (詳見 WORKFLOW.md 步驟 1-4)
EOF

# 步驟 5: DeepSeek豐富
python3 << 'EOF'
from drug_summarizer import summarize_drugs

result = summarize_drugs(
    csv_path="temp_merged_for_deepseek.csv",
    output_path="cache/enrichment_new_drugs.csv",
    update_mode="fill_missing",
    cost_limit=100,
    checkpoint_interval=1000
)

print(f"✓ 已處理: {result['rows_processed']} 行")
print(f"✓ 成本: ${result['total_cost']:.2f}")
EOF

# 步驟 6-7: 合併並帶日期標注保存
python3 finalize_260316.py
```

**預期結果:**
- 輸入: 17,915 行 (合併後)
- 清洗後: 12,042 行 (移除過期)
- AI覆蓋: 67% (8,067/12,042)
- 成本: ~$8 (含快取)
- 輸出: `藥品項查詢項目檔260316 AI 摘要支付價大於0.csv`

完整文檔見: **WORKFLOW.md**

## 快取與成本 (Caching & Cost)

### SQLite快取位置
```
cache/drug_summaries.db
├── 快取藥品數: 3,977 個
├── 快取大小: ~5MB
└── 成本節省: 後續季度 -75-90%
```

### 成本計算
- 新藥品: 3,976 個
- 每藥品API調用: 2 次 (給付規定 + AI-note)
- 單次成本: $0.001
- **總成本: $7.95** (實際調用 7,952 次)

### 快取命中優化
| 季度 | 新藥品 | API調用 | 成本 |
|------|--------|--------|------|
| Q1 | 3,976 | 7,952 | $7.95 |
| Q2 | 500 | 1,000 | $1.00 |
| Q3 | 600 | 1,200 | $1.20 |
| Q4 | 400 | 800 | $0.80 |
| **年合計** | 5,476 | 10,952 | **$11.00** |

## 關鍵日期參數 (ROC Calendar)

```python
# ROC年份轉換
ROC_year = 114          # 2025年 (Gregorian = ROC + 1911)
gregorian_year = 114 + 1911  # 2025

# 5年窗口檢驗
valid_start_year_min = 114 - 5  # 109年 (2020年)
valid_start_year_max = 114      # 114年 (2025年)

# 永久藥證檢驗
PERMANENT_END_DATE = "9991231"  # 有效迄日必須是此值

# 支付價檢驗
min_payment_price = 0  # 允許零價藥品
```

## 檔案版本追蹤 (Version Tracking)

所有輸出自動帶 **YYMMDD 日期戳記**：

```
藥品項查詢項目檔260316 AI  摘要支付價大於0.csv
                    ↑↑↑↑↑↑
              日期戳記 (2026-03-16)

每季度自動更新日期，確保版本清晰可追蹤
```

## References

**工作流完整文檔:** `WORKFLOW.md` (2,500字，含可執行代碼)

**技能完整內容:** `/home/hsu/.claude/skills/deepseek-drug-summarizer/SKILL.md`

**項目指南:** `/home/hsu/Desktop/DrtoolBox/UpdateList/DrugUpdate/CLAUDE.md`

**測試覆蓋:** `test_drug_summarizer.py` (30 個單元測試, 100% 通過)

**快取說明:** `cache/README.md` (快速參考 + 故障排查)
