# 🏥 SoapVoice 專案執行計畫書 (OpnusPlan.md)

## Medical Voice-to-SOAP Conversion System

**版本管理:** uv (Python package & environment manager)
**最後更新:** 2026-03-13
**專案狀態:** 🟢 Phase 5 Completed - Ready for Deployment
**文件版本:** v0.9.0

---

## 1️⃣ 執行摘要 (Executive Summary)

### 🎯 專案願景

建立一套基於本地 LLM 的醫療語音轉 SOAP 病歷系統，實現：

- 🎤 即時多語語音輸入（中文、英文）
- 🧠 AI 驅動的醫療語意標準化與術語專業化
- 📋 結構化 SOAP 病歷自動產出
- 📊 ICD-10 診斷代碼映射與專科分類
- 🔐 內網專用安全部署（192.168.x.x）

### 📊 專案規模

| 項目 | 規格 |
|------|------|
| **前端整合** | doctor-toolbox.com |
| **部署環境** | 內網專用（192.168.x.x） |
| **硬體資源** | Ryzen 9 5950X, 48GB RAM, 44GB VRAM |
| **主要技術棧** | FastAPI, Faster-Whisper, Qwen3-32B, GLM-4.7-Flash |
| **開發週期** | 16 週（3.7 個月） |
| **團隊規模** | 4-5 人 + Claude Code AI 協作 |
| **預算** | $0（全開源方案） |

### 🎯 核心目標 (Core Objectives)

1. **準確性目標**: ASR 醫療詞彙辨識率 ≥95%、SOAP 分類 ≥92%
2. **效能目標**: 端到端處理延遲 <3 秒、API 回應 <500ms
3. **可靠性目標**: 系統可用性 ≥99.5%、平均恢復時間 <30min
4. **安全性目標**: 符合醫療資料保護規範（內網部署 + 認證 + 加密）
5. **可擴展性**: 支援未來多專科模組擴充與國際化

### 💡 價值主張

- **醫師效率提升**: 減少 60-80% 病歷撰寫時間（8-10min → 3-4min）
- **品質提升**: 標準化醫療術語，減少錯誤和歧義
- **資料結構化**: 利於後續醫療數據分析與統計
- **成本控制**: 本地部署，無雲端 API 費用，完全開源技術棧
- **患者隱私**: 所有資料保留在內網，不涉及外部傳輸

---

## 2️⃣ 開發階段與里程碑 (Development Phases & Milestones)

### 🏗️ Phase 0: 專案準備期 (Week 1-2)

**里程碑: M0 - Project Foundation**

**完成標準:** ✅ 所有基礎設施就緒，開發環境可用

| 任務 | 負責人 | 預估時間 | 依賴項 |
|------|--------|----------|--------|
| 硬體環境測試 | DevOps | 2 days | - |
| GPU 驅動與 CUDA 安裝 | DevOps | 1 day | 硬體環境 |
| uv 環境建置 | Backend Dev | 1 day | - |
| Git repository 設定 | Tech Lead | 0.5 day | - |
| Docker 環境準備 | DevOps | 2 days | - |
| 文件架構確認 | All | 1 day | - |

**可交付成果 (Deliverables):**
- ✅ `pyproject.toml` with uv configuration
- ✅ `.gitignore` and repository structure
- ✅ Docker base images
- ✅ Hardware benchmark report
- ✅ Development environment setup guide

---

### 🏗️ Phase 1: 核心模型部署 (Week 3-5)

**里程碑: M1 - LLM Infrastructure Ready**

**完成標準:** ✅ 所有 AI 模型可獨立運行並通過基準測試

#### 1.1 ASR 模型部署 (Faster-Whisper)

| 任務 | 技術規格 | 驗收標準 |
|------|----------|----------|
| Faster-Whisper large-v3 安裝 | FP16, GPU1 (8GB) | WER <5% on medical test set |
| 醫療詞彙優化 | Custom vocabulary injection | 正確辨識 90% 醫療專有名詞 |
| Streaming pipeline 建置 | WebSocket + VAD | Latency <500ms (95th percentile) |
| 多語言測試 | Mandarin + English | Code-switching 支援 ✅ |

#### 1.2 LLM 模型部署

| 模型 | 用途 | 精度 | VRAM | 延遲目標 | 狀態 |
|------|------|------|------|----------|------|
| **Qwen3-32B-Instruct** | 主推理引擎 | FP16 | 36-40GB | <2s | 主力 |
| **GLM-4.7-Flash** | Fast routing (簡單案例) | FP16 | <10GB | <400ms | 備用 |

**技術實作:**

```python
# uv managed dependencies example
# pyproject.toml
[project]
dependencies = [
    "faster-whisper>=1.0.0",
    "vllm>=0.6.0",
    "transformers>=4.45.0",
    "torch>=2.1.0",
    "fastapi>=0.115.0",
]

[tool.uv]
python = "3.11"
```

**可交付成果:**
- ✅ Model inference benchmarks
- ✅ GPU memory profiling report
- ✅ Model serving API (vLLM + OpenAI API format)
- ✅ Load testing results (10+ concurrent requests)

---

### 🏗️ Phase 2: Clinical NLP Engine (Week 6-8)

**里程碑: M2 - Normalization Engine Operational**

#### 2.1 醫療語意標準化模組

| 功能模組 | 輸入 | 輸出 | 資料來源 | 準確率目標 |
|----------|------|------|----------|------------|
| **Typo Correction** | Raw ASR text | Corrected text | Custom dictionary | ≥95% |
| **Synonym Mapping** | 口語中文 | Medical English | clinic-promot.md table | ≥95% |
| **ICD-10 Mapping** | 症狀描述 | ICD-10 code | WHO ICD database | ≥85% |
| **SOAP Classification** | 句子 | S/O/A/P label | Keyword-based rules | ≥90% |
| **Specialty Detection** | 症狀集合 | Medical specialty | Rule-based + ML | ≥85% |

#### 2.2 Pipeline 設計範例

```
Input: "病人說他胸悶兩天還有點喘"
  ↓ [Typo Correction]
"病人說他胸悶兩天還有點喘" (no change)
  ↓ [Synonym Mapping]
"chest tightness for 2 days with dyspnea"
  ↓ [ICD-10 Mapping]
R07.89 (chest pain), R06.02 (shortness of breath)
  ↓ [SOAP Classification]
[Subjective]
  ↓ [Specialty Detection]
Cardiology / Pulmonology
```

**可交付成果:**
- ✅ Normalization engine module (Python package)
- ✅ Medical terminology database (SQLite)
- ✅ Unit tests (coverage ≥80%)
- ✅ Performance benchmark

---

### 🏗️ Phase 3: FastAPI Backend (Week 9-11)

**里程碑: M3 - API Gateway Production Ready**

#### 3.1 API Endpoints 設計

**Endpoint 1: `/api/v1/voice/stream` (WebSocket)**

功能: 即時語音串流轉錄

```json
// Request
{
  "audio_format": "pcm_s16le",
  "sample_rate": 16000,
  "language": "auto"
}

// Response (streaming)
{
  "type": "transcript",
  "text": "病人說胸悶",
  "is_final": false,
  "confidence": 0.92
}
```

**Endpoint 2: `/api/v1/clinical/normalize` (REST)**

功能: 醫療文本標準化

```json
// Request
{
  "text": "我胸悶兩天還有點喘",
  "context": {
    "specialty": "general",
    "language": "zh-TW"
  }
}

// Response
{
  "normalized": [
    {
      "original": "胸悶",
      "standard": "chest tightness",
      "icd10": "R07.89",
      "specialty": ["cardiology", "pulmonology"],
      "soap_category": "subjective",
      "severity": "moderate",
      "confidence": 0.95
    }
  ],
  "routing_decision": "complex",
  "model_used": "qwen3-32b",
  "processing_time_ms": 1823
}
```

**Endpoint 3: `/api/v1/soap/generate` (REST)**

功能: 完整 SOAP 病歷生成

```json
// Request
{
  "transcript": "病人胸悶兩天伴隨呼吸困難",
  "patient_context": {
    "age": 45,
    "gender": "M",
    "chief_complaint": "chest pain"
  }
}

// Response
{
  "soap": {
    "subjective": "45-year-old male with chest tightness for 2 days, accompanied by dyspnea",
    "objective": "BP: 135/85, HR: 92, RR: 20",
    "assessment": "R07.89 - Chest pain, unspecified\nR06.02 - Shortness of breath",
    "plan": "Further cardiac workup pending; patient advised to seek immediate care if symptoms worsen"
  },
  "conversation_summary": "病患主訴胸悶兩天伴隨呼吸困難，需進一步心臟工作檢查。",
  "metadata": {
    "confidence": 0.93,
    "processing_time_ms": 2145,
    "model_version": "qwen3-32b-20260220"
  }
}
```

#### 3.2 安全與認證

