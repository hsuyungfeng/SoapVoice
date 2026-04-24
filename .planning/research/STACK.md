# Stack Research — SoapVoice v1.1 網路部署與資料管理

**Domain:** 醫療語音轉 SOAP 病歷系統 — LAN 瘦客戶端 + 資料持久化 + 儀表板監控 + Linux Wine EXE 驗證
**Researched:** 2026-04-24
**Confidence:** HIGH

> **注意：** 本文件僅涵蓋 v1.1 **新增**功能所需的棧技術。既有棧（Faster-Whisper、llama-cpp-python、ttkbootstrap、FastAPI、PyInstaller 等）保持不變，不在此重複研究。

## Recommended Stack — v1.1 Additions

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **httpx** | ≥0.28.1 | LAN 瘦客戶端 REST 通訊 | 專案已有 `httpx>=0.25.0`，升級至 0.28.1。支援 async/await 原生非阻塞，與 FastAPI 生態完全相容。單一程式庫同時處理同步（GUI 事件迴圈外）與非同步（AST 即時串流）請求。不需 `requests` + `aiohttp` 兩套。 |
| **tenacity** | ≥9.1.4 | 網路重試與容錯 | 提供指數退避重試機制，處理 LAN 環境中 GPU 伺服器斷線、瞬時超時、HTTP 429/503 等狀況。httpx 內建 transport retry 僅處理連線層錯誤，無法應對 HTTP 狀態碼層級錯誤，因此 tenacity 為必要補充。 |
| **aiosqlite** | ≥0.22.1 | FastAPI 端非同步 SQLite | 專案已有大量 sync `sqlite3` 程式碼（`LocalDatabase`、`ClinicalDatabase`、RAG 模組）。v1.1 新增的 **患者記錄 API**（病歷搜尋、看診歷史查詢）需在 async FastAPI 路由中操作資料庫，使用 `aiosqlite` 避免阻塞事件迴圈。sync 版本保留給 CLI 工具與背景初始化腳本。 |
| **sse-starlette** | ≥3.3.4 | 儀表板即時資料推送 (SSE) | 提供標準化 `EventSourceResponse`，自動處理 SSE 規範（事件 ID、ping 心跳、斷線偵測、優雅關閉）。比手寫 `StreamingResponse` 更穩健。選擇 SSE 而非 WebSocket，因儀表板為單向推送（伺服器→監控頁面），無需雙向通訊的額外複雜度。 |
| **psutil** | ≥7.2.2 | GPU 伺服器系統指標擷取 | 跨平台 CPU/記憶體/磁碟/網路指標，無外部依賴。用於儀表板顯示 GPU 伺服器健康狀態（Whisper 模型載入記憶體、LLM 推理延遲、磁碟剩餘空間等）。 |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pydantic** | ≥2.5.0 (既有) | 瘦客戶端請求/回應模型 | 既有。客戶端與伺服器共享 Pydantic schema，確保型別一致性。 |
| **pyyaml** | ≥6.0.0 (既有) | 客戶端設定檔解析 | 既有。LAN 部署設定（伺服器 IP、埠號、JWT token）存為 YAML。 |
| **python-dotenv** | ≥1.0.0 (既有) | 環境變數管理 | 既有。API 金鑰、伺服器端點等敏感設定不硬編碼。 |

### Development Tools (v1.1 Additions)

