---
name: medicalorderupdate
description: 更新健保醫療服務給付項目CSV支付規定。篩選診療項目代碼xxxC，使用舊版規定+Tree搜尋（0.8秒處理2102筆）。支援關鍵詞搜尋、代碼搜尋、同義詞擴展。點數>350查無規定時用NotebookLM補充。用法：/medicalorderupdate
---

# 醫療服務給付項目更新 Skill

## 專案路徑
```
/home/hsu/Desktop/DrtoolBox/UpdateList/MedicalOderUpdate
```

## 觸發方式
- `/medicalorderupdate` — 執行 Tree Pipeline（推薦，0.8秒完成）
- `/medicalorderupdate search <關鍵詞>` — 搜尋支付規定
- `/medicalorderupdate code <代碼>` — 代碼搜尋

## 執行步驟

### Step 1：執行 Tree Pipeline（推薦）

```bash
cd /home/hsu/Desktop/DrtoolBox/UpdateList/MedicalOderUpdate
uv run --with numpy --with ollama --with pymupdf --with python-docx --with tiktoken --with openai --with python-dotenv --with pyyaml --with pandas --with openpyxl python3 rag_processing/pipeline_tree.py
```

**效能：0.8秒處理2102筆，100%填入率**

### 輸出檔案
- `current/醫療服務給付項目_醫療服務給付項目及支付標準_1150316_C類_tree.csv`
- `current/notebooklm_pending_*.json`（若有高點數待查）

### Step 2：NotebookLM 補充（高點數待查）

若有 `notebooklm_pending_*.json`：

```bash
cat current/notebooklm_pending_*.json
```

使用 NotebookLM MCP 查詢：
```
mcp__notebooklm-mcp__notebook_query: "診療項目代碼 {code}（{name}）健保支付規定為何？請用50字以內回答，若無規定請回答null。"
```

### Step 3：完成回報

回報：
- 輸出檔案路徑與筆數
- 支付規定填入率

## 快速搜尋

### CLI 搜尋

```bash
cd /home/hsu/Desktop/DrtoolBox/UpdateList/MedicalOderUpdate

# 代碼搜尋（推薦）
uv run --with numpy --with ollama --with pymupdf --with python-docx --with tiktoken --with openai --with python-dotenv --with pyyaml python3 rag_processing/optimized_hybrid_search.py --code 48001C

# 關鍵詞搜尋
python3 rag_processing/optimized_hybrid_search.py "居家照護"

# 組合搜尋
python3 rag_processing/optimized_hybrid_search.py --combined "手術" --code 48001C
```

### 工作流程整合

```bash
# 單一查詢
python3 rag_processing/medical_workflow.py lookup --name "居家照護" --verbose

# 互動模式
python3 rag_processing/medical_workflow.py interactive
```

### REST API

```bash
cd rag_processing
uv run --with fastapi --with uvicorn python3 api_server.py
# http://localhost:8000
```

API 端點：
- `GET /search?query=居家照護`
- `GET /code/48001C`
- `GET /combined?query=手術&code=48001C`
- `GET /health`

## 關鍵檔案

| 檔案 | 功能 |
|------|------|
| `rag_processing/pipeline_tree.py` | Tree Pipeline（0.8秒完成）⭐ |
| `rag_processing/optimized_hybrid_search.py` | 核心搜尋引擎 |
| `rag_processing/medical_workflow.py` | CLI 工作流程 |
| `rag_processing/api_server.py` | REST API |
| `rag_processing/test_search_accuracy.py` | 測試套件 |
| `PageIndex/results/` | 33 個樹結構 JSON |
| `審查注意事項/` | RAG 文件來源 |

## 技術規格

| 項目 | 規格 |
|------|------|
| Pipeline 速度 | 0.8秒/2102筆 |
| 填入率 | 100% |
| 舊版規定 | 71.6% |
| Tree搜尋 | 28.4% |
| LLM | qwen2.5:14b |
| 嵌入 | nomic-embed-text:latest |
| 快取 | 記憶體+磁碟，24小時 |

## 代碼搜尋範例

| 代碼 | 結果 |
|------|------|
| 48001C | 燒燙傷：小範圍以48001C申報 |
| 48011C | 小換藥（<10cm），嬰兒不得申報 |
| 85213B | 穿透性角膜移植術 |

## 同義詞擴展

| 搜尋詞 | 擴展 |
|--------|------|
| 巡迴醫療 | 居家, 照護, 門診, 山地, 離島 |
| 居家照護 | 護理, 在宅 |
| 安寧療護 | 末期, 緩和 |