| 功能 | 實作方式 | 優先級 | 說明 |
|------|----------|--------|------|
| **API Key 驗證** | Header-based (X-API-Key) | P0 | 基礎認證 |
| **JWT Token** | OAuth2 + Bearer token | P1 | 進階認證 |
| **Rate Limiting** | Redis-based throttling | P0 | 防 DDoS |
| **IP Whitelisting** | 192.168.x.x only | P0 | 內網限制 |
| **Audit Logging** | Structured JSON logs | P0 | 法規遵循 |
| **HTTPS** | Nginx + Let's Encrypt | P1 | 傳輸加密 |

**可交付成果:**
- ✅ FastAPI application with all endpoints
- ✅ API documentation (OpenAPI/Swagger)
- ✅ Authentication middleware
- ✅ Integration tests (≥70% coverage)
- ✅ Performance tests (≥100 req/s)

---

### 🏗️ Phase 4: Frontend Integration (Week 12-13)

**里程碑: M4 - doctor-toolbox.com Integration**

#### 4.1 Frontend Requirements

| 功能 | 技術規格 | UI/UX 需求 |
|------|----------|------------|
| **語音錄製** | WebRTC AudioContext | 一鍵開始/停止，視覺反饋 |
| **即時轉文字** | WebSocket display | 即時顯示 ASR 結果 |
| **SOAP 預覽** | Real-time preview | S/O/A/P 分段顯示 |
| **編輯功能** | Manual correction | 可手動調整 SOAP，自動儲存 |
| **歷史記錄** | Session persistence | 儲存最近 10 筆對話 |

#### 4.2 API Integration Example

```javascript
// Frontend WebSocket connection
const ws = new WebSocket('ws://192.168.x.x:8000/api/v1/voice/stream');

ws.onopen = () => {
  console.log('Connected to SoapVoice API');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'transcript') {
    updateTranscriptDisplay(data.text);
  } else if (data.type === 'soap') {
    updateSOAPPreview(data.soap);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  showErrorNotification('Connection failed');
};
```

**可交付成果:**
- ✅ JavaScript SDK for doctor-toolbox
- ✅ UI components for voice recording
- ✅ SOAP editor component
- ✅ Integration testing with backend

---

### 🏗️ Phase 5: Testing & Optimization (Week 14-15)

**里程碑: M5 - Production Quality Achieved**

#### 5.1 測試策略

| 測試類型 | 覆蓋率目標 | 工具 | 預估工時 |
|----------|------------|------|----------|
| **Unit Tests** | ≥80% | pytest | 40h |
| **Integration Tests** | ≥70% | pytest + httpx | 32h |
| **Load Tests** | 100 concurrent users | locust | 16h |
| **Medical Accuracy** | ≥95% on test set | Custom eval | 24h |
| **Security Tests** | OWASP Top 10 | bandit, safety | 16h |

#### 5.2 效能優化目標

| 優化項目 | 現況 | 目標 | 優化方法 |
|----------|------|------|----------|
| ASR Latency | TBD | <500ms (95th %ile) | GPU optimization, batching |
| LLM Inference | TBD | <2s (95th %ile) | vLLM tuning, prompt caching |
| API Response | TBD | <3s (95th %ile) | Caching, parallel processing |
| GPU Memory | TBD | <42GB (peak) | Model quantization, efficient loading |
| Throughput | TBD | ≥50 req/s | Load balancing, connection pooling |

**可交付成果:**
- ✅ Test suite (all passing)
- ✅ Performance report with metrics
- ✅ Security audit report
- ✅ Optimization recommendations

---

### 🏗️ Phase 6: Deployment & Monitoring (Week 16)

**里程碑: M6 - Production Deployment**

#### 6.1 部署架構

```
┌─────────────────────────────────────────┐
│ Nginx Reverse Proxy (192.168.x.x:443)  │
│  - SSL Termination                      │
│  - Load Balancing (Round-robin)         │
│  - Rate Limiting (100 req/min per IP)   │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐    ┌────▼─────┐   ┌────▼─────┐
│FastAPI │    │FastAPI   │   │FastAPI   │
│Instance│    │Instance  │   │Instance  │
│  #1    │    │  #2      │   │  #3      │
└────────┘    └──────────┘   └──────────┘
    │               │               │
    └───────────────┼───────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐    ┌────▼─────┐   ┌────▼─────┐
│ GPU0:  │    │ GPU1:    │   │ Redis:   │
│Qwen3   │    │Whisper   │   │Cache     │
│-32B    │    │large-v3  │   │Session   │
└────────┘    └──────────┘   └──────────┘
    │               │               │
    └───────────────┼───────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
    ┌───▼─────┐         ┌──────▼────┐
    │PostgreSQL       │ File System │
    │User/Session     │ Logs/Cache  │
    └───────────┘     └────────────┘
```

#### 6.2 監控指標

| 指標類型 | 工具 | Alert 條件 | 目標值 |
|----------|------|------------|--------|
| **System Metrics** | Prometheus | GPU >95%, RAM >90% | Normal <60% |
| **Application Metrics** | Grafana | Error rate >1% | <0.1% |
| **Business Metrics** | Custom Dashboard | Accuracy <90% | ≥92% |
| **Logs** | Loki | Error logs | Zero critical errors |
| **Traces** | Jaeger | Latency >5s | 95th %ile <3s |

**可交付成果:**
- ✅ Docker Compose production config
- ✅ Monitoring dashboards (Prometheus + Grafana)
- ✅ Deployment runbook (step-by-step guide)
- ✅ Disaster recovery plan

---

## 3️⃣ 功能分解與優先級 (Feature Breakdown)

### 🎯 功能分類 (MoSCoW Method)

#### Must Have (P0) - MVP 必要功能

**Total MVP Effort: ~224 hours (6-8 weeks)**

| ID | 功能 | 描述 | 複雜度 | 預估工時 | 優先級 |
|----|------|------|--------|----------|--------|
| F001 | **即時語音辨識** | Faster-Whisper integration | High | 40h | P0 |
| F002 | **SOAP 自動分類** | Keyword-based S/O/A/P routing | Medium | 32h | P0 |
| F003 | **醫療術語標準化** | Synonym mapping (clinic-promot.md table) | Medium | 24h | P0 |
| F004 | **LLM 推理引擎** | Qwen3-32B API service | High | 48h | P0 |
| F005 | **FastAPI Gateway** | REST + WebSocket endpoints | Medium | 40h | P0 |
| F006 | **基礎認證** | API Key validation | Low | 16h | P0 |
| F007 | **SOAP JSON 輸出** | Structured output format | Low | 16h | P0 |
| F008 | **繁體中文摘要** | Conversation summary generation | Low | 8h | P0 |

---

#### Should Have (P1) - 重要但非緊急

**Total P1 Effort: ~168 hours (4-5 weeks)**

| ID | 功能 | 描述 | 複雜度 | 預估工時 | 優先級 |
|----|------|------|--------|----------|--------|
| F101 | **ICD-10 自動映射** | WHO ICD database integration | Medium | 32h | P1 |
| F102 | **專科自動分類** | Specialty detection module | Medium | 24h | P1 |
| F103 | **Routing Model** | GLM-4.7-Flash fast path | Medium | 24h | P1 |
| F104 | **錯字自動修正** | Levenshtein + fuzzy matching | Medium | 20h | P1 |
| F105 | **JWT 認證** | OAuth2 flow | Medium | 24h | P1 |
| F106 | **Rate Limiting** | Redis-based throttling | Low | 16h | P1 |
| F107 | **Audit Logging** | Structured JSON logs | Low | 12h | P1 |
| F108 | **History Management** | Session persistence | Low | 16h | P1 |

---

#### Could Have (P2) - 錦上添花

**Total P2 Effort: ~264 hours (6-8 weeks) - 未來版本**

| ID | 功能 | 描述 | 複雜度 | 預估工時 |
|----|------|------|--------|----------|
| F201 | **SNOMED CT 映射** | Clinical terminology standard | High | 40h |
| F202 | **RxNorm 藥物庫** | Medication normalization | High | 40h |
| F203 | **Differential Diagnosis** | Multiple diagnosis suggestions | Very High | 80h |
| F204 | **語音情緒分析** | Sentiment detection | Medium | 32h |
| F205 | **多使用者管理** | Role-based access control (RBAC) | Medium | 32h |
| F206 | **匯出功能** | PDF/DOCX export | Low | 16h |
| F207 | **統計分析儀表板** | Usage analytics & insights | Medium | 24h |

---

#### Won't Have (此版本不做) ❌

- ❌ 雲端部署（AWS/GCP/Azure）
- ❌ 行動 App（iOS/Android）
- ❌ 多語言 UI（僅繁體中文）
- ❌ Real-time collaboration（單人使用）
- ❌ EHR/EMR 系統整合（Phase 2）

---

## 4️⃣ 技術架構決策 (Architecture Decisions)

### ⚙️ Architecture Decision Records (ADRs)

#### ADR-001: 選擇 FastAPI 而非 Flask/Django

**決策日期:** 2026-02-26
**狀態:** ✅ Accepted

