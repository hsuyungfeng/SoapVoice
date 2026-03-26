# 📋 SoapVoice 每日計畫與待辦事項

**專案名稱:** SoapVoice - Medical Voice-to-SOAP System  
**建立日期:** 2026-03-19  
**當前階段:** 🟢 Phase 1 ✅ 完成，Phase 2 ✅ 完成，Phase 3 ✅ 完成，Phase 4 ✅ 完成，Phase 5 ✅ 完成，Phase 6 ✅ 完成（前端網頁整合）
**測試狀態:** 105/105 通過 ✅  
**最後更新:** 2026-03-24  

---

## 📅 2026-03-23 — 今日完成

### Phase 4: CLI 修復與檔案整理 ✅ 完成

### Phase 5: RAG 系統建立 ✅ 完成

| 項目 | 狀態 | 說明 |
|------|------|------|
| RAG 系統 | ✅ | 1,665 個病例範本區塊 |
| Chroma 向量資料庫 | ✅ | 支援語義搜尋 |
| medical.db 同步 | ✅ | case_templates 表 1,665 筆 |
| SOAP 整合 | ✅ | RAG 結果加入 LLM Prompt |
| 完整 Pipeline 測試 | ✅ | 術語+ICD-10+RAG+SOAP |
| 檔案清理 | ✅ | 節省 300+ MB |

### Phase 6: 前端網頁整合 ✅ 完成

| 項目 | 狀態 | 說明 |
|------|------|------|
| 靜態網頁 | ✅ | static/index.html |
| 麥克風錄音 | ✅ | MediaRecorder API |
| 語音轉譯 | ✅ | Whisper medium 模型 |
| SOAP 生成 | ✅ | Extended API 整合 |
| 模型選擇 | ✅ | qwen2.5:14b/7b/3b |
| 處理時間顯示 | ✅ | ASR + LLM 時間 |
| 測試音檔 | ✅ | 8 個場景測試檔案 |

---

## ✅ 已完成項目歷程

### 2026-03-21

#### Phase 3.7: 策略調整 ✅

- [x] 從 Ollama 轉向 llama.cpp + HuggingFace
- [x] qwen2.5:7b 測試成功（~3.5s SOAP 生成）
- [x] qwen2.5:3b 測試成功（~3s SOAP 生成）
- [x] 更新 `SoapvoiceToApiPlan.md`（新版架構）

#### Phase 3.6: NotebookLM 研究 ✅

- [x] 新增 12 個相關來源
- [x] 生成研究摘要（哈佛研究、台灣趨勢、SOAP 最佳實踐）
- [x] NotebookLM Notebook 更新至 22 個來源
- [x] 更新 `docs/OPEN_SOURCE_MODELS_REPORT.md`

#### Phase 3.5: 模型測試 ✅

- [x] qwen3.5:9b 測試（CUDA 錯誤）
- [x] qwen2.5:7b 測試（✅ 優秀）
- [x] qwen2.5:3b 測試（✅ 良好）
- [x] llama3:8b 測試（⚠️ 英文為主）

#### Phase 3: LLM 部署 ✅ 完成

- ✅ 建立 `src/llm/llama_engine.py` — LlamaEngine 類別（330 行）
- ✅ 建立 `src/llm/doctor_consultation.py` — DoctorConsultationClient（300 行）
- ✅ 建立 `src/llm/dual_engine.py` — DualLLMEngine（250 行）
- ✅ 更新 `Dockerfile` — 多階段建置
- ✅ 更新 `docker-compose.yml` — 開發環境
- ✅ 更新 `docker-compose.prod.yml` — 生產環境
- ✅ 更新 `.env.example` — 完整配置

### 2026-03-21 上午

#### Phase 2: 看診流程 ✅ 完成

- ✅ 建立 `src/consultation/` 模組（4 個檔案，1,500+ 行）
- ✅ 建立 `src/api/consultation_api.py`（400+ 行）
- ✅ 更新 `src/main.py` — 註冊 consultation router

#### Phase 1: 本地資料庫 ✅ 完成

- ✅ 建立 `src/db/` 模組（5 個檔案，1,200+ 行）
- ✅ 初始化資料庫（66.32 MB）

### 2026-03-19

- ✅ 建立 AGENTS.md
- ✅ 更新預設模型 qwen3.5:35b → qwen3.5:9b
- ✅ 實作語音與逐字稿自動儲存功能
- ✅ 實作 CLI 互動介面

---

## 📝 Phase 3 使用方式

### 雙軌 LLM 配置（新方向）

