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

---

## 📅 2026-03-26 ~ 2026-03-27 — 模型比較測試

### CompareModel.md 建立 ✅

**測試配置：**
- 模型：qwen2.5:14b, qwen2.5:7b, qwen2.5:3b
- 音檔：8 個醫療場景測試
- 環境：Ollama + GPU (RTX 2080 Ti)

### 測試結果 (GPU 模式)

| 模型 | 胸痛 | 高血壓 |
|------|------|--------|
| qwen2.5:14b | 83.86秒 | 68.09秒 |
| qwen2.5:7b | 16.33秒 | 6.22秒 |
| qwen2.5:3b | 12.9秒 | 25.21秒 |

### 問題修復 ⚠️

1. **音檔重複問題**：8 個音檔曾是相同內容 → 已使用 edge-tts 重新生成
2. **SOAP 亂碼問題**：`num_predict` 太小 (512) → 增加到 2048
3. **API 掛起問題**：非同步端點中的阻塞調用 → 使用 `asyncio.to_thread()`

### GPU 錯誤狀態 ⚠️

- GPU 0: ERR! 狀態，無法載入模型
- GPU 1: ERR! 狀態
- Ollama CUDA error: unable to allocate CUDA0 buffer
- 無法執行 CPU 測試

### 待完成

| 項目 | 說明 | 優先級 |
|------|------|--------|
| GPU 重置 | 需要管理員執行 `nvidia-smi --gpu-reset` | 🔴 P0 |
| CPU 模式測試 | 比較 CPU vs GPU 效能 | 🟡 P1 |

### 產出檔案

- `CompareModel.md` - 模型比較報告
- `tests/fixtures/results/compare_20260326_163919.json` - 測試結果

**最後更新:** 2026-03-27

---

## 📅 2026-03-27 — Windows EXE 部署規劃

### Windows EXE 部署架構

**推薦方案：llama.cpp CPU 模式**

```
SoapVoice.exe
├── FastAPI Server (Port 8000)
└── llama.cpp (Qwen2.5:7b Q4_K_M, ~4.5GB)
```

### 模型選擇

| 模型 | 量化 | 大小 | 速度 |
|------|------|------|------|
| qwen2.5:7b | Q4_K_M | ~4.5GB | ~8-12 tok/s ⭐推薦 |
| qwen2.5:3b | Q4_K_M | ~2.0GB | ~15-20 tok/s |

### Windows 部署選項

| 選項 | 說明 | 優點 | 缺點 |
|------|------|------|------|
| 方案一 | PyInstaller + Ollama 外置 | 穩定 | 需兩段式安裝 |
| 方案二 | llama.cpp CPU | 單一 EXE | 僅 CPU |
| 方案三 | 混合模式 | 彈性高 | 複雜 |

### 待執行工作

| 優先 | 工作 | 說明 | 狀態 |
|------|------|------|------|
| P0 | llama.cpp 引擎整合 | 建立 src/llm/llama_engine.py | ✅ 已完成 |
| P1 | CLI 介面建立 | Typer 命令列工具 | ✅ 已完成 |
| P1.1 | 模型比較測試 | qwen2.5:3b/7b vs qwen3.5:4b/9b | ✅ 已完成 |
| P2 | Webhook 端點 | 事件驅動整合 | ✅ 已完成 |
| P3 | 檔案監控服務 | watch/ 目錄自動化 | ✅ 已完成 |
| P4 | PyInstaller 包裝 | Windows EXE 編譯 | ✅ 已完成 |

### 2026-03-27 完成項目