**背景:** 需要高效能、非同步、支援 WebSocket 的 API 框架

**選項評估:**

| 框架 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **FastAPI** | 原生 async, 自動文件, type hints, WebSocket | 較新,生態較小 | ⭐⭐⭐⭐⭐ |
| Flask | 成熟,生態豐富 | 同步, 需額外擴充 | ⭐⭐⭐ |
| Django | 全功能, ORM | 過重, 非同步支援差 | ⭐⭐ |

**決策:** 選擇 FastAPI
**理由:** 原生支援 WebSocket 串流、自動 OpenAPI 文件、效能優異

---

#### ADR-002: 使用 Faster-Whisper 而非 OpenAI Whisper

**決策日期:** 2026-02-26
**狀態:** ✅ Accepted

**背景:** 需要本地部署、低延遲的語音辨識引擎

**選項評估:**

| 方案 | RTF (Real-Time Factor) | VRAM | 準確率 | 評分 |
|------|------------------------|------|--------|------|
| **Faster-Whisper** | 0.15-0.3 | 6-8GB | 95%+ | ⭐⭐⭐⭐⭐ |
| OpenAI Whisper | 0.5-1.0 | 10-11GB | 96%+ | ⭐⭐⭐⭐ |
| Vosk | 0.1 | 2GB | 85%+ | ⭐⭐⭐ |
| DeepSpeech | 0.2 | 3GB | 80%+ | ⭐⭐ |

**決策:** 選擇 Faster-Whisper
**理由:** 效能與準確率平衡最佳，支援串流推理，VRAM 效率高

---

#### ADR-003: Qwen3-32B FP16 vs 量化版本

**決策日期:** 2026-02-26
**狀態:** ✅ Accepted

**背景:** 44GB VRAM 可支援不同精度的 32B 模型

**選項評估:**

| 配置 | VRAM | 推理速度 | 準確率 | 評分 |
|------|------|----------|--------|------|
| **FP16 全精度** | 36-40GB | 1.5-2s | 100% | ⭐⭐⭐⭐⭐ |
| Q8 量化 | 20-24GB | 1.2-1.8s | 99% | ⭐⭐⭐⭐ |
| Q4 量化 | 12-16GB | 0.8-1.2s | 95% | ⭐⭐⭐ |

**決策:** 選擇 FP16 全精度
**理由:** 硬體資源充足，醫療準確性優先於速度，確保診斷可靠性

---

#### ADR-004: 使用 uv 而非 pip/poetry

**決策日期:** 2026-02-26
**狀態:** ✅ Accepted

**背景:** 需要快速、可靠的 Python 依賴管理工具

**選項評估:**

| 工具 | 安裝速度 | Lock file | 易用性 | 評分 |
|------|----------|-----------|--------|------|
| **uv** | 10-100x faster | ✅ | High | ⭐⭐⭐⭐⭐ |
| poetry | Slow | ✅ | High | ⭐⭐⭐⭐ |
| pip | Fast | ❌ | Medium | ⭐⭐⭐ |
| conda | Very slow | ❌ | Low | ⭐⭐ |

**決策:** 選擇 uv
**理由:** 符合使用者需求，速度最快，相容性好，Rust 實作保證可靠性

---

#### ADR-005: WebSocket vs HTTP Streaming vs gRPC

**決策日期:** 2026-02-26
**狀態:** ✅ Accepted

**背景:** 即時語音串流需要雙向通訊協定

**選項評估:**

| 協定 | 延遲 | 瀏覽器支援 | 實作複雜度 | 評分 |
|------|------|------------|------------|------|
| **WebSocket** | Low | ✅ | Low | ⭐⭐⭐⭐⭐ |
| HTTP Streaming | Medium | ✅ | Medium | ⭐⭐⭐⭐ |
| gRPC | Very Low | ❌ (需proxy) | High | ⭐⭐⭐ |

**決策:** 選擇 WebSocket
**理由:** 瀏覽器原生支援，延遲低，實作簡單，不需額外轉換層

---

### 🏛️ 系統架構設計 (System Architecture)

#### Layer 1: Presentation Layer
```
doctor-toolbox.com Frontend (Vue.js/React)
├── Voice Recording Component
├── Real-time Transcript Display
├── SOAP Editor (S/O/A/P sections)
└── History Management
```

#### Layer 2: API Gateway Layer
```
FastAPI Application (3 instances for load balancing)
├── /api/v1/voice/stream (WebSocket)
├── /api/v1/clinical/normalize (REST POST)
├── /api/v1/soap/generate (REST POST)
├── /api/v1/health (Health check)
├── Authentication Middleware (API Key + JWT)
├── Rate Limiting Middleware (100 req/min per IP)
└── Logging & Monitoring Middleware
```

#### Layer 3: Business Logic Layer
```
Clinical NLP Engine
├── Typo Correction Module (Levenshtein distance)
├── Synonym Mapping Module (dict-based)
├── ICD-10 Mapping Module (database lookup)
├── SOAP Classification Module (keyword-based)
├── Specialty Detection Module (rule-based)
└── LLM Routing Module (complexity assessment)
```

#### Layer 4: AI Model Layer
```
GPU Infrastructure (44GB VRAM total)
├── GPU0 (22GB): Qwen3-32B-Instruct (vLLM)
│   └── Tensor Parallel = 1 (single GPU)
├── GPU1 (8GB): Faster-Whisper large-v3 (CTranslate2)
│   └── Batch size = 8
└── Optional GPU2: GLM-4.7-Flash for fast routing
```

#### Layer 5: Data Layer
```
Persistence & Cache
├── PostgreSQL: User/Session data, conversation history
├── Redis: Cache (LRU), Rate limiting counters, Session store
├── SQLite: Medical terminology database, ICD-10 codes
└── File System: Audio logs (optional, encrypted), monitoring data
```

---

### 🔧 Technology Stack Summary

| 層次 | 技術 | 版本 | 用途 |
|------|------|------|------|
| **語音辨識** | Faster-Whisper | v1.0+ | ASR engine |
| **主推理模型** | Qwen3-32B-Instruct | Latest | Medical reasoning |
| **Fast Routing** | GLM-4.7-Flash | Latest | Simple cases |
| **API 框架** | FastAPI | 0.115+ | REST + WebSocket |
| **LLM Serving** | vLLM | 0.6+ | Model inference optimization |
| **依賴管理** | uv | Latest | Package management |
| **資料庫** | PostgreSQL | 16+ | Structured data (users, sessions) |
| **快取層** | Redis | 7+ | Cache & rate limiting |
| **反向代理** | Nginx | 1.24+ | Load balancing, SSL |
| **監控指標** | Prometheus | Latest | Time-series metrics |
| **監控可視化** | Grafana | Latest | Dashboards |
| **容器化** | Docker/Compose | Latest | Deployment |
| **Python Runtime** | Python | 3.11+ | Application runtime |

---

## 5️⃣ 時程與資源分配 (Timeline & Resources)

### 📅 專案時程 (16 Weeks)

```
2026-03-01 ──────────────────────────────────────── 2026-06-20
│         │           │           │           │           │
W1   W2   W3    W4   W5  W6    W7   W8   W9   W10 W11 W12 W13 W14 W15 W16
│    │    │     │    │   │     │    │    │    │   │   │   │   │   │   │
└─ P0 ─┴─ P1 ─────┴─ P2 ──┴─ P3 ──────┴─ P4 ┴─ P5 ┴─ P6 ┘
 2w   3w   3w   3w   2w   2w   1w
```

### 👥 團隊角色與職責

| 角色 | 人數 | 主要職責 | 關鍵技能 | 投入比例 |
|------|------|----------|----------|----------|
| **Tech Lead** | 1 | 架構設計、技術決策、code review | Python, LLM, System Design | 100% |
| **Backend Dev** | 1-2 | FastAPI 開發、AI 整合、API design | FastAPI, vLLM, Docker | 100% |
| **Medical NLP Engineer** | 1 | 醫療語意處理、規則引擎、資料庫 | NLP, Medical domain, SQL | 80% |
| **Frontend Dev** | 1 | doctor-toolbox 整合、UI components | JavaScript, WebSocket, React | 60% |
| **DevOps Engineer** | 0.5 | 部署、監控、維運、GPU 管理 | Docker, Nginx, GPU, K8s | 50% |
| **QA Engineer** | 0.5 | 測試、品質保證、醫療驗證 | pytest, Locust, medical domain | 50% |
| **Claude Code AI** | - | 程式碼輔助、文件生成、重複工作自動化 | - | - |

**Total FTE:** 4-5 人，預期平均週工作 40-50 小時

---

### 💰 資源需求估算

#### 硬體資源 (已有)

