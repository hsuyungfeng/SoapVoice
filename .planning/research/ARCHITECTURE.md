# Architecture Research — v1.1 網路部署與資料管理

**Domain:** 醫療語音轉 SOAP 病歷系統 — LAN 瘦客戶端架構整合
**Researched:** 2026-04-24
**Confidence:** HIGH

---

## System Overview: v1.0 → v1.1 架構變遷

### v1.0 既有架構（單體 Monolith）

```
┌──────────────────────────────────────────────────────────────────┐
│                   SoapVoice 單體 (localhost:8010)                  │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ GUI 層   │  │ API 層   │  │ ASR 層   │  │ LLM 層   │        │
│  │ (ttk)    │  │ (FastAPI)│  │ (Whisper)│  │ (llama)  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │              │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐         │
│  │                   NLP 層 + SOAP 層                  │         │
│  │   術語標準化 → ICD-10 → 分類 → SOAP 生成            │         │
│  └──────────────────────────┬─────────────────────────┘         │
│                             │                                    │
│  ┌──────────────────────────┴─────────────────────────┐         │
│  │                    儲存層（檔案 + SQLite）            │         │
│  │  data/recordings/  ·  config.json  ·  medical.db    │         │
│  └─────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘

問題：GUI 與處理引擎耦合在同一主機（需要 GPU），無法 LAN 多機協作。
```

### v1.1 目標架構（LAN 瘦客戶端）