| 項目 | 說明 | 狀態 |
|------|------|------|
| Qwen2.5 GGUF 模型 | 已存在於 models/ 目錄 | ✅ |
| Ollama qwen2.5:7b | 已下載並可用 | ✅ |
| Ollama qwen2.5:3b | 已下載並可用 | ✅ |
| Typer CLI | 建立 src/cli_typer.py (200+ 行) | ✅ |
| CompareModel.md | 更新 8 音檔 4 模型測試結果 | ✅ |
| Webhook API | 建立 src/api/webhook_api.py | ✅ |
| 檔案監控服務 | 建立 src/services/file_monitor.py | ✅ |
| PyInstaller 腳本 | 建立 SoapVoice.spec + build_windows.sh | ✅ |

### 新增 API 端點

```bash
# Webhook
curl http://localhost:8000/api/v1/webhooks/health
curl -X POST http://localhost:8000/api/v1/webhooks/trigger

# 檔案監控
curl http://localhost:8000/api/v1/file-monitor/health
curl -X POST http://localhost:8000/api/v1/file-monitor/init
curl -X POST http://localhost:8000/api/v1/file-monitor/start
```

### 2026-03-27 完成項目

| 項目 | 說明 | 狀態 |
|------|------|------|
| Qwen2.5 GGUF 模型 | 已存在於 models/ 目錄 | ✅ |
| Ollama qwen2.5:7b | 已下載並可用 | ✅ |
| Ollama qwen2.5:3b | 已下載並可用 | ✅ |
| Typer CLI | 建立 src/cli_typer.py (200+ 行) | ✅ |
| CompareModel.md | 更新 8 音檔 4 模型測試結果 | ✅ |

### 模型比較結果 (CPU 模式)

| 模型 | 大小 | 平均時間 | 推薦度 |
|------|------|----------|--------|
| qwen2.5:7b | 4.7 GB | 9.6 秒 | ⭐⭐⭐ 最佳 |
| qwen2.5:3b | 1.9 GB | 15.3 秒 | ⭐⭐ 推薦 |
| qwen3.5:4b | 3.4 GB | 63.7 秒 | 不推薦 |
| qwen3.5:9b | 6.6 GB | 83.1 秒 | 不推薦 |

### 使用方式

```bash
# 使用 Ollama 後端（需先啟動 ollama serve）
uv run python src/cli_typer.py main --text "病人咳嗽" --backend ollama --model qwen2.5:7b

# 使用 llama.cpp 後端（CPU 模式，約 4.5GB 模型）
uv run python src/cli_typer.py main --text "病人咳嗽" --backend llama.cpp --model-path "models/qwen2.5-7b-instruct-q4_k_m.gguf"

# 啟動 API 伺服器
uv run python src/cli_typer.py serve
```

### 已知問題

1. **GPU 不可用**：CUDA error - 需要系統重啟
2. **llama.cpp 模型載入**：目前 GGUF 模型載入失敗（需更新 llama-cpp-python）
3. **建議**：使用 Ollama 後端進行測試

**最後更新:** 2026-03-27

---

## 📅 2026-04-02 — Phase 7: Windows Desktop GUI & 雲端整合規劃 (New Plan)

### 🚀 Phase 7 核心目標
本階段旨在打造適合診所第一線使用的「Windows 漂浮視窗介面」，並將病歷文字、截圖識別、以及雲端 API 進行深度整合。