| 項目 | 規格 | 數量 | 狀態 | 備註 |
|------|------|------|------|------|
| 主機 CPU | Ryzen 9 5950X (16C/32T) | 1 | ✅ Available | 算力充足 |
| RAM | 48GB DDR4 | 1 | ✅ Available | GPU VRAM 之外 |
| GPU VRAM | 44GB (total) | 1-2 | ✅ Available | GPU0: 22GB, GPU1: 8GB |
| 儲存 | SSD ≥1TB NVMe | 1 | ⏳ 待確認 | 需驗證容量 |
| 網路 | 內網 192.168.x.x | - | ✅ Available | 1Gbps+ |

#### 軟體資源成本

| 項目 | 費用 | 週期 | 備註 |
|------|------|------|------|
| GitHub | $0 | - | Free tier or private repo |
| Docker Hub | $0 | - | Free tier |
| Monitoring (Grafana Cloud) | $0 | - | Free tier |
| 模型授權 | $0 | - | Qwen3/GLM 商用免費 |
| AI 輔助 (Claude Code) | 已購 | - | 包含在現有訂閱中 |

**Total 額外成本:** **$0**（全開源、內部資源）

---

### 📆 詳細時程表 (Week-by-Week)

#### **Week 1-2: Phase 0 專案準備期**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W1 | 03/01-03/07 | 環境設置、硬體測試 | Dev environment ready, hardware benchmark | DevOps + Tech Lead |
| W2 | 03/08-03/14 | Docker 配置、文件架構 | Project structure, docker base images | DevOps + All |

---

#### **Week 3-5: Phase 1 核心模型部署**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W3 | 03/15-03/21 | Faster-Whisper 部署 | ASR working, WER <5% | Backend Dev + DevOps |
| W4 | 03/22-03/28 | Qwen3-32B vLLM setup | LLM inference API, <2s latency | Backend Dev |
| W5 | 03/29-04/04 | 模型優化與測試 | Benchmark report, load test pass | Tech Lead + QA |

---

#### **Week 6-8: Phase 2 Clinical NLP Engine**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W6 | 04/05-04/11 | 醫療術語映射資料庫 | Terminology DB, synonym mapping | NLP Engineer |
| W7 | 04/12-04/18 | SOAP 分類引擎 | Classification module, unit tests | NLP Engineer + Backend Dev |
| W8 | 04/19-04/25 | ICD-10 整合 | ICD mapping API, accuracy ≥85% | NLP Engineer |

---

#### **Week 9-11: Phase 3 FastAPI Backend**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W9 | 04/26-05/02 | API endpoints 實作 | REST APIs working, OpenAPI docs | Backend Dev |
| W10 | 05/03-05/09 | WebSocket 串流 | Streaming working, real-time tests | Backend Dev |
| W11 | 05/10-05/16 | 認證與安全 | Auth middleware, rate limiting | Backend Dev + Tech Lead |

---

#### **Week 12-13: Phase 4 Frontend Integration**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W12 | 05/17-05/23 | doctor-toolbox 整合 | UI components, voice recording | Frontend Dev |
| W13 | 05/24-05/30 | 端到端測試 | Integration working, E2E tests pass | Frontend Dev + QA |

---

#### **Week 14-15: Phase 5 Testing & Optimization**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W14 | 05/31-06/06 | 完整測試 | Test suite passing, coverage ≥80% | QA + All |
| W15 | 06/07-06/13 | 效能優化 | Performance report, optimization done | Tech Lead + Backend Dev |

---

#### **Week 16: Phase 6 Deployment & Monitoring**

| Week | 日期 | 主要任務 | 可交付成果 | 負責人 |
|------|------|----------|------------|--------|
| W16 | 06/14-06/20 | 正式部署與上線 | Production live, monitoring active | DevOps + All |

---

### 🎯 里程碑檢核表

| Milestone | 目標日期 | 驗收標準 | 負責人 | 狀態 |
|-----------|----------|----------|--------|------|
| **M0:** Project Setup | W2 (03/14) | 環境可用，文件架構確認 | Tech Lead | ⏳ Pending |
| **M1:** LLM Ready | W5 (04/04) | ASR WER <5%、推理 <2s、GPU 穩定 <42GB | Backend Dev | ⏳ Pending |
| **M2:** NLP Engine | W8 (04/25) | 術語轉換 ≥95%、SOAP 分類 ≥90% | NLP Engineer | ⏳ Pending |
| **M3:** API Gateway | W11 (05/16) | API 文件完整、load test 100 req/s | Backend Dev | ⏳ Pending |
| **M4:** Integration | W13 (05/30) | Frontend 可用、5 位醫師 beta test | Frontend Dev | ⏳ Pending |
| **M5:** Quality | W15 (06/13) | 測試覆蓋 ≥80%、安全審核通過 | QA + Tech Lead | ⏳ Pending |
| **M6:** Deployment | W16 (06/20) | Production live、monitoring active | DevOps | ⏳ Pending |

---

## 6️⃣ 風險評估與因應 (Risk Assessment & Mitigation)

### ⚠️ 風險矩陣 (Risk Matrix)

```
高影響 │ [R3] │ [R1] │
      │      │  ⚠️  │
───────┼──────┼──────┤
中影響 │ [R5] │ [R2] │
      │  ⚠️  │  ⚠️  │
───────┼──────┼──────┤
低影響 │ [R6] │ [R4] │
      │      │      │
───────┴──────┴──────┴
      低機率  高機率
```

---

### 🔴 高優先級風險 (High Priority)

#### [R1] 模型準確率不足 (醫療專業性)

**影響:** 高 | **機率:** 中 | **優先級:** 🔴 **P0**

**風險描述:**
Qwen3-32B 雖強大，但可能在特定醫療專科領域表現不佳，導致 SOAP 分類錯誤或術語轉換不準確。

**影響範圍:**
- 醫療文書品質下降 → 醫師不信任系統
- 需手動大量修正 → 時間節省效果不佳
- 可能導致診斷錯誤 → 法律責任風險

**緩解策略:**

| 策略 | 方式 | 負責人 | 時程 | 成本 |
|------|------|--------|------|------|
| **Domain Fine-tuning** | 收集 1000+ 醫療對話做 LoRA fine-tune | NLP Engineer | W6-W8 | Medium |
| **Rule-based Fallback** | 關鍵醫療術語使用規則優先 | Backend Dev | W7 | Low |
| **Human-in-the-loop** | 提供編輯功能，收集回饋用於改進 | Frontend Dev | W12 | Low |
| **Multi-model Ensemble** | 使用 GLM + Qwen 交叉驗證 | Tech Lead | W10 | High |
| **醫師專家協助** | 邀請醫師進行 prompt engineering | All | W6-W7 | Low |

**偵測指標:**
- 醫療術語轉換準確率 <90%
- SOAP 分類錯誤率 >10%
- 醫師手動修正率 >30%
- 醫療專科測試集準確率 <85%

**應變計畫:**
1. 優先修正高頻詞彙的映射規則
2. 建立醫療專有名詞白名單（強制規則匹配）
3. 邀請 3-5 位醫師專家進行深度 prompt engineering
4. 若仍無法達標，考慮切換至醫療專用模型（如 BioMedLM）
5. 增加 human-in-the-loop 反饋迴圈

---

#### [R2] GPU 記憶體不足或效能瓶頸

**影響:** 高 | **機率:** 中 | **優先級:** 🟠 **P1**

**風險描述:**
Qwen3-32B FP16 (36-40GB) + Whisper large-v3 (8GB) 同時運行可能超過 44GB VRAM，或推理速度無法滿足 <3s 目標。

**影響範圍:**
- 系統無法啟動或頻繁 OOM
- 推理延遲過長（>5s） → 使用者體驗差
- 無法支援多並發請求 → 吞吐量不足

**緩解策略:**

| 策略 | 方式 | 負責人 | 時程 |
|------|------|--------|------|
| **Memory Profiling** | 詳細測量各模型 VRAM 使用，找出瓶頸 | DevOps | W3 |
| **Model Quantization** | 準備 Q8/Q4 備用版本 | Backend Dev | W4 |
| **GPU Isolation** | 使用 CUDA_VISIBLE_DEVICES 分離 GPU0/GPU1 | DevOps | W5 |
| **Request Queue** | 實作請求隊列避免 OOM | Backend Dev | W9 |
| **Caching** | LRU cache for common patterns | Backend Dev | W10 |
| **Batching** | 優化 batch size，提升吞吐 | Backend Dev | W5 |

**偵測指標:**
- GPU memory >95% 時發出警告
- Inference latency >3s (95th %ile)
- 出現 CUDA OOM errors
- Concurrent request limit <5

**應變計畫:**
1. 立即切換至 Q8 量化版本（準確率損失 <1%，速度提升 20-30%）
2. 實作動態模型載入/卸載
3. 啟用 GLM-4.7-Flash 作為快速路由，只有複雜案例才用 Qwen3
4. 考慮購買額外 GPU 或升級至 80GB 顯卡（預備方案）
5. 實作 GPU 記憶體動態回收機制

---

### 🟡 中優先級風險 (Medium Priority)

#### [R3] ASR 醫療詞彙辨識錯誤

**影響:** 高 | **機率:** 低 | **優先級:** 🟡 **P2**

