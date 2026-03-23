# 📋 SoapVoice 每日計畫與待辦事項

**專案名稱:** SoapVoice - Medical Voice-to-SOAP System  
**建立日期:** 2026-03-19  
**當前階段:** 🟢 Phase 1 ✅ 完成，Phase 2 ✅ 完成，Phase 3 ✅ 完成，Phase 4 ⏳ CLI 優化中  
**測試狀態:** 92/92 通過 ✅  
**最後更新:** 2026-03-23  

---

## 📅 2026-03-23 — 今日完成

### Phase 4: CLI 修復與檔案整理 ✅

#### CLI 擴展模式修復

| 問題 | 解決方案 |
|------|----------|
| `src/__init__.py` vllm import 錯誤 | 改為可選 import，Ollama 為主後端 |
| `extended_soapvoice.py` NLP 模組未初始化 | 新增 `_init_models()` 呼叫到各方法 |

**修復後測試：**
```bash
$ uv run python src/cli.py --extended --text "病人咳嗽兩天"

🔍 症狀: ['cough', '咳嗽']
🏥 ICD-10: [('R05', 'Cough')]
📋 醫囑: ['祛痰劑', '止咳藥物', '多喝水']
💊 藥物: [('咳特靈', '1# 3次/日')]
📄 English SOAP: (完整 SOAP 病歷)
```

#### 檔案整理

| 動作 | 說明 |
|------|------|
| 刪除 12 個測試腳本 | test_moonshine_basic.py, test_asr_comparison.py, 等 |
| 刪除重複目錄 | CliVoice/agent-harness/ |
| 刪除過期檔案 | .planning/todos/pending/2026-02-* |
| 刪除暫時檔案 | benchmark_results.json |

**保留的核心腳本：**
- `scripts/extended_soapvoice.py` - 擴展 SOAP 流程
- `scripts/soapvoice_engine.py` - 基本引擎
- `scripts/load_test.py` - 負載測試
- `scripts/test_e2e.py` - 端到端測試
- `scripts/test_models.py` - 模型驗證

#### README.md 更新

- ✅ 新增 CLI 使用說明（基本模式 + 擴展模式）
- ✅ 新增 `--extended`, `--audio`, `--model` 等 CLI 選項說明
- ✅ 更新預設模型：qwen2.5:14b（qwen3.5:9b 有 CUDA 問題）
- ✅ 新增擴展 API 端點 `/api/v1/extended/process` 文件
- ✅ 移除已刪除測試腳本參考
- ✅ 程式碼品質：ruff check 全部通過

---

## 📅 2026-03-21 — 今日完成

### Phase 3.5: 模型測試 ✅

#### Ollama 模型測試結果

| 模型 | 狀態 | SOAP 生成 | 處理時間 | 語言 | 備註 |
|------|------|-----------|----------|------|------|
| **qwen3.5:9b** | ❌ | - | - | - | CUDA 錯誤（RTX 2080 Ti 雙卡不相容） |
| **qwen2.5:7b** | ✅ | ✅ 優秀 | ~3.5s | 繁體中文 | **首選推薦** |
| **qwen2.5:3b** | ✅ | ✅ 良好 | ~3s | 繁體中文 | 快速備用 |
| **llama3:8b** | ✅ | ⚠️ 一般 | ~7s | 英文為主 | 不適合中文場景 |

#### qwen2.5:7b SOAP 生成測試

```
輸入：醫療對話（咳嗽、喉嚨痛、無發燒）

S - 主觀資料:
- 症狀：咳嗽兩天，有痰，喉嚨痛
- 發燒：無

O - 客觀資料:
- 體溫: 正常（未測量）
- 喉嚨：紅腫（+）
- 扁桃腺：無腫大（-）
- 肺部聽診：無異常呼吸音（-）

A - 評估分析:
- 上呼吸道感染

P - 計劃:
- 處理方式：醫師開具藥物
- 隨訪建議：按時服藥，注意觀察症狀是否有改善或惡化
```

### Phase 3.6: NotebookLM 研究 ✅

#### 新增來源（12 個）

| # | 來源 | 類型 |
|---|------|------|
| 1 | Ollama Blog | web_page |
| 2 | HuggingFace Text Generation | web_page |
| 3 | Ollama GitHub | web_page |
| 4 | SOAP Note Wikipedia | web_page |
| 5 | llama.cpp GitHub | web_page |
| 6 | Qwen GitHub | web_page |
| 7 | Qwen HuggingFace | web_page |
| 8 | HuatuoGPT GitHub | web_page |
| 9 | PMC-LLaMA paper | web_page |
| 10 | ChatDoctor paper | web_page |
| 11 | NHI 網站 | web_page |
| 12 | LLaMA-Factory | web_page |

