---
name: deepseek-drug-summarizer
description: Use when generating drug summaries with DeepSeek API for NHI enrichment files, handling cost constraints and API limits
---

# DeepSeek Drug Summarizer Skill

## Overview

This skill guides building a `drug_summarizer.py` module that uses DeepSeek API to generate clinical summaries and reimbursement rules for Taiwan NHI drug datasets. It handles batching, caching, rate limiting, and incremental processing for 700k+ drug records with cost-awareness.

**Core principle:** Cost control first (cache before API), quality second (validate output), completion third (checkpoint recovery).

## When to Use

Use this skill when:
- Generating `給付規定` (reimbursement rules) or `AI-note` (clinical summaries) from drug dataset
- Processing 10k+ rows → need batching and rate limiting
- Working with DeepSeek API → cost constraints mandatory
- Handling partial/stale enrichment → decide update strategy first
- Need fault tolerance → checkpoints and caching non-negotiable

**Not for:** Single-drug lookups (use API directly) | Batch jobs <100 rows (simpler script OK)

## Architecture Pattern

**Three-stage pipeline:**

```
┌─────────────────────────────────────────────────────┐
│ STAGE 1: Load & Analyze                             │
│ - Load cleaned CSV (706k rows)                       │
│ - Count empty 給付規定 / AI-note fields              │
│ - Decide: regenerate all vs fill missing only       │
│ - Build prompt engineering context (ingredients)     │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│ STAGE 2: Generate with Cost Control                  │
│ - Check cache first (JSON/SQLite)                    │
│ - Only call DeepSeek if not cached                  │
│ - Batch API calls (5-10 per request if supported)   │
│ - Implement exponential backoff on rate limits       │
│ - Write checkpoints every 1k rows                   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│ STAGE 3: Merge & Validate                            │
│ - Use existing drug_enricher.py to merge results    │
│ - Validate 給付規定 vs AI-note distinctions         │
│ - Check for "無資訊" fallback usage                  │
└─────────────────────────────────────────────────────┘
```

## Critical Decisions Before Coding

**Make these decisions first—they determine the entire implementation:**

### 1. Update Strategy
- **OPTION A:** Regenerate all 給付規定 + AI-note (scorched earth)
  - Cost: Highest | Time: Longest | Quality: Uniform
  - Choose if: Current data is stale or low quality
- **OPTION B:** Fill missing values only (cost-aware)
  - Cost: Medium | Time: Medium | Quality: Mixed
  - Choose if: Recent data is good, only gaps need filling
- **OPTION C:** Selective refresh (hybrid)
  - Cost: Lower | Time: Shorter | Quality: Targeted
  - Choose if: Some rows are stale, others are fresh

**ACTION:** Write this decision in code as a parameter:
```python
def summarize_drugs(
    csv_path,
    update_mode="fill_missing",  # or "regenerate_all" or "selective"
    ...
):
```

### 2. Semantic Definition
Define the EXACT difference before writing prompts:

**給付規定** (Reimbursement Rules):
- Health insurance coverage conditions, restrictions, contraindications
- Example: "限用於經診斷確認為類風濕性關節炎患者" (Limited to RA patients confirmed by diagnosis)
- Source: Official NHI regulations, drug approval documents
- Length: 50-150 characters

**AI-note** (Clinical Summary):
- Drug mechanism, indications, common side effects, dosage guidance
- Example: "用於治療成人抑鬱症，初始劑量 20mg/日，最大 40mg/日。常見副作用：頭暈、失眠。" (Treatment for adult depression, initial 20mg/day...)
- Source: Clinical trials, medical literature, pharmacology
- Length: 100-300 characters

**Hardcode this distinction in your prompt template:**
```python
REIMBURSEMENT_PROMPT = """
Based on this drug info, provide NHI reimbursement coverage rules:
[Drug info]
Return ONLY the coverage conditions (50-150 chars), not clinical info.
"""

CLINICAL_PROMPT = """
Based on this drug info, provide clinical summary:
[Drug info]
Return indication + dosage + side effects (100-300 chars), not reimbursement rules.
"""
```