**風險描述:**
Faster-Whisper 在醫療專有名詞（如藥物名稱、罕見疾病）辨識率可能不佳，導致 ASR 基礎質量差。

**緩解策略:**
- 建立 500+ 醫療詞彙 hotword list
- 使用 post-ASR 錯字修正模組（Levenshtein distance）
- 訓練醫療領域 acoustic adapter（可選）

---

#### [R5] 開發時程延遲

**影響:** 中 | **機率:** 中 | **優先級:** 🟡 **P2**

**風險描述:**
16 週時程可能因技術難題、資源不足而延誤，特別是 Phase 1 和 Phase 5。

**緩解策略:**
- 每兩週 sprint review + retrospective
- 預留 20% buffer time (實際分配: 3.2 週)
- MVP 優先，P1/P2 feature 可延後至 v0.2
- 每週監控進度，及早發現偏差
- 彈性調整團隊資源配置

---

#### [R4] 版本依賴衝突

**影響:** 中 | **機率:** 中 | **優先級:** 🟡 **P2**

**風險描述:**
Python 生態複雜，PyTorch/Transformers/vLLM 版本升級可能導致衝突。

**緩解策略:**
- 使用 uv lock file，確保可重現性
- Docker 容器化隔離，避免系統污染
- CI/CD 自動化測試，每次 commit 驗證依賴
- 定期（每月）更新安全漏洞，不追求最新版本

---

### 🟢 低優先級風險 (Low Priority)

#### [R6] 網路或硬體故障

**影響:** 低 | **機率:** 低 | **優先級:** 🟢 **P3**

**風險描述:**
電源故障、冷卻系統故障、磁碟損毀等。

**緩解策略:**
- 定期備份（每日 PostgreSQL dump，每日 Redis RDB）
- UPS 不斷電系統（預算許可）
- RAID-1 磁碟備份（推薦）
- 監控系統溫度和健康狀態

---

## 7️⃣ 成功指標與 KPI (Success Metrics & KPIs)

### 📈 KPI Dashboard (關鍵績效指標)

#### 🎯 技術指標 (Technical KPIs)

##### 1. 準確性指標 (Accuracy Metrics)

| 指標 | 目標值 | 測量方式 | 頻率 | 責任人 |
|------|--------|----------|------|--------|
| **ASR 詞錯率 (WER)** | <5% | 人工標註醫療測試集 | 每週 | QA |
| **醫療術語準確率** | ≥95% | 醫療詞彙測試集 | 每週 | NLP Engineer |
| **SOAP 分類準確率** | ≥92% | Expert (醫師) validation | 每月 | QA |
| **ICD-10 映射準確率** | ≥85% | 疾病代碼驗證 | 每月 | NLP Engineer |
| **整體醫療品質評分** | ≥4.2/5 | 醫師滿意度調查 | 每月 | QA |

---

##### 2. 效能指標 (Performance Metrics)

| 指標 | 目標值 | Alert 閾值 | 測量基礎 |
|------|--------|------------|----------|
| **ASR 延遲 (RTF)** | <0.3 | >0.5 | 95th percentile |
| **LLM 推理時間** | <2s | >3s | 95th percentile |
| **端到端延遲** | <3s | >5s | 90th percentile |
| **API 回應時間** | <500ms | >1s | 99th percentile |
| **系統 Throughput** | ≥50 req/s | <30 req/s | Sustained load |

---

##### 3. 可靠性指標 (Reliability Metrics)

| 指標 | 目標值 | 測量週期 | SLA |
|------|--------|----------|------|
| **系統可用性 (Uptime)** | ≥99.5% | 每月 | 43.8 小時/月 downtime |
| **錯誤率 (Error Rate)** | <1% | 每日 | <1 error per 100 requests |
| **平均恢復時間 (MTTR)** | <30min | Per incident | 自動告警+人工響應 |
| **GPU 利用率** | 60-85% | 即時 | 過低表示浪費，過高表示風險 |
| **記憶體使用率** | <90% | 即時 | >90% 需立即調查 |

---

##### 4. 資源指標 (Resource Metrics)

| 指標 | 正常範圍 | 警告閾值 | 危險閾值 |
|------|----------|----------|----------|
| **GPU VRAM 使用** | 30-40GB | >42GB | >43GB |
| **CPU 使用率** | 30-60% | >80% | >95% |
| **RAM 使用** | 20-35GB | >42GB | >46GB |
| **磁碟 I/O** | <50MB/s | >100MB/s | >200MB/s |

---

#### 💼 業務指標 (Business KPIs)

##### 5. 使用者體驗指標

| 指標 | 目標值 | 測量方式 | 頻率 |
|------|--------|----------|------|
| **醫師採用率** | ≥80% | Active users / Total users | 每月 |
| **每日活躍使用** | ≥50 sessions/day | Session logs | 每日 |
| **平均每次使用時長** | 5-10 min | Session duration | 每月 |
| **手動修正率** | <20% | Edit actions / Total | 每月 |
| **NPS (Net Promoter Score)** | ≥40 | 每季調查 | 每季 |

---

##### 6. 效率提升指標

| 指標 | Baseline | 目標改善 | 測量方式 |
|------|----------|----------|----------|
| **病歷撰寫時間** | 8-10 min | -60% (3-4 min) | 時間追蹤 |
| **每日處理病患數** | 20 人/day | +20% (24 人) | 工作量統計 |
| **文書工作時間占比** | 40% | -50% (20%) | 時間日誌 |

---

### 📊 測量與監控架構

#### Metrics Collection Stack

```
Application Layer (FastAPI)
  ├── Custom Metrics (Python decorators)
  │   ├── @track_latency
  │   ├── @track_accuracy
  │   └── @track_errors
  ↓
Prometheus Exporter (/metrics endpoint)
  ├── http_requests_total
  ├── http_request_duration_seconds (histogram)
  ├── llm_inference_duration_seconds
  ├── asr_latency_seconds
  ├── soap_classification_accuracy
  ├── medical_terminology_accuracy
  ↓
Prometheus Server (time-series database)
  ├── Data retention: 30 days
  ├── Alerting rules
  ├── Service discovery
  ↓
Visualization Layer
  ├── Grafana Dashboards
  │   ├── System Overview (CPU, RAM, GPU, Disk)
  │   ├── API Metrics (request rate, latency, error rate)
  │   ├── Model Performance (inference time, throughput)
  │   ├── Business Metrics (daily sessions, accuracy)
  │   └── SLA Dashboard (uptime, MTTR)
  └── Weekly/Monthly Reports (CSV export)
```

---

### 🎯 里程碑驗收標準 (Milestone Success Criteria)

#### **M1: LLM Infrastructure Ready (Week 5)**

✅ **必須通過條件:**

- [ ] Qwen3-32B inference <2s (95th percentile)
- [ ] Faster-Whisper ASR WER <5% on medical test set
- [ ] GPU memory usage stable <42GB peak
- [ ] 10+ concurrent requests without degradation
- [ ] Model serving API responds <500ms
- [ ] Health check endpoint returns 200 OK

#### **M2: Normalization Engine (Week 8)**

✅ **必須通過條件:**

- [ ] Medical terminology mapping accuracy ≥95%
- [ ] SOAP classification accuracy ≥90%
- [ ] ICD-10 mapping coverage ≥80% (for common conditions)
- [ ] Processing latency <300ms per request
- [ ] Unit test coverage ≥80%
- [ ] 0 critical bugs

#### **M3: API Gateway (Week 11)**

✅ **必須通過條件:**

- [ ] All API endpoints documented (OpenAPI)
- [ ] Authentication working (API key + JWT)
- [ ] Rate limiting enforced (100 req/min per IP)
- [ ] API response time <500ms (99th percentile)
- [ ] Load test: 100 req/s sustained for 5 min
- [ ] 0 unhandled exceptions

#### **M4: Integration (Week 13)**

✅ **必須通過條件:**

- [ ] doctor-toolbox frontend can record voice
- [ ] Real-time transcript display working
- [ ] SOAP output correctly formatted
- [ ] End-to-end latency <3s
- [ ] 5 physicians complete beta testing
- [ ] NPS ≥30 from beta testers

#### **M5: Production Quality (Week 15)**

✅ **必須通過條件:**

- [ ] Test coverage ≥80%
- [ ] Security audit passed (no critical issues)
- [ ] Performance benchmark met (all metrics green)
- [ ] Documentation complete (API docs, deployment guide)
- [ ] Disaster recovery tested & working
- [ ] 0 known critical bugs

#### **M6: Deployment (Week 16)**

✅ **必須通過條件:**

- [ ] Production deployment successful
- [ ] Monitoring dashboards live & alerting working
- [ ] 24hr uptime without critical incidents
- [ ] 10+ physicians actively using system
- [ ] Positive initial feedback (NPS ≥30)
- [ ] Runbook followed without issues

---

### 📉 紅線指標 (Red Line Metrics)

**若觸發以下條件，專案需緊急評估:**