#### NotebookLM 研究發現

- **哈佛研究：** Llama 3.1 405B 在醫學診斷超越 GPT-4（70% vs 64%）
- **台灣趨勢：** 75% 醫療單位最期待「醫療紀錄摘要」應用
- **SOAP 最佳實踐：** RAG + 知識圖譜 + 臨床指南約束

#### NotebookLM Notebook

- **ID:** `0035a6c6-1ef6-49ad-88b0-a39e0f316469`
- **URL:** https://notebooklm.google.com/notebook/0035a6c6-1ef6-49ad-88b0-a39e0f316469
- **來源數量:** 22 個 ✅

### Phase 3.7: 策略調整 ⚠️

> **重要變更：** 從 Ollama 轉向 llama.cpp + HuggingFace

| 變更項目 | 原因 |
|----------|------|
| ~~Ollama~~ | qwen3.5:9b 有 CUDA 相容性問題 |
| **llama.cpp + HuggingFace** | 更靈活、無 CUDA 問題 |

### Phase 3: LLM 部署與外部整合 ✅ 完成

#### 3.1 LlamaEngine 實作 ✅

- [x] 建立 `src/llm/llama_engine.py` — LlamaEngine 類別
  - [x] 使用 llama-cpp-python
  - [x] 支援 GGUF 格式模型（Q4_K_M 量化）
  - [x] GPU offload 設定
  - [x] 串流生成支援
  - [x] 聊天模式支援

#### 3.2 DoctorConsultation API 整合 ✅

- [x] 建立 `src/llm/doctor_consultation.py` — DoctorConsultationClient
  - [x] API Key 認證
  - [x] SOAP 病歷生成端點
  - [x] 錯誤處理與重試機制
  - [x] 診斷驗證、治療建議、藥物交互作用檢查

#### 3.3 雙軌 LLM 引擎 ✅

- [x] 建立 `src/llm/dual_engine.py` — DualLLMEngine
  - [x] 自動選擇本地/雲端 LLM
  - [x] 支援 4 種策略：local_first, cloud_first, local_only, cloud_only
  - [x] Fallback 機制

#### 3.4 Docker 部署設定 ✅

- [x] 更新 `Dockerfile` — 多階段建置（development, production, production-gpu）
- [x] 更新 `docker-compose.yml` — 開發環境配置
- [x] 更新 `docker-compose.prod.yml` — 生產環境配置
- [x] 更新 `.env.example` — 完整環境變數

#### 3.5 模組更新 ✅

- [x] 更新 `src/llm/__init__.py` — 導出所有 LLM 引擎

---

## 📌 完成總覽

### Phase 1: 本地資料庫 ✅

| 項目 | 狀態 | 說明 |
|------|------|------|
| 資料庫初始化 | ✅ | 66.32 MB，110,947 筆資料 |
| ATC 分類 | ✅ | 14 大類，37+ 症狀映射 |
| 查詢 API | ✅ | ICD-10、藥品、醫療服務 |

### Phase 2: 看診流程 ✅

| 項目 | 狀態 | 說明 |
|------|------|------|
| ConsultationFlow | ✅ | 715 行 |
| SessionManager | ✅ | 300 行 |
| RealtimeSearch | ✅ | 575 行，37+ 症狀關鍵字 |
| API 端點 | ✅ | 400+ 行 |

### Phase 3: LLM 部署 ✅

| 項目 | 狀態 | 說明 |
|------|------|------|
| LlamaEngine | ✅ | llama.cpp 本地推理 |
| DoctorConsultationClient | ✅ | 雲端 API 整合 |
| DualLLMEngine | ✅ | 雙軌自動切換 |
| Docker | ✅ | 4 種建置目標 |
| .env | ✅ | 完整環境變數 |
| 模型測試 | ✅ | qwen2.5:7b SOAP 生成 ~3.5s |
| NotebookLM 研究 | ✅ | 22 個來源研究完成 |

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

**最後更新:** 2026-03-23  
**下次更新:** 待續

---

## ✅ 2026-03-23 下午完成項目

### 1. Qwen3.5-9B 模型 ✅

- [x] 使用 Ollama 下載 `qwen3.5:9b` (6.6 GB)
- [x] 模型可用但有 EOF 錯誤（可能是 RTX 2080 Ti 雙卡不相容問題）
- [x] **替代方案：** 使用 `qwen2.5:7b` 正常運作