| Tool | Purpose | Notes |
|------|---------|-------|
| **Wine + WineHQ** | Linux 上測試 Windows EXE | 非 Python 套件。用於 CI/CD 容器化驗證。需 Docker 映像（Ubuntu 24.04 + WineHQ stable + Windows Python 3.11）搭配 `xvfb-run` 執行無頭測試。 |
| **docker** | Wine EXE 驗證容器化 | CI/CD 環境一致性。`Dockerfile` 預裝 WineHQ、Windows Python、PyInstaller 相依性。每次 push 自動重建 EXE 並執行煙霧測試。 |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PostgreSQL / MySQL** | 需要獨立資料庫伺服器行程，與「Windows CPU 全離線」設計哲學衝突。LAN 部署中 GPU 伺服器已是單一節點，SQLite 完全足夠。未來若需水平擴展再遷移。 | **aiosqlite + SQLite WAL 模式** |
| **TinyDB** | Schema-less JSON 儲存。無型別保證、無外鍵約束、無 ACID 交易、大檔案效能崩潰。醫療資料不可承受此風險。 | **SQLite（透過 aiosqlite）** |
| **Peewee ORM** | 額外抽象層。專案已有成熟的 raw SQL + `sqlite3.Row` 模式（`local_database.py`、`clinical_db.py`、`rag/` 模組），加入 ORM 增加學習成本但無對應收益。 | **aiosqlite + 參數化 SQL** |
| **WebSocket（儀表板）** | WebSocket 為雙向通訊設計，有自訂握手協定、連線狀態管理、代理穿透問題。儀表板僅需單向推送（指標→前端），SSE 更簡單且瀏覽器原生自動重連。 | **sse-starlette (SSE)** |
| **Prometheus / Grafana** | 為本地醫療語音工作站建立 Prometheus 棧是大材小用。一個 GPU 伺服器配一個儀表板頁面，不需要時間序列資料庫。 | **psutil + SSE → 自訂儀表板 HTML** |
| **Celery / Redis (任務佇列)** | 既有架構為單一使用者、單一 GPU 伺服器、同步請求-回應模式。v1.1 的 LAN 部署仍為 1-3 個瘦客戶端，不需分散式任務佇列。若流量增長至 10+ 客戶端，再考慮加入。 | **FastAPI 背景任務 (`BackgroundTasks`)** |
| **requests (舊式 HTTP)** | 既有 `httpx` 已提供 async 支援。不應同時維護兩套 HTTP 程式庫。 | **httpx** |

## Stack Integration Points

### 整合矩陣：新套件 × 既有模組

| 新套件 | 使用位置 | 整合方式 |
|--------|----------|----------|
| **httpx 0.28.1** | 新 `src/client/` 模組（瘦客戶端 REST 通訊層） | 既有 `httpx>=0.25.0` 升級。客戶端封裝為 `SoapVoiceClient` 類，提供 `send_audio()`、`send_screenshot_ocr()`、`get_soap()` 方法。 |
| **tenacity 9.1.4** | `src/client/api_client.py`（HTTP 呼叫包裝層） | 裝飾器模式套用於客戶端方法，LAN 瞬斷自動重試 3 次，指數退避 1s→2s→4s。 |
| **aiosqlite 0.22.1** | 新 `src/api/patient_api.py`（患者記錄 REST 端點） | 使用 `fastapi.Depends` + lifespan 初始化連線。WAL 模式啟用。sync 版本 (`src/db/`) 保持不動。 |
| **sse-starlette 3.3.4** | 新 `src/api/dashboard_api.py`（儀表板 SSE 端點） | `EventSourceResponse` 包裝 async generator。既有 `src/main.py` 中註冊路由 `/api/v1/dashboard/stream`。 |
| **psutil 7.2.2** | `src/monitor/system_metrics.py` | 提供 `get_system_metrics()` 函式，回傳 dict（CPU%、記憶體 GB、磁碟%、模型載入狀態）。儀表板 SSE generator 每秒呼叫。 |

### 新增 Python 相依性（pyproject.toml 追加）

```toml
# v1.1 新增相依
"httpx>=0.28.1",          # 從 0.25.0 升級，LAN 瘦客戶端 REST
"tenacity>=9.1.4",        # HTTP 重試與容錯
"aiosqlite>=0.22.1",      # FastAPI 非同步 SQLite
"sse-starlette>=3.3.4",   # SSE 儀表板推送
"psutil>=7.2.2",          # 系統指標監控
```

### 安裝指令