| 紅線 | 觸發條件 | 行動 | 負責人 |
|------|----------|------|--------|
| **準確率崩潰** | SOAP accuracy <70% | 停止 rollout, code review | Tech Lead |
| **效能災難** | 95th latency >10s | 回滾至上一版本 | Backend Dev |
| **可靠性危機** | Uptime <95% for 3 days | 全員緊急修復 | All hands |
| **使用者抵制** | Adoption rate <30% after 1 month | 產品策略重新評估 | Tech Lead + PM |
| **安全漏洞** | Critical CVE discovered | 立即修補 + security audit | Tech Lead + DevOps |

---

### 📅 KPI Review Schedule

| 頻率 | 會議 | 參與者 | 重點指標 | 格式 |
|------|------|--------|----------|------|
| **每日** | Standup (15min) | Dev team | Error rate, latency, build status | Slack/Teams |
| **每週** | Sprint review (30min) | All | Milestone progress, tech metrics, blockers | Confluence/Wiki |
| **每月** | Business review (60min) | Lead + Stakeholders | Adoption, NPS, business impact, ROI | PowerPoint |
| **每季** | Strategic review (90min) | Management | Overall progress, future roadmap, risks | Board presentation |

---

## 8️⃣ 依賴關係與前置需求 (Dependencies & Prerequisites)

### 🔗 系統依賴圖 (Dependency Graph)

```
Hardware Setup
    ↓
GPU Drivers/CUDA 12.1+
    ↓
Docker + Docker Compose
    ↓
Python 3.11 + uv
    ├→ Faster-Whisper (ASR)
    ├→ vLLM + Qwen3 (LLM)
    └→ FastAPI backend
        ├→ PostgreSQL
        ├→ Redis
        └→ Nginx
            ↓
Clinical NLP Engine
    ↓
FastAPI Backend
    ↓
Frontend Integration
    ↓
Production Deployment
```

---

### ✅ Phase 0 前置需求檢查表

#### 硬體需求 (Hardware Prerequisites)

| 項目 | 最低需求 | 建議配置 | 當前狀態 | 檢查人 |
|------|----------|----------|----------|--------|
| **CPU** | 8C/16T | 16C/32T (Ryzen 9 5950X) | ✅ | - |
| **RAM** | 32GB | 48GB+ | ✅ | - |
| **GPU VRAM** | 40GB | 44GB+ | ✅ | - |
| **SSD 儲存** | 500GB | 1TB+ NVMe | ⏳ 待確認 | DevOps |
| **網路** | 1Gbps | 內網 192.168.x.x | ✅ | - |

---

#### 軟體前置需求 (Software Prerequisites)

| 項目 | 版本需求 | 安裝指令 | 驗證命令 | 狀態 |
|------|----------|----------|----------|------|
| **Ubuntu LTS** | 22.04+ | - | `lsb_release -a` | ⏳ 待確認 |
| **NVIDIA Driver** | ≥535 | `ubuntu-drivers install` | `nvidia-smi` | ⏳ 待測試 |
| **CUDA** | 12.1+ | `apt install cuda-toolkit-12-1` | `nvcc --version` | ⏳ 待安裝 |
| **cuDNN** | 8.9+ | Bundled with CUDA | Check CUDA dir | ⏳ 待安裝 |
| **Docker** | 24.0+ | `apt install docker.io` | `docker --version` | ⏳ 待安裝 |
| **Docker Compose** | 2.20+ | `apt install docker-compose-plugin` | `docker compose version` | ⏳ 待安裝 |
| **Python** | 3.11+ | `uv python install 3.11` | `python --version` | ⏳ 待安裝 |
| **uv** | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` | ⏳ 待安裝 |
| **Git** | 2.40+ | `apt install git` | `git --version` | ✅ |
| **Nginx** | 1.24+ | `apt install nginx` | `nginx -v` | ⏳ 待安裝 |

---

### 📦 Python 依賴項 (uv managed)

#### pyproject.toml 範例

```toml
[project]
name = "soapvoice"
version = "0.1.0"
description = "Medical Voice-to-SOAP Conversion System"
requires-python = ">=3.11"
authors = [
    {name = "SoapVoice Team", email = "team@soapvoice.local"}
]
dependencies = [
    # AI/ML Core
    "torch>=2.1.0",
    "transformers>=4.45.0",
    "faster-whisper>=1.0.0",
    "vllm>=0.6.0",

    # FastAPI Stack
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "websockets>=12.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.3.0",

    # Database
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis>=5.0.0",

    # NLP Tools
    "nltk>=3.8.0",
    "spacy>=3.7.0",
    "python-Levenshtein>=0.25.0",

    # Utilities
    "pyyaml>=6.0.0",
    "python-dotenv>=1.0.0",
    "tenacity>=8.5.0",

    # Monitoring
    "prometheus-client>=0.20.0",
    "opentelemetry-api>=1.25.0",

    # Security
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "locust>=2.29.0",
    "black>=24.0.0",
    "ruff>=0.5.0",
    "mypy>=1.11.0",
    "bandit>=1.7.5",
]

[tool.uv]
python = "3.11"
cache-dir = ".uv-cache"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 安裝指令

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 建立虛擬環境
uv venv

# 激活虛擬環境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 同步依賴 (production)
uv sync

# 同步開發依賴
uv sync --extra dev

# 鎖定依賴版本
uv lock
```

---

### 🤖 AI 模型依賴

#### 模型下載與驗證

| 模型 | 大小 | 下載指令 | 存儲位置 | 驗證方式 |
|------|------|----------|----------|----------|
| **Qwen3-32B-Instruct** | ~65GB | `huggingface-cli download Qwen/Qwen3-32B-Instruct` | `/data/models/qwen3-32b/` | SHA256 checksum |
| **Faster-Whisper large-v3** | ~3GB | Auto-download on first run | `~/.cache/huggingface/` | Model inference test |
| **GLM-4.7-Flash** | ~10GB | `huggingface-cli download THUDM/GLM-4-9B-Chat` | `/data/models/glm-flash/` | Model inference test |

#### HuggingFace 快取設定

```bash
# 設定模型快取目錄（推薦 /data/models）
export HF_HOME="/data/models"
export HF_TOKEN="your_hf_token_here"  # 可選

# 下載模型（預計 2-4 小時）
mkdir -p /data/models
huggingface-cli download Qwen/Qwen3-32B-Instruct --local-dir /data/models/qwen3-32b

# 驗證下載
ls -lh /data/models/qwen3-32b/
```

---

### 🗄️ 資料依賴

#### 醫療詞典與資料庫

| 資料來源 | 用途 | 格式 | 取得方式 | 狀態 |
|----------|------|------|----------|------|
| **ICD-10-CM** | 疾病代碼 | JSON/SQLite | WHO/CDC website | ⏳ 待下載 |
| **醫療術語表** | Synonym mapping | CSV | clinic-promot.md 表格 | ✅ 已有 |
| **專科分類規則** | Specialty routing | YAML | 自建 | ⏳ 待建立 |
| **測試語料** | Accuracy benchmark | JSON | 醫師標註 | ⏳ 待收集 |

#### ICD-10 資料庫設定

```bash
# 下載 ICD-10-CM (WHO 版本)
mkdir -p /data/icd10
wget https://www.cms.gov/files/zip/2024-icd-10-cm-codes-file.zip
unzip 2024-icd-10-cm-codes-file.zip -d /data/icd10/

# 轉換為 SQLite (Python script)
python scripts/import_icd10.py --input /data/icd10/icd10cm_codes_2024.txt --output /data/icd10.db

# 驗證資料庫
sqlite3 /data/icd10.db "SELECT COUNT(*) FROM icd10_codes;"
```

---

### 🔐 外部服務依賴 (可選)

| 服務 | 用途 | 必要性 | 替代方案 | 狀態 |
|------|------|--------|----------|------|
| **HuggingFace** | Model download | 必要 | 手動下載 + 鏡像 | ✅ Required |
| **Redis** | Cache & session | 建議 | 記憶體快取 | ✅ Included |
| **PostgreSQL** | User/session DB | 建議 | SQLite | ✅ Included |
| **Prometheus** | Monitoring | 建議 | 簡易 logging | ✅ Included |
| **Grafana** | Visualization | 建議 | Prometheus UI | ✅ Included |

---

### 📋 前置任務執行順序

#### Critical Path (必須按順序執行)

```
Week 0 (Pre-project):
1. ✅ 硬體驗收測試 (GPU, RAM, Disk)
   ↓
2. ⏳ Ubuntu 22.04+ 安裝與更新
   ↓
3. ⏳ NVIDIA Driver (≥535) + CUDA 12.1 安裝
   ↓ (需重開機)
4. ⏳ Docker + Docker Compose 安裝
   ↓
5. ⏳ Python 3.11 + uv 安裝
   ↓
6. ⏳ Git clone repository
   ↓
7. ⏳ uv sync (安裝 Python 依賴)
   ↓