| 任務分類 | 說明 | 優先級 |
|------|------|--------|
| **Windows 小視窗 (GUI)** | 使用 Tkinter 建立「永遠置頂(Always-On-Top)」、可拖曳的微型視窗，內含巨型「開始錄音」與「設定」按鈕。支援背景呼叫 FastAPI 核心。 | 🔴 P0 |
| **互動狀態與顏色提示** | **預備**: 藍色 [▶ 開始錄音]<br>**錄音中**: 閃爍紅色 [⏹ 停止錄音]<br>**處理中**: 黃色 [⏳ 處理中]<br>**完成**: 綠色提示並自動複製至剪貼簿 (Auto Clipboard Copy) | 🔴 P0 |
| **診所與醫師多重註冊** | 簡化註冊流程。設定檔內寫入「診所名稱」、「醫療機構代碼」(如 3503190424)。支援同一診所下多名醫師(姓名、身份證或代號)快速切換。 | 🟡 P1 |
| **螢幕截圖與 OCR 識別** | 按下錄音的瞬間截取螢幕，使用純 CPU OCR (EasyOCR/pytesseract) 提取發散文字，再交由 Qwen2.5 結構化成病患與醫師資訊。 | 🔴 P0 |
| **自動比對醫師身分** | 從 OCR 取出的文字中，自動比對是否與「已註冊之某位醫師」相符，自動 Tag 到病歷上。 | 🟡 P1 |
| **TXT Tag 格式輸出** | 以純文字(TXT)複製至剪貼簿，且結尾自動帶上 Tag (如 `#診所名稱 #醫師姓名 #紀錄時間`) 方便貼上 HIS 系統歸檔。 | 🟡 P1 |
| **雲端 API 端點 (Cloud)** | API 新增：<br>`POST /api/v1/cloud/sync_wav` (上傳音檔)<br>`GET /api/v1/cloud/export_md/{id}` (匯出病歷) | 🟢 P2 |

### 🔍 執行步驟
1. 實作 `src/gui/desktop_app.py` 處理 Tkinter 啟動與 FastAPI 背景綁定。
2. 整合 `EasyOCR` 到 `src/nlp/ocr_parser.py` 用作截圖取詞。
3. 擴增資料庫 Schema / 或本機 config 支援多位醫師建檔與診所機構代碼。
4. 打通「GUI UI -> 截圖 -> 轉錄 -> LLM SOAP -> 剪貼簿」的完整 Pipeline。

**計畫更新日期:** 2026-04-02

---

## 📅 2026-04-02 — GUI 介面優化完成 ✅

### Phase 7.1: Windows 桌面 GUI 扁平化設計 ✅

根據用戶需求，已完成 GUI 介面的全面優化：

#### 1. 橫向長條形扁平化至一半 ✅
- **視窗尺寸:** 300x120 像素（原 180x260）
- **佈局:** 橫向排列，更適合桌面使用
- **設計:** 扁平化設計，減少視覺干擾

#### 2. 移除註冊點 ✅
- **簡化流程:** 移除醫師註冊/登入功能
- **直接使用:** 開箱即用，無需設定
- **狀態顯示:** 簡化為「準備就緒」狀態

#### 3. 加入麥克風圖示 ✅
- **主按鈕:** 「🎤 開始錄音」紅色大按鈕
- **視覺提示:** 麥克風圖示 + 文字說明
- **狀態指示:** 錄音中閃爍紅色

#### 4. 彩色設計 ✅
- **主色調:** 藍色 (#3498db) 背景
- **功能按鈕:**
  - 錄音: 紅色 (#e74c3c)
  - 停止: 灰色 (#95a5a6)
  - 處理: 橙色 (#f39c12)
  - 測試: 紫色 (#9b59b6)
- **狀態指示:** 綠色 (#2ecc71)

#### 5. 測試音檔支援 ✅
- **測試按鈕:** 「🧪 測試」紫色按鈕
- **音檔位置:** `tests/fixtures/scenarios/chest_pain.wav`
- **功能:** 直接使用預設測試音檔進行處理

### 使用方式

```bash
# 啟動 GUI
uv run python run_gui.py

# 或直接執行
python run_gui.py
```

### 功能流程
1. **🎤 開始錄音** - 開始錄製語音
2. **⏹ 停止** - 停止錄音
3. **⚡ 處理** - 處理錄音生成 SOAP 病歷
4. **🧪 測試** - 使用測試音檔快速測試
5. **📋 結果彈窗** - 顯示並複製 SOAP 病歷

### 檔案更新
- `src/gui/desktop_app.py` - 全新扁平化 GUI 設計
- `run_gui.py` - 整合啟動腳本
- `test_gui.py` - GUI 測試腳本

**完成時間:** 2026-04-02