```bash
# 新增 v1.1 套件
uv add httpx tenacity aiosqlite sse-starlette psutil

# 開發相依（若尚未存在）
uv add --group dev pytest pytest-asyncio pytest-cov black ruff
```

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| aiosqlite 0.22.1 | Python 3.8+ / FastAPI 0.115+ | 標準函式庫 `sqlite3` 的非同步包裝，無特殊衝突 |
| sse-starlette 3.3.4 | Starlette 0.38+ / FastAPI 0.115+ | 注意：SSE 路由需停用 GZipMiddleware，否則串流會被緩衝 |
| tenacity 9.1.4 | Python 3.8+ / httpx 0.28.1 | 純 Python，無 C 擴展，跨平台無問題 |
| psutil 7.2.2 | Python 3.6+ (含 3.11) | Linux/Windows 均原生支援，macOS 亦可 |

## Alternatives Considered (Detailed)

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| aiosqlite 0.22.1 | **SQLAlchemy 2.0 (async)** | 若未來需要跨資料庫遷移（SQLite→PostgreSQL）或多節點連線池，SQLAlchemy 的 async engine 提供更高抽象。v1.1 規模不需要。 |
| sse-starlette (SSE) | **WebSocket** | 若儀表板需雙向互動（如從網頁觸發 SOAP 重新生成、暫停/重啟錄音），應使用 WebSocket。目前僅需單向推送。 |
| tenacity 9.1.4 | **httpx 內建 transport retries** | 僅需處理 TCP 連線層瞬斷（非 HTTP 錯誤碼）且不需要指數退避時，可用內建 `HTTPTransport(retries=2)`。幾乎不建議。 |
| psutil 7.2.2 | **prometheus_client** | 若未來需 Grafana 整合或多伺服器聚合指標，Prometheus 是標準方案。v1.1 單伺服器場景不需要。 |

## Sources

### Primary (HIGH confidence)
- **httpx 0.28.1** — [PyPI](https://pypi.org/project/httpx/0.28.1/) + [官方文件](https://www.python-httpx.org/) — 版本、async API、transport retry 限制已驗證
- **tenacity 9.1.4** — [PyPI](https://pypi.org/project/tenacity/9.1.4/) — 版本、API (retry/stop/wait/retry_if)、httpx 整合已驗證
- **aiosqlite 0.22.1** — [PyPI](https://pypi.org/project/aiosqlite/0.22.1/) — 版本、Python 3.11 相容性、WAL mode PRAGMA 已驗證
- **sse-starlette 3.3.4** — [PyPI](https://pypi.org/project/sse-starlette/3.3.4/) — 版本、EventSourceResponse、心跳/斷線偵測已驗證
- **psutil 7.2.2** — [PyPI](https://pypi.org/project/psutil/7.2.2/) — 版本、Python 3.11 相容性已驗證

### Secondary (MEDIUM confidence)
- **SSE vs WebSocket 選擇** — 多篇 2025-2026 技術文章（freeCodeCamp、OneUptime、dev.to）共識：儀表板用 SSE，雙向互動用 WebSocket
- **SQLite 生產環境最佳實踐** — WAL mode + NORMAL synchronous + single-worker deployment 來自多篇 Reddit/HN 討論與實戰經驗
- **Wine Docker 測試流程** — PyInstaller 官方文件 + Medium 技術文章，WINEPREFIX 隔離與 xvfb-run 為標準做法

### Tertiary (LOW confidence — 僅供參考)
- **Peewee vs TinyDB 比較** — 來自一般性技術文章，非醫療領域專門研究。醫療資料的 schema 強制性為通用軟體工程原則，不需領域特定驗證。
- **Celery/Redis 不推薦** — 基於專案規模（1-3 客戶端）的架構判斷，非實證資料。若未來流量增長需重新評估。

---
*Stack research for: SoapVoice v1.1 — 網路部署與資料管理*
*Researched: 2026-04-24*
*Author: GSD research agent — spawned by `/gsd-new-milestone` Phase 6*