8. ⏳ 下載 AI 模型 (~80GB, ~4-6 hours)
   ├ Qwen3-32B (~65GB)
   ├ Faster-Whisper large-v3 (~3GB)
   └ GLM-4.7-Flash (~10GB)
   ↓
9. ⏳ 準備醫療資料庫 (ICD-10, terminology)
   ↓
10. ✅ 環境驗證測試 (all components)
```

#### 平行任務 (可同時進行)

```
並行 A: Frontend 開發環境準備 (node, npm/yarn, React)
並行 B: 醫療測試語料收集 (200+ medical cases)
並行 C: 文件撰寫 (API spec, deployment guide)
並行 D: 監控系統設置 (Prometheus/Grafana)
```

---

### 🧪 環境驗證腳本

#### scripts/verify_environment.sh

```bash
#!/bin/bash
set -e

echo "🔍 === SoapVoice 環境驗證 === 🔍"
echo ""

# 硬體檢查
echo "1️⃣ 檢查硬體..."
echo "   GPU 信息:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
echo ""

# CUDA 檢查
echo "2️⃣ 檢查 CUDA..."
nvcc --version
echo ""

# Docker 檢查
echo "3️⃣ 檢查 Docker..."
docker --version
docker compose version
echo ""

# Python 檢查
echo "4️⃣ 檢查 Python..."
python3 --version
uv --version
echo ""

# PyTorch 檢查
echo "5️⃣ 檢查 PyTorch CUDA 支援..."
python3 << EOF
import torch
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU 數量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    print(f"CUDA 版本: {torch.version.cuda}")
else:
    print("❌ CUDA 不可用！")
    exit(1)
EOF
echo ""

echo "✅ 環境驗證完成！所有必要組件已就緒。"
```

#### 執行驗證

```bash
chmod +x scripts/verify_environment.sh
./scripts/verify_environment.sh
```

---

### ⚠️ Blocker Dependencies (阻擋項目)

**以下依賴若未滿足，專案無法進行:**

| Blocker | 影響階段 | 解決方案 | 預估時間 |
|---------|----------|----------|----------|
| CUDA 安裝失敗 | Phase 1 | 驅動降版或升級 kernel | 4-8 hr |
| 44GB VRAM 不足 | Phase 1 | 模型量化或硬體升級 | 2-5 days |
| uv 無法安裝依賴 | Phase 0 | 切換至 pip/poetry | 2 hr |
| 模型下載失敗 | Phase 1 | 鏡像站或手動傳輸 | 1 day |
| doctor-toolbox API 不相容 | Phase 4 | 協調 API 規格 | 1-2 weeks |

---

---

## 9️⃣ 深度審查改進計畫 (Deep Review Improvement Plan)

> **審查日期:** 2026-03-02
> **審查人:** Gemini AI Code Review
> **審查範圍:** 全專案程式碼 + 規劃文件 + 架構設計

---

### 🔍 現況總結 (Current State Assessment)

#### ✅ 已完成項目

| 項目 | 檔案 | 品質 | 備註 |
|------|------|------|------|
| ASR 模型封裝 | `src/asr/whisper_model.py` (234行) | ⭐⭐⭐⭐ | 結構清晰，API 設計良好 |
| 串流轉錄器 | `src/asr/stream_transcriber.py` (312行) | ⭐⭐⭐ | 功能完整但有 bug |
| 醫療詞彙模組 | `src/asr/vocabulary.py` (115行) | ⭐⭐⭐⭐ | 設計良好，可擴展 |
| WebSocket API | `src/api/websocket.py` (374行) | ⭐⭐⭐ | 有邏輯錯誤需修復 |
| 醫療詞彙庫 | `config/medical_vocabulary.json` (39KB) | ⭐⭐⭐⭐ | 內容豐富 |
| 模型配置 | `config/models.yaml` | ⭐⭐⭐⭐ | 結構完整 |
| Docker 配置 | `docker-compose.yml` + `Dockerfile` | ⭐⭐⭐ | 基礎可用 |
| 測試框架 | `tests/test_vocabulary.py` | ⭐⭐⭐ | 覆蓋基本場景 |
| 規劃文件 | `OpnusPlan.md` (1534行) | ⭐⭐⭐⭐⭐ | 非常詳盡 |

---

### 🚨 發現的關鍵問題 (Critical Issues Found)

#### 🔴 P0 - 嚴重問題（必須立即修復）

##### Issue #1: `vllm_engine.py` 缺失導致導入失敗

```python
# src/llm/__init__.py 引用了不存在的模組
from .vllm_engine import VLLMEngine  # ❌ 文件不存在！
```

**影響:** 任何引用 `src.llm` 的程式碼都會崩潰
**修復方案:** 建立 `src/llm/vllm_engine.py`，實作 VLLMEngine 類

---

##### Issue #2: WebSocket 端點雙重 `receive_text` bug

```python
# src/api/websocket.py L232-249
while True:
    # ❌ 第一次 receive_text 的結果被丟棄
    await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
    # ❌ 第二次 receive_text 才被處理，導致每隔一條訊息被丟失
    data = await websocket.receive_text()
```

**影響:** 50% 的客戶端訊息被靜默丟棄
**修復方案:** 合併為單次 receive 並正確處理超時

---

##### Issue #3: 缺少 FastAPI 主程式入口

**問題:** 無 `app/main.py` 或 `src/main.py`，Dockerfile CMD 指向 `app.main:app` 但不存在
**影響:** API 服務完全無法啟動
**修復方案:** 建立 `src/main.py`，整合所有 Router

---

##### Issue #4: 缺少 SOAP 生成模組

**問題:** 核心功能 — 醫療語音轉 SOAP 病歷 — 完全未實作
**計畫對應:** Phase 2 (Clinical NLP Engine)、F002 (SOAP 自動分類)
**修復方案:** 建立 `src/nlp/` 模組，包含 SOAP 分類與生成

---

#### 🟠 P1 - 重要問題

##### Issue #5: 缺少 `__init__.py` 導致 Python 套件不完整

```
src/           ← 缺少 __init__.py
├── api/       ← 缺少 __init__.py
├── asr/       ← ✅ 有 __init__.py
└── llm/       ← ✅ 有 __init__.py（但引用不存在的模組）
```

---

##### Issue #6: 模型配置中 LLM 指向雲端 API

```yaml
# config/models.yaml
llm:
  provider: "glm"
  api_base: "https://open.bigmodel.cn/api/paas/v4"  # ❌ 雲端 API
```

**問題:** 專案定位為「本地部署」，但 LLM 配置指向外部雲端 API
**修復方案:** 改為本地 vLLM 端點 `http://localhost:8001/v1`

---

##### Issue #7: pyproject.toml 與計畫書不一致

| 計畫書要求 | pyproject.toml 實際 | 狀態 |
|------------|---------------------|------|
| `websockets>=12.0` | ❌ 缺少 | 未安裝 |
| `pydantic-settings>=2.3.0` | ❌ 缺少 | 未安裝 |
| `sqlalchemy>=2.0.0` | ❌ 缺少 | 未安裝 |
| `redis>=5.0.0` | ❌ 缺少 | 未安裝 |
| `prometheus-client` | ❌ 缺少 | 未安裝 |
| `python-jose[cryptography]` | ❌ 缺少 | 未安裝 |

---

##### Issue #8: 安全配置風險

```yaml
# config/websocket.yaml
cors:
  allow_origins: ["*"]    # ❌ 允許所有來源
  allow_methods: ["*"]    # ❌ 允許所有方法
  allow_headers: ["*"]    # ❌ 允許所有標頭
```

**問題:** 醫療系統使用寬鬆 CORS 配置，不符合內網安全需求

---

### 📐 目標架構 vs 現況對比

```
計畫架構                              現況
────────────────────────              ────────────
✅ ASR Layer (Whisper)                ✅ 已實作 (基本功能)
   ├── WhisperModel                  ✅ 已有
   ├── StreamTranscriber             ⚠️ 有 bug
   └── MedicalVocabulary             ✅ 已有

❌ NLP Engine                         ❌ 完全缺失
   ├── TypoCorrection                ❌
   ├── SynonymMapping                ❌
   ├── SOAPClassifier                ❌
   ├── ICD10Mapper                   ❌
   └── SpecialtyDetector             ❌

❌ LLM Layer                          ❌ 模組空殼
   ├── VLLMEngine                    ❌ 檔案缺失
   ├── RoutingModel                  ❌
   └── PromptManager                 ❌

⚠️ API Gateway                       ⚠️ 部分完成
   ├── WebSocket                     ⚠️ 有 bug
   ├── REST Endpoints                ❌
   ├── Auth Middleware               ❌
   └── Main App                      ❌ 入口缺失
```

---

### 🛠️ 改進行動計畫 (Action Plan)

#### Sprint 1: 修復基礎 (Week 1-2, 立即開始)

> **目標:** 讓現有程式碼能正確運行