```python
from src.llm import DualLLMEngine, DualLLMConfig, LLMPriority, LlamaConfig, DoctorConsultationConfig

# 配置雙軌引擎（使用 llama.cpp + HuggingFace GGUF）
config = DualLLMConfig(
    priority=LLMPriority.LOCAL_FIRST,
    local_config=LlamaConfig(
        model_path="models/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        n_gpu_layers=35,
    ),
    cloud_config=DoctorConsultationConfig(
        api_key="your-api-key",
    ),
)

# 使用雙軌引擎
engine = DualLLMEngine(config)
engine.initialize()

# 自動選擇最佳 LLM
result = engine.generate_soap(
    transcript="病人咳嗽兩天...",
    patient_context={"age": 45},
)
```

### 模型下載（HuggingFace）

```bash
# Qwen2.5-7B GGUF（主要模型）
mkdir -p models/
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF Qwen2.5-7B-Instruct-Q4_K_M.gguf --local-dir models/

# 或使用 python 下載
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-7B-Instruct-GGUF', filename='Qwen2.5-7B-Instruct-Q4_K_M.gguf', local_dir='models/')"
```

### Docker 啟動

```bash
# 開發環境
docker-compose up -d

# 生產環境（需要 GPU）
docker-compose -f docker-compose.prod.yml up -d

# 查看日誌
docker-compose logs -f api
```

---

## ⏳ 待完成項目

### 2026-03-23 計畫

| 項目 | 說明 | 優先級 |
|------|------|--------|
| **Whisper CLI 整合** | 使用 openai-whisper skill | 🔴 P0 |
| **Moonshine ASR 整合** | 輕量快速 ASR 備用方案 | 🟡 P1 |
| **HuggingFace 模型下載** | 下載 Qwen2.5-7B GGUF | 🔴 P0 |
| **LlamaEngine 實際測試** | 用 llama.cpp 跑 SOAP 生成 | 🔴 P0 |
| **Windows 啟動腳本** | batch 腳本 | 🟡 P1 |
| **效能壓力測試** | 比較不同模型/量化 | 🟡 P1 |

### Whisper CLI 整合步驟

```bash
# 1. 安裝 Whisper CLI
pip install openai-whisper

# 2. 下載模型
whisper --model medium

# 3. 測試轉譯
whisper audio.wav --language Chinese --model medium
```

### 模型測試腳本

```python
# tests/test_llm_models.py

from src.llm import LlamaEngine, LlamaConfig

def test_qwen2_5_7b_soap_generation():
    """測試 Qwen2.5-7B SOAP 生成"""
    config = LlamaConfig(
        model_path="models/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        n_gpu_layers=35,
    )
    engine = LlamaEngine(config)
    
    prompt = """請將以下醫療對話轉換為 SOAP 病歷：
    
    醫師：你好，請問今天有什麼不舒服？
    病人：我咳嗽兩天了，有痰，喉嚨痛。
    """
    
    result = engine.generate(prompt)
    assert "S - 主觀資料" in result
    assert "O - 客觀資料" in result
    assert "A - 評估分析" in result
    assert "P - 計劃" in result
```

**最後更新:** 2026-03-24  
**下次更新:** 待續

---

## 📅 2026-03-24 — 今日完成

### Phase 5: RAG 系統建立與病例範本同步 ✅

#### 1. Git 推送與 Git LFS 設定 ✅

| 項目 | 說明 |
|------|------|
| 問題 | GitHub 檔案大小限制（50MB 推薦，100MB 上限）|
| 解決 | 使用 `git filter-repo` 清理歷史記錄 + Git LFS 追蹤 `.db`/`.pdf` |
| 結果 | 成功推送 medical.db（70 MB via LFS）|

#### 2. 病例範本補充腳本 ✅

- 建立 `src/db/supplement_case_templates.py`（180 行）
- 支援 `.txt`, `.doc`, `.docx` 檔案格式
- 發現 748 個病例範本檔案（大部分 .doc 格式無法讀取）

#### 3. RAG 系統建立 ✅

**安裝套件：**
```bash
uv add chromadb sentence-transformers
```

**建立模組：**
- `src/rag/case_template_rag.py` - RAG 系統主程式
- `src/rag/__init__.py` - 模組初始化

**功能：**
- Chroma 向量資料庫（支援語義搜尋）
- Sentence-transformers 嵌入模型
- 文字分塊（500 字元區塊，50 字元重疊）
- SQLite 備份匯出

**命令列工具：**
```bash
# 初始化
uv run python -m src.rag.case_template_rag init --template-dir "CurrentData/各种病例规范模板/" --clear

# 搜尋
uv run python -m src.rag.case_template_rag search --query "冠心病 胸悶" --top-k 5

# 統計
uv run python -m src.rag.case_template_rag stats
```

#### 4. LibreOffice .doc 轉 .txt ✅

**問題：** 742 個 `.doc` 檔案無法用 python-docx 讀取

**解決：** 使用 LibreOffice 命令列轉換
```bash
libreoffice --headless --convert-to txt "*.doc"
```