```
┌────────────────────────── 區網 (LAN) ──────────────────────────┐
│                                                                 │
│  ┌─────────────────────────────┐   ┌──────────────────────────┐│
│  │   瘦客戶端 Windows EXE       │   │  GPU 伺服器 (Linux)       ││
│  │   (Capture-Only)            │   │  (Processing + Storage)  ││
│  │                             │   │                          ││
│  │  ┌──────────┐  ┌─────────┐  │   │  ┌──────────────────┐   ││
│  │  │ GUI 側邊欄│  │ 麥克風   │  │   │  │  FastAPI Server  │   ││
│  │  │ (ttk)    │  │ 錄音     │  │   │  │  (0.0.0.0:8010) │   ││
│  │  └────┬─────┘  └────┬────┘  │   │  └────────┬─────────┘   ││
│  │       │             │       │   │           │              ││
│  │  ┌────┴─────────────┴────┐  │   │  ┌────────┴─────────┐   ││
│  │  │  HTTP Client          │  │   │  │  ASR 引擎          │   ││
│  │  │  (requests 連線)       │──┼───┼──│  Faster-Whisper   │   ││
│  │  └───────────────────────┘  │   │  └────────┬─────────┘   ││
│  │                             │   │           │              ││
│  │  ┌───────────────────────┐  │   │  ┌────────┴─────────┐   ││
│  │  │  WebSocket Client     │  │   │  │  LLM 引擎          │   ││
│  │  │  (音頻串流)            │══╪═══╪══│  llama-cpp-python │   ││
│  │  └───────────────────────┘  │   │  └────────┬─────────┘   ││
│  │                             │   │           │              ││
│  │  ┌───────────────────────┐  │   │  ┌────────┴─────────┐   ││
│  │  │  螢幕截圖 (mss)       │  │   │  │  NLP + SOAP 管線   │   ││
│  │  │  HIS 畫面 OCR 上傳     │──┼───┼──│  術語→ICD-10→SOAP │   ││
│  │  └───────────────────────┘  │   │  └────────┬─────────┘   ││
│  │                             │   │           │              ││
│  └─────────────────────────────┘   │  ┌────────┴─────────┐   ││
│                                     │  │  資料持久層        │   ││
│                                     │  │  SQLAlchemy ORM   │   ││
│                                     │  │  SQLite 資料庫    │   ││
│                                     │  └────────┬─────────┘   ││
│                                     │           │              ││
│                                     │  ┌────────┴─────────┐   ││
│                                     │  │  監控儀表板        │   ││
│                                     │  │  /metrics 端點     │   ││
│                                     │  │  Grafana 面板     │   ││
│                                     │  └──────────────────┘   ││
│                                     └──────────────────────────┘│
│                                                                 │
│  通訊協定：HTTP REST + WebSocket + 靜態檔案上傳 (截圖)           │
│  認證：API Key + JWT Token（已實作，v1.1 沿用並擴充）            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. LAN 瘦客戶端：模組分割策略

### 模組歸屬決策

| 模組 | 現有位置 | v1.1 歸屬 | 理由 |
|------|---------|-----------|------|
| `src/gui/desktop_app.py` | 伺服器端 | **客戶端**（重寫） | GUI 在客戶端運行，顯示 SOAP 結果 |
| `src/gui/config_manager.py` | 伺服器端 | **客戶端**（修改） | 診所/醫師設定保留在客戶端 `config.json` |
| `src/asr/whisper_model.py` | 伺服器端 | **伺服器端**（不變） | GPU 密集型，須留在伺服器 |
| `src/asr/stream_transcriber.py` | 伺服器端 | **伺服器端**（不變） | 串流處理邏輯不變 |
| `src/asr/asr_factory.py` | 伺服器端 | **伺服器端**（不變） | 引擎選擇邏輯不變 |
| `src/nlp/*` | 伺服器端 | **伺服器端**（不變） | 全部 NLP 處理留在伺服器 |
| `src/soap/soap_generator.py` | 伺服器端 | **伺服器端**（不變） | LLM 推理須在 GPU 端 |
| `src/llm/*` | 伺服器端 | **伺服器端**（不變） | 僅 GPU 環境可用 |
| `src/db/*` | 伺服器端 | **伺服器端**（重寫） | 改為 SQLAlchemy ORM，見 §2 |
| `src/nlp/ocr_parser.py` | 伺服器端 | **部分移至客戶端** | 截圖在客戶端執行，OCR 可選上傳後由伺服器處理 |
| `src/phase8/capture_ocr.py` | 伺服器端 | **客戶端**（重寫） | 截圖擷取邏輯移至客戶端 |
| `src/security/auth.py` | 伺服器端 | **伺服器端**（擴充） | API Key 驗證擴充 session token |

### 客戶端 EXE 組成

```
client/
├── main.py                  # 客戶端入口（PyInstaller 打包為 EXE）
├── gui/
│   ├── thin_app.py          # 瘦客戶端 GUI（極簡版，無推理）
│   └── config_manager.py    # 設定管理（診所/醫師/伺服器位址）
├── capture/
│   ├── audio_recorder.py    # 麥克風錄音 + WebSocket 串流
│   └── screen_capture.py    # 螢幕截圖（HIS 畫面）
└── network/
    ├── api_client.py         # HTTP REST 客戶端（原有 requests 擴充）
    └── ws_client.py          # WebSocket 客戶端（原有邏輯分離）
```

### 網路介面契約

**客戶端 → 伺服器通訊：**

| 端點 | 方法 | 內容 | 既有/新增 |
|------|------|------|-----------|
| `POST /api/v1/clinical/soap/generate` | REST | 語音逐字稿 → SOAP 病歷 | **既有**（不變） |
| `POST /api/v1/soap/audio` | REST | 完整音檔上傳 + SOAP 生成 | **新增** |
| `POST /api/v1/ocr/capture` | REST | 截圖上傳 → OCR 結果 | **新增** |
| `WS /api/v1/ws/transcribe` | WebSocket | 即時音頻串流 → 轉錄 | **既有**（不變） |
| `POST /api/v1/auth/token` | REST | JWT token 獲取 | **既有**（不變） |
| `GET /api/v1/server/status` | REST | 伺服器健康/GPU 狀態 | **新增** |

**新模式：音檔上傳（非串流）**
```
客戶端錄完整段對話 → 上傳 WAV 檔 → 伺服器執行完整管線 → 回傳 SOAP
```
這個模式適合「錄完再處理」的場景，與既有 WebSocket 串流互補。

### 既有 GUI 變更摘要

**現有 `desktop_app.py` 問題：**
- 硬編碼 `API_BASE_URL = "http://127.0.0.1:8010"`（LAN 部署需改為可設定）
- 錄音、截圖、API 呼叫、顯示全部耦合在一個 524 行的檔案中
- `AudioRecorder` 內嵌 WebSocket 客戶端邏輯，難以分離

**v1.1 重構策略：**
1. 將 `desktop_app.py` 拆分為 `thin_app.py`（GUI 殼層）+ `api_client.py`（網路層）
2. `API_BASE_URL` 改為從 `config_manager.py` 讀取，GUI 設定頁面讓使用者輸入伺服器 IP
3. 移除所有 `import src.asr`, `import src.llm`, `import src.nlp` — 客戶端不應依賴推理模組
4. `AudioRecorder` 保留在客戶端，只負責麥克風擷取和音頻上傳

---

## 2. 資料庫持久層：SQLAlchemy ORM 整合

### 現有狀態分析

```python
# src/db/clinical_db.py（既有 — 連線每次新建）
class ClinicalDatabase:
    def __init__(self, db_path: str = "data/local_db/medical.db"):
        self.db_path = db_path

    def _get_connection(self):  # ⚠ 每次查詢建立新連線
        return sqlite3.connect(self.db_path)
```

**問題：**
- 無 ORM：原始 SQL 字串拼接（SQL injection 風險低但維護性差）
- 無連線池：每次查詢 `sqlite3.connect()` → `close()`，效能瓶頸
- 無遷移管理：schema 變更靠手動 SQL 腳本
- 無 async 支援：阻塞 FastAPI event loop
- 諮詢記錄僅存在記憶體（`SessionManager._sessions = {}` dict），伺服器重啟即丟失

### v1.1 推薦架構

**技術棧：**
| 元件 | 技術 | 理由 |
|------|------|------|
| ORM | SQLAlchemy 2.0+ (async) | FastAPI 生態標準，官方 async 支援成熟 |
| Database | SQLite (aiosqlite) | 單機 LAN 部署足夠，免安裝免維護 |
| Migration | Alembic | SQLAlchemy 官方遷移工具 |
| Connection | `async_sessionmaker` + DI | 每請求一 session，自動釋放 |

**目錄結構：**

```
src/db/
├── __init__.py
├── database.py              # 引擎 + session factory（新增）
├── models/                   # SQLAlchemy 模型（新增）
│   ├── __init__.py
│   ├── base.py              # DeclarativeBase
│   ├── patient.py            # 患者模型
│   ├── consultation.py       # 諮詢記錄模型
│   ├── soap_record.py        # SOAP 病歷模型
│   └── user.py               # 使用者/醫師模型
├── repositories/             # 倉儲層（新增）
│   ├── __init__.py
│   ├── base_repo.py          # 通用 CRUD
│   ├── patient_repo.py
│   └── consultation_repo.py
├── dependencies.py           # FastAPI Depends（新增）
├── clinical_db.py            # ⚠ 保留為相容層，內部改用 SQLAlchemy
├── local_database.py         # ⚠ 保留，內部改用 SQLAlchemy
└── alembic/                  # 遷移腳本（新增）
    ├── env.py
    └── versions/
```

**核心資料模型：**

```python
# src/db/models/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# src/db/models/consultation.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime

class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    doctor_name = Column(String(128), nullable=True)
    clinic_name = Column(String(256), nullable=True)
    status = Column(String(32), default="recording")
    transcript = Column(Text, nullable=True)           # ASR 逐字稿
    audio_path = Column(String(512), nullable=True)     # 音檔路徑
    screenshot_path = Column(String(512), nullable=True) # HIS 截圖
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    soap_record = relationship("SOAPRecord", back_populates="consultation", uselist=False)

class SOAPRecord(Base):
    __tablename__ = "soap_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"), unique=True)
    subjective = Column(Text, nullable=True)
    objective = Column(Text, nullable=True)
    assessment = Column(Text, nullable=True)
    plan = Column(Text, nullable=True)
    conversation_summary = Column(Text, nullable=True)
    icd10_code = Column(String(16), nullable=True)
    normalized_terms = Column(Text, nullable=True)  # JSON string
    generated_at = Column(DateTime, default=datetime.utcnow)

    consultation = relationship("Consultation", back_populates="soap_record")
```

**依賴注入模式（取代既有單例 `get_clinical_db()`）：**

```python
# src/db/dependencies.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每請求建立一個資料庫 session，請求結束自動關閉"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

**既有單例相容策略：**

現有 `rest.py` 中的 `get_clinical_db()`, `get_soap_generator()` 等單例模式**保留不變**，內部改為從 DI 取得 SQLAlchemy session。這樣確保既有 API 端點無需大幅改寫：

```python
# src/db/clinical_db.py（重構後）
class ClinicalDatabase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_medical_orders(self, symptoms, icd10_codes):
        # 使用 SQLAlchemy 查詢取代原始 sqlite3
        ...

# src/api/rest.py（最小改動）
def get_clinical_db(
    db: AsyncSession = Depends(get_db_from_singleton),
) -> ClinicalDatabase:
    # 既有單例模式，內部改用 SQLAlchemy session
    ...
```

### 既有檔案儲存 → DB 遷移路徑

| 既有儲存 | 目標 | 遷移方式 |
|---------|------|---------|
| `config.json`（診所/醫師設定） | `clinics` + `users` 表 | 一次性匯入腳本 |
| `SessionManager._sessions` (in-memory dict) | `consultations` 表 | 廢棄 in-memory，直接寫 DB |
| `data/recordings/*.wav`（音檔） | `data/recordings/`（保留）+ DB 紀錄路徑 | 既有目錄結構保留，DB 儲存 metadata |
| 無患者記錄 | `patients` 表 | **新增功能**，支援歷史查詢 |

---

## 3. 監控儀表板：即時指標整合

### 既有狀態

```python
# src/main.py — 既有監控端點（極簡）
@app.get("/health")        # {"status": "healthy"}
@app.get("/api/v1/stats")  # {"active_connections": 3, ...}  # 手動計數
# config/prometheus.yml 存在但無 /metrics 端點
```

### v1.1 新增元件

**步驟 1：安裝並注入 `prometheus-fastapi-instrumentator`**

```python
# src/main.py（新增約 5 行程式碼）
from prometheus_fastapi_instrumentator import Instrumentator

# 在 app 建立後，路由註冊前
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, include_in_schema=False)
# 自動建立 GET /metrics 端點
```

**自動獲取的指標（零額外程式碼）：**
- `http_requests_total` — 請求計數（按 method, path, status 分組）
- `http_request_duration_seconds_bucket` — 處理時間分佈（含 P50/P95/P99）
- `http_request_size_bytes` — 請求大小

**步驟 2：自訂業務指標（新增）**

```python
# src/metrics.py（新增檔案）
from prometheus_client import Counter, Histogram, Gauge, Info

# 自訂業務指標
soap_generation_total = Counter(
    "soap_generation_total",
    "SOAP 病歷生成總數",
    ["model", "status"]
)

soap_generation_duration = Histogram(
    "soap_generation_duration_seconds",
    "SOAP 生成耗時（秒）",
    buckets=[1, 2, 5, 10, 15, 30, 60]
)

asr_transcription_duration = Histogram(
    "asr_transcription_duration_seconds",
    "ASR 轉錄耗時",
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

active_connections = Gauge(
    "websocket_active_connections",
    "活躍 WebSocket 連線數"
)

gpu_memory_used = Gauge(
    "gpu_memory_used_bytes",
    "GPU 記憶體使用量"
)
```

**步驟 3：在既有端點中埋點**

現有 `rest.py` 中的 SOAP 生成端點已追蹤 `processing_time_ms`，只需加一行：

```python
# src/api/rest.py — generate_soap() 內
soap_generation_total.labels(model=generator.config.model_id, status="success").inc()
soap_generation_duration.observe(processing_time / 1000)
```

**步驟 4：儀表板 UI — 兩條路徑並行**

| 路徑 | 目標用戶 | 實作方式 |
|------|---------|---------|
| **A. 獨立 Grafana 面板** | 系統管理員 | Docker Compose 新增 `grafana` 服務，匯入預設面板 JSON |
| **B. 內嵌監控頁面** | 一般使用者（醫師） | 靜態 HTML 頁面 `static/dashboard.html`，以 JS fetch `/api/v1/stats` + SSE 即時更新 |

**路徑 B 優先實作理由：**
- LAN 部署環境不一定有 Grafana
- 醫師只需看「伺服器狀態、今日 SOAP 數、GPU 記憶體」等簡易指標
- 靜態 HTML 頁面即可滿足，不需外部依賴

**新增 SSE 端點（server-sent events，即時推送）：**

```python
# src/api/metrics_api.py（新增）
@router.get("/api/v1/metrics/stream")
async def metrics_stream(request: Request):
    """SSE 即時指標串流"""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            stats = {
                "gpu_memory_used_mb": get_gpu_memory_mb(),
                "active_connections": len(manager.active_connections),
                "soap_today": await count_soap_today(),
                "pending_jobs": len(_job_queue),
            }
            yield f"data: {json.dumps(stats)}\n\n"
            await asyncio.sleep(2)  # 每 2 秒推送
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 擴充既有端點（不取代）

| 既有端點 | v1.1 變更 |
|---------|----------|
| `GET /health` | 擴充：新增 `gpu.available`, `db.connected`, `llm.loaded` 欄位 |
| `GET /api/v1/stats` | 擴充：新增 `soap_count_today`, `avg_processing_time`, `uptime` |
| `GET /metrics` | **新增**：Prometheus 格式（供外部工具抓取） |
| `GET /api/v1/metrics/stream` | **新增**：SSE 即時串流 |

---

## 4. Wine EXE 測試：CI 整合模式

### 定位

Wine EXE 測試**不屬於執行期架構**，而是 CI/CD 層的品保機制。目標是在 Linux 開發環境中，使用 Wine 驗證透過 PyInstaller 打包的 Windows EXE 在 Wine 下可啟動、基本功能正常。

### 架構位置

```
soapvoice/
├── .github/
│   └── workflows/
│       └── wine-test.yml          # 新增：Wine 測試工作流程
├── tests/
│   └── wine/
│       ├── __init__.py
│       ├── test_exe_launch.py     # 新增：EXE 啟動測試
│       ├── test_exe_api.py        # 新增：EXE API 連線測試
│       └── conftest.py            # 新增：Wine fixture
└── scripts/
    └── wine_wrapper.sh            # 新增：Wine 包裝腳本
```

### CI 工作流程（GitHub Actions）

```yaml
# .github/workflows/wine-test.yml
name: Wine EXE Validation
on:
  push:
    paths:
      - 'client/**'
      - 'soapvoice.spec'
      - 'pyproject.toml'

jobs:
  wine-test:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Install Wine
        run: |
          sudo dpkg --add-architecture i386
          sudo apt update
          sudo apt install -y wine64 wine32 xvfb

      - name: Build Client EXE
        run: |
          uv sync
          uv run pyinstaller soapvoice.spec

      - name: Smoke Test (Wine)
        run: |
          xvfb-run wine dist/soapvoice/soapvoice.exe --help
        # 驗證：EXE 可啟動、無 crash、help 輸出正確

      - name: API Connectivity Test
        run: |
          # 啟動測試伺服器，模擬 GPU 伺服器回應
          uv run uvicorn tests.wine.mock_server:app --host 0.0.0.0 --port 8010 &
          sleep 3
          xvfb-run wine dist/soapvoice/soapvoice.exe --test-connect
```

### 與既有 `soapvoice.spec` 的關係

既有 `SoapVoice-Offline.spec` 是**全功能離線版**（含 llama.cpp + GGUF 模型，體積巨大）。Wine 測試應使用**客戶端專用 spec**：

```
soapvoice-client.spec     # 新增：輕量客戶端 EXE
  ├── 僅含 client/ 模組
  ├── 不含 models/*.gguf（~2 GB）
  ├── 不含 src/asr/, src/llm/（推理模組）
  └── 最終 EXE < 50 MB（適合快速 CI）
```

---

## 5. 整合點摘要：新 vs 修改 vs 不變

### 新增模組

| 模組 | 路徑 | 說明 |
|------|------|------|
| 客戶端 EXE | `client/` (根目錄) | 瘦客戶端：GUI + 錄音 + 截圖 + 網路層 |
| SQLAlchemy 模型 | `src/db/models/` | 患者、諮詢、SOAP、使用者模型 |
| Alembic 遷移 | `src/db/alembic/` | Schema 版本管理 |
| 倉儲層 | `src/db/repositories/` | CRUD 封裝 |
| 指標模組 | `src/metrics.py` | Prometheus 自訂指標 |
| SSE 即時指標 | `src/api/metrics_api.py` | 儀表板 SSE 串流 |
| 監控面板 | `static/dashboard.html` | 內嵌監控頁面 |
| Wine CI | `.github/workflows/wine-test.yml` | 自動化 Wine 測試 |
| 客戶端 spec | `soapvoice-client.spec` | PyInstaller 輕量打包 |

### 修改模組

| 模組 | 變更範圍 | 風險等級 |
|------|---------|---------|
| `src/main.py` | 新增 Instrumentator、metrics 路由 | **低** — 純新增 |
| `src/api/rest.py` | 既有端點加入 prometheus 埋點 | **低** — 加行不加邏輯 |
| `src/gui/desktop_app.py` | 拆分為 thin_app.py，移除推理依賴 | **中** — 重構 |
| `src/db/clinical_db.py` | 內部改用 SQLAlchemy session | **中** — 向後相容 |
| `src/db/local_database.py` | 內部改用 SQLAlchemy | **中** — 向後相容 |
| `src/consultation/session_manager.py` | in-memory → DB 持久化 | **中** — 行為改變 |
| `config/prometheus.yml` | 更新 scrape target | **低** — 設定檔 |
| `pyproject.toml` | 新增 sqlalchemy, aiosqlite, alembic, prometheus-client | **低** |

### 不變模組（黑盒復用）

這些模組的實作完全不變，僅透過既有的 HTTP API 被呼叫：

- `src/asr/whisper_model.py`
- `src/asr/stream_transcriber.py`
- `src/asr/asr_factory.py`
- `src/llm/llama_engine.py`
- `src/llm/ollama_engine.py`
- `src/nlp/terminology_mapper.py`
- `src/nlp/icd10_classifier.py`
- `src/nlp/soap_classifier.py`
- `src/soap/soap_generator.py`
- `src/security/auth.py`（僅擴充，不重寫）

---

## 6. 資料流比較：v1.0 vs v1.1

### v1.0（同一主機）

```
麥克風 → AudioRecorder → 本地 WAV 檔
                              ↓
                     Whisper ASR (本地模型)
                              ↓
                     術語標準化 + ICD-10
                              ↓
                     Gemma 4:E4B (本地 GPU)
                              ↓
                     SOAP 病歷 → GUI 顯示
```

### v1.1 模式 A：WebSocket 即時串流（LAN）

```
[客戶端 Windows]                    [GPU 伺服器 Linux]

麥克風 → AudioRecorder
         ↓
    WebSocket 音頻串流 ───────────→ Whisper ASR (GPU)
                                       ↓
                                  術語標準化 + ICD-10
                                       ↓
                                  Gemma 4:E4B (GPU)
                                       ↓
                                  SOAP 病歷
                                       ↓
    ← REST 回傳 JSON ────────────────┘
         ↓
    GUI 顯示 + 存檔(gui 本機)
```

### v1.1 模式 B：完整音檔上傳（批次）

```
[客戶端 Windows]                    [GPU 伺服器 Linux]

麥克風 → 錄音完整對話 → WAV 檔
         ↓
    POST /api/v1/soap/audio ──────→ 完整管線處理
    (multipart/form-data)              (ASR → NLP → LLM)
                                       ↓
    ← JSON SOAP 回傳 ────────────────┘
         ↓
    GUI 顯示
```

### v1.1 模式 C：截圖 OCR（HIS 畫面）

```
[客戶端 Windows]                    [GPU 伺服器 Linux]

mss 截圖 HIS 畫面 → PNG
         ↓
    POST /api/v1/ocr/capture ─────→ Tesseract OCR
    (multipart/form-data)            (繁體中文 + 英文)
                                       ↓
    ← 患者資訊 JSON ─────────────────┘
         ↓
    自動填入 SOAP patient_context
```

---

## 7. 建置順序建議（依賴關係）

```
Phase 10: 資料持久層（DB ORM + 遷移）
  └─ 無上游依賴，先行建立
  └─ 產生者：models, dependencies, alembic/initial migration
  └─ 下游：所有需要儲存的模組

Phase 11: 客戶端分離（Client EXE）
  └─ 依賴：Phase 10（DB models 定義完成），Phase 9（PyInstaller 經驗）
  └─ 產生者：client/ 目錄、thin_app.py、soapvoice-client.spec
  └─ 下游：Phase 13（Wine 測試）

Phase 12: 監控儀表板（Metrics + Dashboard）
  └─ 無上游依賴（與 Phase 10/11 平行開發）
  └─ 產生者：/metrics、SSE stream、dashboard.html、Grafana 模板

Phase 13: Wine EXE 驗證
  └─ 依賴：Phase 11（客戶端 EXE 可建置）
  └─ 產生者：CI workflow、Wine 測試腳本

Phase 14: 技術文件
  └─ 依賴：Phase 10-13 完成
  └─ 產生者：README.md 重寫、ARCHITECTURE.md 更新、AGENTS.md 更新
```

**平行化建議：**
- Phase 10（DB）與 Phase 12（監控）可平行開發（無互相依賴）
- Phase 11（客戶端）需等 Phase 10 的資料模型定義好，但可與 Phase 12 平行

---

## 8. 既有單例模式適應策略

SoapVoice 大量使用模組層級單例（`src/api/rest.py` 中有 5 個 `get_*()` 函數）。v1.1 整合時須遵守以下原則：

**原則 1：保留單例，內部升級。**
不要一次把所有單例改成 DI — 這會造成大規模重構風險。讓既有的 `get_*()` 函數在內部改用新的實作。

**原則 2：逐步遷移。**
新端點（如監控、搜尋）直接使用 SQLAlchemy DI；既有端點保留單例作為過渡，內部橋接到新的 session 管理。

**原則 3：不要跨模組引入循環依賴。**
客戶端模組（`client/`）不能 `import src.*` — 這是最重要的邊界。客戶端只透過 HTTP/WS 協議與伺服器通訊。

---

## Anti-Patterns to Avoid

### Anti-Pattern 1：客戶端模組 import 伺服器推理模組
**錯誤：** `from src.llm.llama_engine import LlamaEngine` 出現在客戶端程式碼中
**後果：** 客戶端 EXE 體積暴增（需包含 llama-cpp-python + CUDA 依賴），且無法在無 GPU 機器執行
**正解：** 客戶端所有推理需求透過 HTTP API/WebSocket 呼叫伺服器

### Anti-Pattern 2：資料庫 session 跨請求共用
**錯誤：** 在模組層級建立一個全域 `AsyncSession`，多次請求共用
**後果：** Transaction 汙染、連線洩漏、concurrent 請求互相干擾
**正解：** 每請求一 session（透過 FastAPI `Depends`），請求結束自動關閉

### Anti-Pattern 3：監控端點無認證保護
**錯誤：** `/metrics` 端點公開無保護
**後果：** Prometheus 指標洩漏內部實作細節（端點路徑、錯誤率）
**正解：** `/metrics` 僅允許內網存取，或加 API Key 驗證（LAN 環境下內網 IP 過濾即可）

### Anti-Pattern 4：Wine 測試用全功能 EXE
**錯誤：** 用包含 GPU 推理模組的完整 EXE 跑 Wine 測試
**後果：** CI 每次需下載 ~2 GB 模型，Wine 無法載入 CUDA
**正解：** 客戶端專用 spec，僅含 GUI + 網路層，< 50 MB

---

## Sources

- [FastAPI SQLAlchemy async session dependency injection pattern](https://medium.com/) — 2025-2026 標準模式，per-request session with `async_sessionmaker` — **HIGH confidence**
- [prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator) — 官方推薦的 FastAPI Prometheus 整合庫 — **HIGH confidence**
- [FastAPI WebSocket audio streaming deployment](https://fastapi.tiangolo.com/advanced/websockets/) — FastAPI 官方 WebSocket 文件 — **HIGH confidence**
- 既有原始碼分析：`src/main.py`, `src/api/rest.py`, `src/api/websocket.py`, `src/db/clinical_db.py`, `src/gui/desktop_app.py`, `src/soap/soap_generator.py`, `soapvoice.spec`, `docker-compose.yml` — **HIGH confidence**（直接程式碼驗證）
- 既有專案文件：`.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/HANDOFF.json`, `AGENTS.md` — **HIGH confidence**（專案官方決策記錄）

---

*Architecture research for: SoapVoice v1.1 LAN thin client + database + monitoring integration*
*Researched: 2026-04-24*