| # | 任務 | 優先級 | 預估 | 檔案 |
|---|------|--------|------|------|
| 1.1 | 修復 WebSocket 雙重 receive bug | P0 | 1h | `src/api/websocket.py` |
| 1.2 | 建立 `src/main.py` FastAPI 入口 | P0 | 2h | `src/main.py` [NEW] |
| 1.3 | 建立 `src/llm/vllm_engine.py` | P0 | 4h | `src/llm/vllm_engine.py` [NEW] |
| 1.4 | 補齊所有 `__init__.py` | P0 | 0.5h | `src/`, `src/api/` |
| 1.5 | 修正 LLM 配置為本地部署 | P1 | 1h | `config/models.yaml` |
| 1.6 | 同步 `pyproject.toml` 依賴 | P1 | 1h | `pyproject.toml` |
| 1.7 | 修正 CORS 安全配置 | P1 | 0.5h | `config/websocket.yaml` |
| 1.8 | 修正 Dockerfile CMD 路徑 | P0 | 0.5h | `Dockerfile` |

**Sprint 1 驗收標準:**
- [ ] `uv run python -c "from src.llm import VLLMEngine"` 成功
- [ ] `uv run uvicorn src.main:app --port 8000` 可啟動
- [ ] WebSocket 連接測試不丟失訊息
- [ ] 所有現有測試通過

---

#### Sprint 2: 核心 NLP 引擎 (Week 3-4)

> **目標:** 實作 SOAP 病歷生成核心邏輯

| # | 任務 | 優先級 | 預估 | 檔案 |
|---|------|--------|------|------|
| 2.1 | 建立 NLP 模組結構 | P0 | 1h | `src/nlp/__init__.py` [NEW] |
| 2.2 | 實作口語→醫療術語映射 | P0 | 6h | `src/nlp/synonym_mapper.py` [NEW] |
| 2.3 | 實作 SOAP 關鍵字分類器 | P0 | 8h | `src/nlp/soap_classifier.py` [NEW] |
| 2.4 | 實作錯字修正模組 | P1 | 4h | `src/nlp/typo_corrector.py` [NEW] |
| 2.5 | 實作 NLP Pipeline 串接 | P0 | 4h | `src/nlp/pipeline.py` [NEW] |
| 2.6 | 建立 REST API `/api/v1/soap/generate` | P0 | 4h | `src/api/soap_router.py` [NEW] |
| 2.7 | 建立 REST API `/api/v1/clinical/normalize` | P0 | 3h | `src/api/clinical_router.py` [NEW] |
| 2.8 | NLP 單元測試 | P0 | 4h | `tests/test_soap_classifier.py` [NEW] |
| 2.9 | 整合 LLM 與 NLP Pipeline | P1 | 6h | `src/nlp/llm_soap_generator.py` [NEW] |

**Sprint 2 驗收標準:**
- [ ] 輸入中文醫療對話 → 輸出結構化 SOAP JSON
- [ ] SOAP 分類準確率 ≥ 85%（基礎關鍵字版本）
- [ ] REST API 端點可用且有 OpenAPI 文件
- [ ] 單元測試覆蓋率 ≥ 70%

---

#### Sprint 3: LLM 整合與 Prompt 工程 (Week 5-6)

> **目標:** 用 LLM 增強 SOAP 品質

| # | 任務 | 優先級 | 預估 | 檔案 |
|---|------|--------|------|------|
| 3.1 | 完善 VLLMEngine 推理功能 | P0 | 6h | `src/llm/vllm_engine.py` |
| 3.2 | 實作 Prompt 模板管理 | P0 | 4h | `src/llm/prompt_manager.py` [NEW] |
| 3.3 | 建立 clinic-promot.md 的程式化版本 | P0 | 3h | `src/llm/medical_prompts.py` [NEW] |
| 3.4 | 實作路由模型邏輯 | P1 | 4h | `src/llm/routing.py` [NEW] |
| 3.5 | LLM 推理效能調優 | P1 | 4h | `config/models.yaml` |
| 3.6 | 端到端測試 (語音→SOAP) | P0 | 6h | `tests/test_e2e_soap.py` [NEW] |

---

#### Sprint 4: 安全與監控 (Week 7-8)

> **目標:** 達到 MVP 生產品質

| # | 任務 | 優先級 | 預估 |
|---|------|--------|------|
| 4.1 | 實作 API Key 認證中間件 | P0 | 4h |
| 4.2 | 實作速率限制 | P1 | 3h |
| 4.3 | 加入 Prometheus 監控指標 | P1 | 4h |
| 4.4 | 實作健康檢查端點 | P0 | 1h |
| 4.5 | 完善 Docker Compose（加入 Redis/PostgreSQL） | P1 | 4h |
| 4.6 | 建立 README.md | P0 | 2h |
| 4.7 | 效能壓力測試 | P1 | 4h |

---

### 📁 改進後的目錄結構

```
SoapVoice/
├── src/
│   ├── __init__.py                  [NEW]
│   ├── main.py                      [NEW] FastAPI 入口
│   ├── api/
│   │   ├── __init__.py              [NEW]
│   │   ├── websocket.py             [FIX] 修復雙重 receive bug
│   │   ├── soap_router.py           [NEW] SOAP 生成 REST API
│   │   ├── clinical_router.py       [NEW] 醫療標準化 REST API
│   │   └── middleware.py            [NEW] 認證、速率限制
│   ├── asr/
│   │   ├── __init__.py              ✅ 已有
│   │   ├── whisper_model.py         ✅ 已有
│   │   ├── stream_transcriber.py    ✅ 已有
│   │   └── vocabulary.py            ✅ 已有
│   ├── nlp/                         [NEW] 全新模組
│   │   ├── __init__.py
│   │   ├── pipeline.py              NLP 處理管道
│   │   ├── soap_classifier.py       SOAP 分類器
│   │   ├── synonym_mapper.py        口語→醫療術語
│   │   ├── typo_corrector.py        錯字修正
│   │   └── llm_soap_generator.py    LLM 增強 SOAP 生成
│   └── llm/
│       ├── __init__.py              ✅ 已有
│       ├── vllm_engine.py           [NEW] vLLM 推理引擎
│       ├── prompt_manager.py        [NEW] Prompt 管理
│       ├── medical_prompts.py       [NEW] 醫療 Prompt 模板
│       └── routing.py              [NEW] 模型路由
├── config/
│   ├── medical_vocabulary.json      ✅ 已有
│   ├── models.yaml                  [FIX] 改為本地部署
│   └── websocket.yaml               [FIX] CORS 安全化
├── tests/
│   ├── test_vocabulary.py           ✅ 已有
│   ├── test_soap_classifier.py      [NEW]
│   ├── test_nlp_pipeline.py         [NEW]
│   └── test_e2e_soap.py             [NEW]
├── scripts/
│   ├── verify-hardware.sh           ✅ 已有
│   └── import_icd10.py              [NEW]
├── pyproject.toml                   [FIX] 同步依賴
├── docker-compose.yml               [FIX] CMD 路徑
├── Dockerfile                       [FIX] 入口修正
└── README.md                        [NEW]
```

---

### 📊 改進計畫 KPI 目標

| 指標 | 當前值 | Sprint 2 後 | Sprint 4 後 |
|------|--------|-------------|-------------|
| 程式碼行數 | ~1,100 行 | ~3,500 行 | ~5,500 行 |
| 模組數 | 5 個 | 13 個 | 18 個 |
| 測試覆蓋率 | ~15% | ≥50% | ≥70% |
| API 端點數 | 3 (WS+health+stats) | 6 | 8 |
| P0 bug | 4 個 | 0 個 | 0 個 |
| SOAP 生成 | ❌ 不可用 | ✅ 關鍵字版 | ✅ LLM 增強版 |
| 服務可啟動 | ❌ 否 | ✅ 是 | ✅ 生產就緒 |

---

### ⚡ 立即行動清單 (Immediate Actions)

> 以下可在今天內完成的修復：

1. **修復** `src/api/websocket.py` L232-249 雙重 receive bug
2. **建立** `src/__init__.py` 和 `src/api/__init__.py`
3. **建立** `src/main.py` FastAPI 入口點
4. **建立** `src/llm/vllm_engine.py` 基礎骨架
5. **修正** `config/models.yaml` LLM 為本地配置
6. **修正** `Dockerfile` CMD 路徑

---

## 📌 文件管理

**版本:** v0.2.0
**最後更新:** 2026-03-02
**下一次更新:** Sprint 1 完成後（約 2026-03-14）

**相關文件:**
- [clinic-promot.md](./clinic-promot.md) - 核心技術規格
- [DailyProgress.md](./DailyProgress.md) - 每日進度追蹤
- [README.md](./README.md) - 專案說明（待建立）

**責任人:** Tech Lead (Yu Hsu)
**審核人:** All team members

---

**使用說明:** 本文件是 SoapVoice 項目的執行計畫藍圖。請定期（每 2 週）檢查是否仍符合實際進度，有重大偏差時更新本文件並通知團隊。