**結果：** 成功轉換所有 `.doc` → `.txt`

#### 5. RAG 數據同步到 medical.db ✅

**同步結果：**
```
RAG 向量資料庫：1,665 個區塊
medical.db case_templates：1,665 筆

專科分佈：
- 一般: 1,073
- 胃腸疾病病例: 258
- 冠心病病例: 169
- 糖尿病病例: 91
- 肺炎病例: 57
- 肺癌病例: 13
- 慢阻肺病例: 4
```

**medical.db 最新內容：**
```
icd10_codes:     96,802 筆  (疾病分類)
drugs:           12,042 筆  (藥品資料)
medical_orders:   2,102 筆  (醫療服務)
case_templates:   1,665 筆  (病例範本) ← 新增 RAG
```

#### RAG 搜尋測試結果

```bash
$ uv run python -m src.rag.case_template_rag search --query "冠心病 胸悶 胸痛 高血壓" --top-k 3

結果 1: 劉蘭英病歷.docx (相似度: 0.1494)
結果 2: 馬林花病歷.docx (相似度: 0.1460)
結果 3: 病程記錄.txt (相似度: 0.1419)
```

#### 6. RAG 整合到 SOAP 生成流程 ✅

**更新檔案：**
- `src/soap/soap_generator.py` - 新增 RAG 檢索功能
- `src/__init__.py` - 改為 Ollama 為主後端
- `tests/test_init.py` - 更新為 Ollama 測試

**整合方式：**
- LLM Prompt 中加入病例範本作為 reference context
- API 回傳 `result["case_templates"]` 包含檢索結果
- CLI 顯示 logger.info 檢索結果

#### 7. 完整 Pipeline 測試 ✅

**測試輸入：** 病人胸悶兩天，有高血壓病史，呼吸困難

**Pipeline 流程：**
```
語音輸入 → ASR → 術語標準化 → ICD-10 → RAG 檢索 → LLM → SOAP
```

**測試結果：**
- 術語標準化：3 個術語（胸悶→chest tightness、高血壓→hypertension、呼吸困難→dyspnea）
- ICD-10 分類：3 個診斷碼（R07.89、R06.02、I10）
- RAG 病例範本檢索：3 個相關病例
- SOAP 生成：✅ 成功

#### 8. 檔案清理 ✅

| 動作 | 說明 |
|------|------|
| 刪除 `CurrentData/各種病例規範模板/` | 282 MB（已同步到 medical.db）|
| 刪除 `agent-harness/` | 清理舊測試目錄 |
| 刪除 `skills/` | 清理重複技能目錄 |
| 刪除 `.planning/` | 清理規劃暫存 |
| 刪除 `tests/test_vllm.py` | 清理過期測試 |

**節省空間：** 300+ MB

#### 9. 測試通過 ✅

```bash
$ uv run pytest tests/ -v
=================== 105 passed ===================
```

---

## ⏳ 待完成項目

### 未來規劃

| 項目 | 說明 | 優先級 |
|------|------|--------|
| **實際病患對話測試** | 前端網頁實際錄音測試 | 🔴 P0 |
| **生產環境部署測試** | Docker 部署驗證 | 🟡 P1 |
| **效能優化** | 模型量化、批次處理 | 🟡 P1 |

### 使用方式

```bash
# 啟動 API 伺服器
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# 瀏覽器開啟
http://localhost:8000

# API 測試
curl -X POST http://localhost:8000/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人胸悶兩天，有高血壓病史"}'

# CLI 模式
uv run python src/cli.py --extended --text "病人咳嗽兩天"
```

### 測試音檔位置

```
tests/fixtures/scenarios/
├── chest_pain.wav       # 胸痛
├── diabetes.wav        # 糖尿病
├── doctor_patient.wav  # 醫病對話
├── drug_order.wav      # 藥物醫囑
├── hypertension.wav    # 高血壓
├── respiratory.wav     # 呼吸系統
├── surgery_record.wav  # 手術記錄
└── wound_care.wav      # 傷口護理
```

**最後更新:** 2026-03-25

---

## 📅 2026-03-25 — LLM 效能測試

### Qwen3.5 兼容性問題 ⚠️

- Qwen3.5 系列在 RTX 2080 Ti (Turing) 崩潰
- GitHub Issue #14715 已標記 not_planned
- 錯誤: CUDA error: an illegal instruction

### 測試結果

| 模型 | 平均時間 | 狀態 |
|------|----------|------|
| qwen2.5:3b | 1.93s | ✅ |
| qwen2.5:7b | 5.11s | ✅ |
| qwen2.5:14b | 20.66s | ✅ |
| qwen3.5:9b | - | ⏭️ 跳過 |

**結論：僅使用 Qwen2.5 系列**
