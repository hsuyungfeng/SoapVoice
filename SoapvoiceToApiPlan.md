# SoapVoice 本地 API 系統建置計畫

**專案名稱:** SoapVoice - Medical Voice-to-SOAP System  
**計畫版本:** v1.0.1  
**建立日期:** 2026-03-21  
**目標:** 建立本地醫療資料庫 + 10分鐘語音看診流程 + 小型 LLM 部署  
**最後更新:** 2026-03-21  
**計畫狀態:** Phase 1 ✅ 完成，Phase 2 ✅ 完成，Phase 3 ⏳ 進行中  

---

## 📋 執行摘要

本計畫旨在將 SoapVoice 系統升級為**完整的本地部署醫療語音 API 系統**，達到以下目標：

| 目標 | 說明 | 優先級 | 狀態 |
|------|------|--------|------|
| **本地資料庫整合** | 建立 ICD-10、藥物、醫囑本地資料庫 | 🔴 P0 | ✅ 完成 |
| **10分鐘語音看診流程** | 錄音 → 轉譯 → LLM整理 → 資料庫搜尋 → SOAP輸出 | 🔴 P0 | ✅ 完成 |
| **小型 LLM 部署** | 使用 llama.cpp + HuggingFace + <13B 模型 + <20GB GPU | 🔴 P0 | ⏳ 進行中 |
| **外部 LLM 整合** | 集成 DoctorConsultation LLM (https://doctor-toolbox.com/) | 🔴 P0 | ⏳ 進行中 |
| **語音辨識模型** | Whisper CLI + Moonshine 本地 ASR | 🟡 P1 | ⏳ 進行中 |
| **API Docker 化** | Windows 環境 Docker 部署 | 🟡 P1 | ⏳ 進行中 |

---

## 🎯 第一階段：本地資料庫建置 ✅ 完成

### 1.1 資料庫架構設計 ✅

```
local_db/
├── medical.db                    # SQLite - 整合式資料庫（96,802 + 12,042 + 2,102 筆）
└── search_index/                # Meilisearch - 全文搜尋索引（待實作）
    ├── icd10_index/
    ├── drugs_index/
    └── orders_index/
```

### 1.1.1 已建立檔案

| 檔案 | 說明 | 行數 |
|------|------|------|
| `src/db/__init__.py` | 模組初始化 | 34 |
| `src/db/initialize_database.py` | 資料庫初始化腳本 | 400+ |
| `src/db/local_database.py` | SQLite 查詢介面 | 370 |
| `src/db/atc_classification.py` | ATC 分類對照表 | 359 |
| `src/db/integration_example.py` | 整合範例 | 100+ |

### 1.1.2 已初始化資料

| 資料表 | 筆數 | 資料來源 | 資料庫大小 |
|--------|------|---------|-----------|
| ICD-10 | 96,802 筆 | `icd10-data.js` | ✅ |
| 藥品 | 12,042 筆 | `藥品項查詢項目檔260316...csv` | ✅ |
| 醫療服務 | 2,102 筆 | `醫療服務給付項目NotebookLM1150316.csv` | ✅ |
| 病例範本 | 1 筆 | `各种病例规范模板/` | ✅ |
| **總計** | **110,947 筆** | | **66.32 MB** |

### 1.1.3 ATC 分類系統 ✅

已建立完整的 ATC（解剖學治療學及化學分類系統）對照表，包含：

- **14 大類**（A-R）：消化道、心血管、神經、呼吸等
- **症狀→ATC 映射**：37+ 種常見症狀對應
- **藥物搜尋**：根據 ATC 代碼快速查詢藥物

```python
from src.db import get_atc_by_symptom, LocalDatabase

# 根據症狀取得 ATC 分類
atc_codes = get_atc_by_symptom('咳嗽')
# → ['R05', 'R05D', 'R05C']

# 根據 ATC 搜尋藥物
db = LocalDatabase(Path('data/local_db/medical.db'))
drugs = db.search_drugs_by_atc_class('R05')
```

### 1.2 已實作的查詢功能

```python
from src.db import LocalDatabase

db = LocalDatabase(Path('data/local_db/medical.db'))

# ICD-10 搜尋
results = db.search_icd10('胸悶', limit=10)

# 藥品搜尋
results = db.search_drugs('止痛', limit=10)
results = db.search_drugs_by_atc_class('N02', limit=20)  # ATC 分類

# 醫療服務搜尋
results = db.search_medical_orders('注射', limit=10)

# 統計資訊
stats = db.get_statistics()
```

---

## 🎯 第二階段：10分鐘語音看診流程 ✅ 完成

### 2.1 系統架構

```
┌──────────────────────────────────────────────────────────────────┐
│                      看診流程架構                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐         │
│  │  錄音    │───▶│  Whisper CLI │───▶│  即時轉譯      │         │
│  │  10分鐘  │    │  Moonshine   │    │  (Streaming)   │         │
│  └──────────┘    └──────────────┘    └───────┬────────┘         │
│                                                │                  │
│                                                ▼                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐         │
│  │  LLM     │◀───│  對話整理    │◀───│  分段組裝      │         │
│  │  整理    │    │  (Summarize) │    │  (Assembly)    │         │
│  └────┬─────┘    └──────────────┘    └────────────────┘         │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐         │
│  │  SOAP    │───▶│  資料庫      │───▶│  完整輸出      │         │
│  │  生成    │    │  搜尋        │    │  + 建議        │         │
│  └──────────┘    └──────────────┘    └────────────────┘         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 已建立檔案

| 檔案 | 說明 | 行數 |
|------|------|------|
| `src/consultation/__init__.py` | 模組初始化 | 30 |
| `src/consultation/consultation_flow.py` | 核心諮詢流程 | 715 |
| `src/consultation/session_manager.py` | 會話管理 | 300 |
| `src/consultation/realtime_search.py` | 即時資料庫搜尋 | 575 |
| `src/api/consultation_api.py` | RESTful API 端點 | 400+ |

### 2.3 主要類別

#### ConsultationFlow（諮詢流程管理器）

```python
from src.consultation import ConsultationFlow, ConsultationConfig

# 建立諮詢流程
config = ConsultationConfig(
    max_duration_seconds=600,      # 10 分鐘
    whisper_model_size="medium",
    llm_model="qwen2.5-7b-q4_k_m.gguf",
)
flow = ConsultationFlow(config)

# 設定病患背景
flow.set_patient_context({"age": 45, "gender": "M", "chief_complaint": "胸悶"})

# 開始諮詢
flow.start_consultation()

# 處理音頻塊
flow.process_audio_chunk(audio_bytes)

# 結束諮詢
flow.end_consultation()

# 生成 SOAP
result = flow.generate_soap()
```

#### SessionManager（會話管理器）

```python
from src.consultation import SessionManager

manager = SessionManager()

# 建立新會話
session = manager.create_session({"age": 45, "gender": "M"})

# 完成會話
manager.complete_session(session.session_id, result)

# 列出歷史會話
sessions = manager.list_saved_sessions()
```

#### RealtimeSearch（即時搜尋）

```python
from src.consultation import RealtimeSearch

searcher = RealtimeSearch()

# 搜尋所有類別
results = searcher.search_all("病人咳嗽兩天，有痰")

# 分類搜尋
icd10 = searcher.search_icd10("胸悶")
drugs = searcher.search_drugs("頭痛")
orders = searcher.search_medical_orders("注射")

# ATC 建議
recommendations = searcher.get_atc_recommendations(["咳嗽", "發燒"])
```

### 2.4 API 端點

```
POST /api/v1/consultation/start     # 開始新會話
POST /api/v1/consultation/end       # 結束錄音
POST /api/v1/consultation/soap/generate  # 生成 SOAP
POST /api/v1/consultation/search     # 即時搜尋
GET  /api/v1/consultation/stats     # 取得統計
GET  /api/v1/consultation/sessions  # 列出歷史會話
WS   /api/v1/consultation/ws        # WebSocket 即時串流
```

### 2.5 已實作功能

| 功能 | 說明 | 狀態 |
|------|------|------|
| 即時語音轉文字 | Faster-Whisper / Moonshine 串流處理 | ✅ |
| 症狀自動提取 | 37+ 症狀關鍵字偵測 | ✅ |
| ICD-10 建議 | 根據症狀查詢建議診斷碼 | ✅ |
| 藥品建議 | ATC 分類 + 名稱搜尋 | ✅ |
| 醫療服務建議 | 根據症狀查詢建議醫囑 | ✅ |
| SOAP 病歷生成 | LLM 生成結構化病歷 | ✅ |
| 會話管理 | 保存/載入/過期清理 | ✅ |
| 即時搜尋快取 | 減少重複查詢 | ✅ |

---

## 🎯 第三階段：LLM 部署與外部整合 ⏳ 進行中

### 3.1 模型測試結果（2026-03-21）

| 模型 | 測試狀態 | SOAP 生成 | 處理時間 | 語言支援 | 備註 |
|------|---------|------------|---------|---------|------|
| **qwen3.5:9b** | ❌ CUDA 錯誤 | - | - | - | RTX 2080 Ti 雙卡不相容 |
| **qwen2.5:7b** | ✅ 正常 | ✅ 優秀 | ~3.5s | 繁體中文 | **首選推薦** |
| **qwen2.5:3b** | ✅ 正常 | ✅ 良好 | ~3s | 繁體中文 | 快速備用 |
| **llama3:8b** | ✅ 正常 | ⚠️ 一般 | ~7s | 英文為主 | 不適合中文場景 |
| **HuatuoGPT-7B** | ❌ Ollama 無 | - | - | - | 需 HuggingFace 部署 |

### 3.2 雙軌 LLM 策略（新方向）

> **重要更新（2026-03-21）：** 從 Ollama 轉向 llama.cpp + HuggingFace 直接部署

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLM 推理策略（新版）                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  本地部署（llama.cpp + HuggingFace）         外部 API                         │
│  ┌─────────────────────────────┐            ┌─────────────────────────────┐│
│  │ Qwen2.5-7B-GGUF             │            │ DoctorConsultation           ││
│  │ (Q4_K_M 量化)               │            │ (doctor-toolbox.com)         ││
│  │ <13B 參數                   │            │                              ││
│  │ <14GB VRAM                  │            │ 雲端推理                     ││
│  │ llama.cpp 推理引擎           │            │                              ││
│  │ 完全離線運行                 │            │                              ││
│  └─────────────────────────────┘            └─────────────────────────────┘│
│                                                                              │
│  用途：                          用途：                                      │
│  - 即時轉譯後處理                 - SOAP 病歷生成（增強版）                  │
│  - 術語標準化                    - 複雜診斷建議                             │
│  - 快速分類                      - 藥物交互作用檢查                         │
│                                                                              │
│  ASR 語音辨識：                                                                 │
│  ┌─────────────────────────────┐                                             │
│  │ Whisper CLI                  │ ← 預設（已整合 openai-whisper skill）       │
│  │ Moonshine                    │ ← 備用（輕量、快速）                        │
│  │ Qwen3-ASR                    │ ← 中文優化（簡→繁）                        │
│  └─────────────────────────────┘                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 模型選擇（新版）

| 模型 | 參數 | VRAM | 量化 | 來源 | 用途 | 優先級 |
|------|------|------|------|------|------|--------|
| **Qwen2.5-7B** | 7B | 14GB | Q4_K_M | HuggingFace | 本地主力 | ⭐⭐⭐⭐⭐ |
| **Qwen2.5-3B** | 3B | 6GB | Q4_K_M | HuggingFace | 本地備用/行動 | ⭐⭐⭐⭐ |
| **Whisper CLI** | - | - | - | 本地 | 語音轉文字 | ⭐⭐⭐⭐⭐ |
| **Moonshine** | - | - | - | 本地 | 快速 ASR | ⭐⭐⭐ |
| **DoctorConsultation** | - | - | API | 雲端 | SOAP 增強 | ⭐⭐⭐⭐ |

### 3.4 模型下載（HuggingFace）

```bash
# 模型下載位置
mkdir -p models/

# Qwen2.5-7B GGUF（主要模型）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF Qwen2.5-7B-Instruct-Q4_K_M.gguf --local-dir models/

# Qwen2.5-3B GGUF（快速備用）
huggingface-cli download Qwen/Qwen2.5-3B-Instruct-GGUF Qwen2.5-3B-Instruct-Q4_K_M.gguf --local-dir models/

# 或使用 python 下載
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-7B-Instruct-GGUF', filename='Qwen2.5-7B-Instruct-Q4_K_M.gguf', local_dir='models/')"
```

### 3.5 Llama.cpp 引擎實作（已實作）

```python
# src/llm/llama_engine.py ✅ 已實作

"""
Llama.cpp LLM 推理引擎

使用 llama.cpp 进行本地 LLM 推理
透過 HuggingFace GGUF 模型
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LlamaConfig:
    """Llama.cpp 設定"""
    model_path: str = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    n_gpu_layers: int = 35
    n_ctx: int = 4096
    n_threads: int = 8
    temperature: float = 0.3
    max_tokens: int = 1024


class LlamaEngine:
    """Llama.cpp LLM 推理引擎"""

    def __init__(self, config: Optional[LlamaConfig] = None):
        self.config = config or LlamaConfig()
        self._model = None

    def _load_model(self) -> None:
        """載入模型"""
        from llama_cpp import Llama

        logger.info(f"載入 LLM 模型: {self.config.model_path}")
        self._model = Llama(
            model_path=str(Path(self.config.model_path).resolve()),
            n_gpu_layers=self.config.n_gpu_layers,
            n_ctx=self.config.n_ctx,
            n_threads=self.config.n_threads,
            use_mmap=True,
            verbose=False,
        )
        logger.info("LLM 模型載入完成")

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """生成文字"""
        if self._model is None:
            self._load_model()

        output = self._model(
            prompt,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        return output["choices"][0]["text"].strip()
```

### 3.6 DoctorConsultation LLM 整合（已實作）

```python
# src/llm/doctor_consultation.py ✅ 已實作

"""
DoctorConsultation LLM 整合模組

使用外部 API 生成醫療 SOAP 病歷
"""

import httpx
from typing import Optional, Dict, Any

class DoctorConsultationClient:
    """DoctorConsultation API 客戶端"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://doctor-toolbox.com/DoctorConsultation",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.Client(timeout=timeout)

    def generate_soap(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        icd10_codes: Optional[list[str]] = None,
        drug_recommendations: Optional[list[str]] = None,
    ) -> Dict[str, str]:
        """生成 SOAP 病歷"""
        response = self.client.post(
            f"{self.base_url}/generate",
            json={
                "transcript": transcript,
                "patient_context": patient_context or {},
                "icd10_codes": icd10_codes or [],
                "drug_recommendations": drug_recommendations or [],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return response.json()
```

### 3.7 Docker 部署設定（已實作）

```yaml
# docker-compose.yml ✅ 已實作
# docker-compose.prod.yml ✅ 已實作

version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./data:/app/data
      - ./local_db:/app/local_db
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - LLM_MODEL_PATH=/app/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf
      - DOCTOR_CONSULTATION_API_KEY=${DOCTOR_CONSULTATION_API_KEY}
      - DOCTOR_CONSULTATION_BASE_URL=https://doctor-toolbox.com/DoctorConsultation
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## 📊 NotebookLM 研究發現（2026-03-21）

根據 NotebookLM 對 22 個來源的分析：

### 哈佛醫學院研究（2026-03）
- **Llama 3.1 405B** 在醫學診斷複雜病例判斷上已超越 GPT-4
  - Llama 3.1 405B: 70% 準確率
  - GPT-4: 64% 準確率

### 台灣醫療趨勢
- **75%** 醫療單位最期待「醫療紀錄摘要」應用
- **27%** 採用在地部署（強化資安與資料控制）
- **60%** 面臨資料格式不一致問題

### SOAP 病歷生成最佳實踐
1. **減少幻覺：** RAG + 知識圖譜注入 + 臨床指南約束
2. **品質保證：** 不確定性量化 + CHAI 責任型 AI 指引
3. **工作流程整合：** UI 贴近臨床習慣 + HIS API 整合

### NotebookLM Notebook
- **ID:** `0035a6c6-1ef6-49ad-88b0-a39e0f316469`
- **URL:** https://notebooklm.google.com/notebook/0035a6c6-1ef6-49ad-88b0-a39e0f316469
- **來源數量:** 22 個

---

## 📊 實作時間表

| 階段 | 工作項目 | 預估工時 | 優先級 | 狀態 |
|------|---------|---------|--------|------|
| **Phase 1** | 本地資料庫建置 | | | ✅ 完成 |
| **Phase 2** | 看診流程實作 | | | ✅ 完成 |
| **Phase 3** | LLM 本地部署 | | | ⏳ 進行中 |
| | 3.1 LlamaEngine 實作 | - | 🔴 | ✅ |
| | 3.2 DoctorConsultation API 整合 | - | 🔴 | ✅ |
| | 3.3 模型下載（HuggingFace） | 2h | 🔴 | ⏳ |
| | 3.4 模型測試（qwen2.5:7b） | 1h | 🔴 | ✅ |
| | 3.5 Whisper CLI 整合 | 2h | 🔴 | ⏳ |
| | 3.6 Moonshine ASR 整合 | 2h | 🟡 | ⏳ |
| | 3.7 Docker 設定 | - | 🔴 | ✅ |
| | 3.8 Windows 啟動腳本 | 2h | 🟡 | ⏳ |
| | 3.9 效能測試 | 4h | 🟡 | ⏳ |
| **總計** | | **65h** | | **Phase 1-2 完成** |

---

## ✅ 驗收標準

### Phase 1：本地資料庫 ✅

- [x] ICD-10 資料庫包含 96,802 筆資料
- [x] 醫療服務資料庫包含 2,102 筆資料
- [x] 藥品資料庫包含 12,042 筆資料
- [x] ATC 分類系統完整（14 大類，37+ 症狀映射）
- [x] 查詢回應時間滿意

### Phase 2：看診流程 ✅

- [x] 支援 10 分鐘連續錄音
- [x] 即時症狀提取（37+ 關鍵字）
- [x] 即時 ICD-10/藥品/醫囑建議
- [x] SOAP 病歷生成
- [x] 會話管理（保存/載入）

### Phase 3：LLM 部署 ⏳

- [x] LlamaEngine 實作完成
- [x] DoctorConsultation API 整合完成
- [x] 模型測試 qwen2.5:7b（~3.5s SOAP 生成）
- [ ] 模型下載 HuggingFace GGUF
- [ ] Whisper CLI 整合
- [ ] Moonshine ASR 整合
- [ ] Docker 容器成功啟動
- [ ] Windows 環境可正常執行

---

## 📁 產出檔案清單

```
SoapVoice/
├── src/
│   ├── db/
│   │   ├── __init__.py              # ✅
│   │   ├── local_database.py        # ✅
│   │   ├── initialize_database.py   # ✅
│   │   ├── atc_classification.py   # ✅
│   │   └── integration_example.py   # ✅
│   ├── consultation/
│   │   ├── __init__.py             # ✅
│   │   ├── consultation_flow.py    # ✅
│   │   ├── session_manager.py      # ✅
│   │   └── realtime_search.py      # ✅
│   ├── api/
│   │   ├── consultation_api.py     # ✅
│   │   ├── rest.py                 # ✅
│   │   └── websocket.py            # ✅
│   └── llm/
│       ├── ollama_engine.py        # ✅ (Ollama)
│       ├── llama_engine.py          # ✅ (llama.cpp)
│       ├── doctor_consultation.py   # ✅ (外部 API)
│       └── dual_engine.py          # ✅ (雙軌引擎)
├── data/
│   ├── local_db/
│   │   └── medical.db              # ✅ (66.32 MB)
│   └── recordings/                  # ✅
├── models/                          # ⏳ 待下載
│   ├── Qwen2.5-7B-Instruct-Q4_K_M.gguf
│   └── Qwen2.5-3B-Instruct-Q4_K_M.gguf
├── scripts/
│   ├── initialize_database.py       # ✅
│   └── download_llm_models.sh       # ⏳
├── docker-compose.yml               # ✅
├── Dockerfile                       # ✅
├── .env.example                    # ✅
└── requirements.txt                # ✅
```

---

## 📝 備註

1. **雙軌 LLM 策略：**
   - 本地 llama.cpp + HuggingFace（Qwen2.5 7B）：即時處理、低延遲、完全離線
   - DoctorConsultation API：複雜推理、雲端計算、持續更新

2. **模型來源變更（2026-03-21）：**
   - 從 Ollama 轉向 HuggingFace GGUF + llama.cpp
   - Ollama 有 CUDA 相容性問題（RTX 2080 Ti 雙卡）
   - HuggingFace 提供更靈活的量化選項

3. **DoctorConsultation API：**
   - URL: `https://doctor-toolbox.com/DoctorConsultation`
   - 需要 API Key 認證
   - 支援 SOAP 病歷生成增強

4. **Llama.cpp 安裝注意：** 需先安裝 CMake 和編譯工具
   ```bash
   # Ubuntu/Debian
   apt install cmake build-essential
   
   # Windows
   # 使用 Visual Studio Developer Command Prompt
   ```

5. **GPU 驅動需求：** 需安裝 NVIDIA Driver 535+
   ```bash
   nvidia-smi  # 驗證驅動
   ```

6. **模型量化：** 建議使用 Q4_K_M 量化，平衡品質與效能

7. **Windows Docker：** 需啟用 WSL 2 和 CUDA in WSL

8. **ASR 語音辨識選擇：**
   - **Whisper CLI：** 預設方案（已整合 openai-whisper skill）
   - **Moonshine：** 備用方案（輕量、快速）
   - **Qwen3-ASR：** 中文優化（簡→繁轉換）

---

**最後更新:** 2026-03-21  
**計畫狀態:** Phase 1 ✅ 完成，Phase 2 ✅ 完成，Phase 3 ⏳ 進行中  
**預計工時:** 65 小時（Phase 1-2 已完成，Phase 3 預估 23 小時）