### 3. Cost Model
Estimate before starting:

```
706,555 drugs × API calls per drug × cost per call = total cost

Scenarios:
- All new calls: 706k × 1 call × $0.001 = $706
- With 30% cache hit: 494k × 1 call × $0.001 = $494
- Batch 10 drugs/call: 70.6k × 1 call × $0.005 = $353
- Batch + 30% cache: 49.4k × 1 call × $0.005 = $247
```

**Decision point:** At what cost do you stop? Set a circuit breaker:
```python
COST_LIMIT_USD = 300  # Abort if projected cost exceeds this
```

## Implementation Template

**File structure:**
```
drug_summarizer.py          # Main module
  - summarize_drugs()       # Entry point
  - DeepSeekAPIClient       # API wrapper with retry
  - DrugCache               # SQLite cache
  - ProgressCheckpoint      # Fault recovery
  - PromptBuilder           # Prompt engineering

cache/
  - drug_summaries.db       # SQLite cache
  - checkpoint_*.json       # Incremental checkpoints
```

### A. API Client with Rate Limiting

```python
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

class DeepSeekAPIClient:
    """Wrapper for DeepSeek API with exponential backoff and rate limiting."""

    def __init__(self, api_key: str, max_retries: int = 3, rpm_limit: int = 60):
        self.api_key = api_key
        self.max_retries = max_retries
        self.rpm_limit = rpm_limit  # Requests per minute
        self.request_times = []  # Track request times for rate limiting

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed RPM limit."""
        now = time.time()
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.rpm_limit:
            # Wait until oldest request leaves the window
            sleep_time = 60 - (now - self.request_times[0]) + 0.1
            print(f"Rate limit reached. Sleeping {sleep_time:.1f}s...")
            time.sleep(sleep_time)

    def call(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """
        Call DeepSeek API with exponential backoff.
        Returns: Generated text or None if all retries failed.
        """
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
                self.request_times.append(time.time())

                # ACTUAL API CALL HERE
                # response = client.messages.create(
                #     model="deepseek-chat",
                #     messages=[{"role": "user", "content": prompt}],
                #     max_tokens=max_tokens
                # )
                # return response.content[0].text

                # PLACEHOLDER FOR TESTING
                return f"Generated summary for prompt starting with: {prompt[:50]}..."

            except Exception as e:
                wait_time = 2 ** attempt  # Exponential: 1s, 2s, 4s
                if attempt < self.max_retries - 1:
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"All {self.max_retries} attempts failed for prompt: {prompt[:50]}...")
                    return None
```

### B. Cache Layer (SQLite)

```python
import sqlite3
import json
from pathlib import Path

class DrugCache:
    """SQLite cache for drug summaries to avoid re-calling API."""

    def __init__(self, db_path: str = "cache/drug_summaries.db"):
        Path(db_path).parent.mkdir(exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    drug_code TEXT PRIMARY KEY,
                    reimbursement_rules TEXT,
                    ai_note TEXT,
                    cached_at TIMESTAMP,
                    api_cost REAL
                )
            """)
            conn.commit()

    def get(self, drug_code: str) -> Optional[Dict]:
        """Retrieve cached summary for drug."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT reimbursement_rules, ai_note FROM summaries WHERE drug_code = ?",
                (drug_code,)
            ).fetchone()
        return {"給付規定": row[0], "AI-note": row[1]} if row else None

    def set(self, drug_code: str, reimbursement: str, ai_note: str, cost: float = 0):
        """Cache a summary."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO summaries
                (drug_code, reimbursement_rules, ai_note, cached_at, api_cost)
                VALUES (?, ?, ?, datetime('now'), ?)
            """, (drug_code, reimbursement, ai_note, cost))
            conn.commit()

    def stats(self) -> Dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(api_cost) FROM summaries"
            ).fetchone()
        return {"cached_drugs": row[0], "total_api_cost": row[1] or 0}
```

### C. Checkpoint for Fault Recovery