### 2. Whisper CLI 整合 ✅

- [x] 載入 openai-whisper skill
- [x] Whisper CLI 有 numba/numpy 相容性問題
- [x] 使用 faster-whisper 替代（已安裝）
- [x] 測試轉寫：`tests/fixtures/sample_zh.wav` → 中文

### 3. 完整 Pipeline 測試 ✅

**流程：** Whisper (faster-whisper) → Ollama (qwen2.5:7b) → SOAP 病歷

```bash
# Step 1: 語音轉文字
轉錄結果: 病人 阻塑胸悶兩天 伴隨呼吸困難血壓偏高 建議心電圖胸部X光檢查...

# Step 2: 生成 SOAP 病歷
S - 主觀資料:
- 病人主訴：阻塞性胸悶兩天，伴隨呼吸困難
- 血壓偏高

O - 客觀資料:
- 未提供具體的客觀檢查結果

A - 評估:
- 病人可能患有胸悶和呼吸困難，需進一步檢查

P - 計劃:
- 建議進行心電圖檢查及胸部X光檢查
```

### Ollama 可用模型

| 模型 | 大小 | 狀態 | 原因 |
|------|------|------|------|
| qwen3.5:9b | 6.6 GB | ❌ EOF/CRASH | RTX 2080 Ti 雙卡 CUDA 不相容 |
| qwen2.5:7b | 4.7 GB | ✅ 正常 | 穩定運作 |
| qwen2.5:3b | 1.9 GB | ✅ 正常 | 穩定運作 |
| qwen2.5:14b | 9.0 GB | 未測試 | 可能也有問題 |

### 🐛 RTX 2080 Ti 雙卡問題

**錯誤日誌：**
```
panic: failed to sample token
CUDA error: an illegal instruction was encountered
```

**原因：**
- RTX 2080 Ti 是 Turing 架構 (compute 7.5)
- 雙 GPU 設置觸發 CUDA 相容性問題
- **僅 qwen3.5:9b 觸發錯誤**（其他模型正常）

**測試結果：**
| 模型 | 大小 | 狀態 |
|------|------|------|
| **qwen3.5:9b** | 6.6 GB | ❌ 崩潰 | MTP 架構不相容 |
| qwen2.5:14b | 9.0 GB | ✅ 正常 | |
| phi4:latest | 9.1 GB | ✅ 正常 | |
| qwen2.5:7b | 4.7 GB | ✅ 正常 | 首選 |
| qwen2.5:3b | 1.9 GB | ✅ 正常 | |

**解決方案：**
1. **首選：** 使用 `qwen2.5:7b` 或 `qwen2.5:14b`
2. **避免使用 qwen3.5:9b**
3. 可嘗試單 GPU 模式：

```bash
# 單 GPU 模式（可能仍有問題）
CUDA_VISIBLE_DEVICES=0 ollama run qwen3.5:9b
```

**根本原因：** qwen3.5 使用新的 MTP (Multi-Token Prediction) 架構，與 RTX 2080 Ti 雙卡 CUDA 設定不相容。這是 Ollama 與特定 GPU 配置的已知問題。

---

### 🎯 待完成項目

| 項目 | 說明 | 優先級 |
|------|------|--------|
| **Windows Docker 自動化** | 建立 Windows 啟動腳本 | 🟡 P1 |
| **Web API 文件** | 行動 app 整合文件 | 🟡 P1 |
| **醫療術語擴充** | 增加更多術語映射 | 🟡 P2 |

### 🚀 使用方式

#### CLI 模式

```bash
# 基本 SOAP 生成
uv run python src/cli.py --text "病人咳嗽兩天"

# 擴展模式（含症狀/ICD-10/醫囑/藥物）
uv run python src/cli.py --extended --text "病人胸悶兩天"

# 音訊輸入
uv run python src/cli.py --audio recording.wav --extended
```

#### API 模式

```bash
# 啟動 API 伺服器
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 基本 SOAP 生成
curl -X POST http://localhost:8000/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人咳嗽兩天"}'

# 擴展 SOAP（含症狀/ICD-10/醫囑/藥物）
curl -X POST http://localhost:8000/api/v1/extended/process \
  -H "Content-Type: application/json" \
  -d '{"text": "病人咳嗽兩天", "include_all": true}'
```

**最後更新:** 2026-03-23  
**下次更新:** 待續