```python
import json
from pathlib import Path
from datetime import datetime

class ProgressCheckpoint:
    """Save progress every N rows for crash recovery."""

    def __init__(self, checkpoint_dir: str = "cache/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True, parents=True)

    def save(self, processed_rows: int, failed_count: int, total_cost: float):
        """Save checkpoint."""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "processed_rows": processed_rows,
            "failed_count": failed_count,
            "total_cost": total_cost
        }
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{processed_rows}.json"
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        print(f"✓ Checkpoint saved: {processed_rows} rows, ${total_cost:.2f}")

    def latest(self) -> Optional[Dict]:
        """Load latest checkpoint."""
        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.json"),
                           key=lambda x: int(x.stem.split('_')[1]), reverse=True)
        if not checkpoints:
            return None
        with open(checkpoints[0], 'r', encoding='utf-8') as f:
            return json.load(f)
```

### D. Main Entry Point

```python
import csv
from typing import List, Dict, Tuple

def summarize_drugs(
    csv_path: str,
    output_path: str = None,
    update_mode: str = "fill_missing",  # "fill_missing" | "regenerate_all" | "selective"
    cost_limit: float = 300,
    checkpoint_interval: int = 1000
) -> Dict:
    """
    Generate drug summaries using DeepSeek API.

    Args:
        csv_path: Path to cleaned drug CSV
        output_path: Where to save enrichment CSV (default: cache/enrichment.csv)
        update_mode: Strategy for which rows to generate
        cost_limit: Abort if projected cost exceeds this
        checkpoint_interval: Save progress every N rows

    Returns:
        Dictionary with results, costs, statistics
    """
    output_path = output_path or "cache/enrichment.csv"
    api_client = DeepSeekAPIClient()
    cache = DrugCache()
    checkpoint = ProgressCheckpoint()

    # Step 1: Load CSV and analyze
    print(f"Loading {csv_path}...")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Step 2: Determine rows to process based on update_mode
    rows_to_process = _filter_rows_by_mode(rows, update_mode)
    print(f"Processing {len(rows_to_process)} of {len(rows)} rows")

    # Step 3: Generate summaries
    enrichment_data = []
    total_cost = 0
    failed_count = 0

    for i, row in enumerate(rows_to_process, 1):
        drug_code = row.get('藥品代號', '').strip()

        # Check cache first
        cached = cache.get(drug_code)
        if cached:
            enrichment_data.append({
                '藥品代號': drug_code,
                '給付規定': cached['給付規定'],
                'AI-note': cached['AI-note']
            })
            continue

        # Call API
        prompt = _build_prompt(row)
        result = api_client.call(prompt)

        if result:
            reimbursement, ai_note = _parse_result(result)
            cache.set(drug_code, reimbursement, ai_note, cost=0.001)
            enrichment_data.append({
                '藥品代號': drug_code,
                '給付規定': reimbursement,
                'AI-note': ai_note
            })
            total_cost += 0.001
        else:
            enrichment_data.append({
                '藥品代號': drug_code,
                '給付規定': '無資訊',
                'AI-note': '無資訊'
            })
            failed_count += 1

        # Cost circuit breaker
        if total_cost > cost_limit:
            print(f"⚠ Cost limit ${cost_limit} exceeded. Stopping.")
            break

        # Checkpoint
        if i % checkpoint_interval == 0:
            checkpoint.save(i, failed_count, total_cost)
            print(f"Progress: {i}/{len(rows_to_process)} rows, ${total_cost:.2f}, {failed_count} failures")

    # Step 4: Save enrichment CSV
    _save_enrichment_csv(output_path, enrichment_data)

    return {
        'status': 'success',
        'rows_processed': len(enrichment_data),
        'rows_failed': failed_count,
        'total_cost': total_cost,
        'output_file': output_path,
        'cache_stats': cache.stats()
    }

def _filter_rows_by_mode(rows: List[Dict], mode: str) -> List[Dict]:
    """Filter rows based on update mode."""
    if mode == "regenerate_all":
        return rows
    elif mode == "fill_missing":
        return [r for r in rows if not r.get('給付規定', '').strip() or not r.get('AI-note', '').strip()]
    elif mode == "selective":
        # Fill if both missing, but keep existing if one present
        return [r for r in rows if not r.get('給付規定', '').strip() and not r.get('AI-note', '').strip()]
    return rows

def _build_prompt(row: Dict) -> str:
    """Build DeepSeek prompt from drug row."""
    drug_name = row.get('藥品中文名稱', '')
    ingredients = row.get('成分', '')
    dosage_form = row.get('劑型', '')
    atc_code = row.get('ATC代碼', '')

    return f"""
根據以下藥品資訊，請生成健保給付規定和臨床摘要：

藥品名稱: {drug_name}
成分: {ingredients}
劑型: {dosage_form}
ATC代碼: {atc_code}

請回覆JSON格式：
{{
  "給付規定": "[健保給付條件和限制，50-150字]",
  "AI-note": "[臨床摘要，包括適應症、用法用量、副作用，100-300字]"
}}
"""

def _parse_result(text: str) -> Tuple[str, str]:
    """Parse API response into reimbursement and AI-note."""
    try:
        import json
        data = json.loads(text)
        return data.get('給付規定', '無資訊'), data.get('AI-note', '無資訊')
    except:
        return '無資訊', '無資訊'

def _save_enrichment_csv(path: str, data: List[Dict]):
    """Save enrichment data to CSV."""
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['藥品代號', '給付規定', 'AI-note'])
        writer.writeheader()
        writer.writerows(data)
    print(f"✓ Saved enrichment to {path}")
```

## Common Mistakes

| Mistake | Why it Fails | Fix |
|---------|-------------|-----|
| **Call API first, cache after** | Wastes cost on duplicates | Check cache BEFORE every API call |
| **No rate limiting** | API blocks requests, crashes | Implement 60 RPM tracking with sleep |
| **No checkpoints** | Crash at row 500k = restart from 0 | Save every 1k rows, resume from checkpoint |
| **All-or-nothing updates** | Can't refresh stale data incrementally | Use `update_mode` parameter for strategy |
| **Hardcode cost model** | Can't adjust for API price changes | Pass cost estimate as parameter |
| **No distinction 給付規定 vs AI-note** | Generator produces wrong content | Define semantics in system prompt |
| **Process all 706k rows at once** | Out of memory, slow feedback | Batch in 10k-row chunks with progress |
| **Ignore API errors silently** | Data gaps without visibility | Track failures, log to CSV, report counts |

## Cost Control Strategy

**Always apply in this order:**

1. **Cache first** (100% cost savings)
   - Check SQLite before any API call
   - Resume from checkpoints

2. **Batch API calls** (5-10x savings if supported)
   - Send 5-10 drugs per request
   - Adjust `max_tokens` proportionally

3. **Selective updates** (2-3x savings)
   - Use `update_mode="fill_missing"` by default
   - Only regenerate if data quality is bad

4. **Cost circuit breaker** (prevent runaway bills)
   - Set `cost_limit` based on budget
   - Stop immediately if exceeded

5. **Monitor and adjust**
   - Check cache hit rate (`cache.stats()`)
   - Recalculate cost every 1k rows
   - Report actual vs projected cost

## Integration with Existing Pipeline

After generating enrichment CSV, merge with `drug_enricher.py`:

```python
from drug_enricher import enrich_drug_data

result = enrich_drug_data(
    cleaned_filepath="cleaned_drugs.csv",
    enrichment_filepath="cache/enrichment.csv",  # Generated by this skill
    output_filepath="final_enriched_drugs.csv"
)
```

This handles left join, missing value filling, and deduplication automatically.

## Testing Checklist

- [ ] Cache returns correct data for repeated calls
- [ ] API client respects rate limits (no 429 errors)
- [ ] Checkpoint saves and resumes correctly
- [ ] Cost estimate is within 10% of actual
- [ ] Output CSV merges cleanly with drug_enricher.py
- [ ] 給付規定 and AI-note are semantically distinct
- [ ] Failed rows filled with "無資訊" (not empty)
- [ ] UTF-8 encoding preserved throughout
- [ ] Cost limit triggers before first request fails
