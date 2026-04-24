# Project Research Summary

**Project:** SoapVoice — 醫療語音轉 SOAP 病歷系統
**Domain:** 醫療 AI — LAN 瘦客戶端擴展、資料持久化、監控儀表板
**Researched:** 2026-04-24
**Confidence:** HIGH（四份研究報告均為 HIGH 信心，多來源交叉驗證）

## Executive Summary

SoapVoice v1.1 的核心轉型是從「單機一體式 GPU 工作站」升級為「LAN 瘦客戶端架構」：一個 Linux GPU 伺服器服務多台 Windows 精簡客戶端。這是醫療 AI 系統的標準演進路徑——診所通常有 1-3 個診間，共用一台 GPU 伺服器遠比每間都裝 RTX 3060 來得經濟且易於維護。

研究推薦的 v1.1 技術棧極簡且務實：**httpx + tenacity** 處理 LAN 通訊與容錯、**aiosqlite** 讓 FastAPI 端非同步操作 SQLite、**sse-starlette** 提供儀表板即時推送、**psutil** 擷取系統指標。明確拒絕 PostgreSQL、Prometheus/Grafana、Celery/Redis 等對單一診所規模過度設計的技術。核心架構策略是將既有單體拆分為「客戶端（capture-only）+ 伺服器（processing + storage）」，客戶端完全不 import 推理模組，僅透過 HTTP REST 呼叫伺服器。

關鍵風險集中在兩個方面：(1) **LLM 推理阻塞 event loop** — llama-cpp-python 的 `generate()` 是同步 GPU 操作，若在 FastAPI async handler 內直接呼叫會凍結所有其他請求，必須用獨立 process + semaphore 解耦；(2) **SQLite 並行寫入競爭** — WAL 模式、busy_timeout、寫入佇列三者缺一不可，否則多醫師同時儲存 SOAP 時記錄會靜默流失。另外，Wine EXE 驗證僅能做語法/啟動測試，不可替代 Windows 實機驗證——這是 PyInstaller 官方文件明確申明的限制。

## Key Findings

### Recommended Stack

v1.1 僅新增 5 個核心套件，既有棧（Faster-Whisper、llama-cpp-python、ttkbootstrap、FastAPI）保持不變：

| Technology | Purpose | Key Rationale |
|------------|---------|---------------|
| **httpx ≥0.28.1** | LAN 瘦客戶端 REST 通訊 | 既有 `httpx≥0.25.0` 升級，async/await 原生支援，單一程式庫取代 `requests` + `aiohttp` |
| **tenacity ≥9.1.4** | 網路重試與容錯 | 指數退避處理 LAN 瞬斷、HTTP 503，httpx 內建 transport retry 無法處理 HTTP 狀態碼錯誤 |
| **aiosqlite ≥0.22.1** | FastAPI 端非同步 SQLite | 患者記錄 API 需 async 查詢，避免阻塞 event loop；sync 版本保留給 CLI/初始化腳本 |
| **sse-starlette ≥3.3.4** | 儀表板即時推送 (SSE) | 標準化 EventSourceResponse，單向推送無需 WebSocket 的雙向複雜度；瀏覽器原生自動重連 |
| **psutil ≥7.2.2** | 系統指標擷取 | 跨平台 CPU/記憶體/磁碟指標，儀表板顯示 GPU 伺服器健康狀態 |

**明確拒絕的技術：** PostgreSQL/MySQL（單機 SQLite 足夠）、TinyDB（無 ACID/型別保證）、Peewee ORM（額外抽象無收益）、WebSocket 用於儀表板（過度設計）、Prometheus/Grafana（單伺服器不需要時間序列資料庫）、Celery/Redis（1-3 客戶端不需要分散式佇列）。

### Expected Features

**Must have（v1.1 發佈必須 — P1）：**

| Feature | Why Critical |
|---------|-------------|
| Thin Client: 音檔 + 截圖上傳至伺服器 | 實現 LAN 瘦客戶端的基礎傳輸層 |
| Thin Client: SOAP 結果接收與顯示 | 醫師完成問診後須在客戶端 GUI 看到病歷 |
| Patient Record Persistence（SQLite） | 每次問診的 SOAP、音檔、逐字稿、metadata 結構化儲存 |
| Patient Search by Name/Date | 醫師回溯查詢病患歷史記錄，含分頁 |
| Network Error Handling & Session Auto-Save | LAN 斷線提示 + 本地暫存錄音（時間戳命名，非固定 temp.wav） |
| Wine EXE Smoke Test | 啟動 → 健康檢查 → 正常關閉 |
| README Complete Rewrite | 反映 v1.1 thin client 架構 |

**Should have（v1.1.x 後續 — P2）：** GPU 監控儀表板（pynvml + Chart.js）、症狀搜尋、Local CPU Fallback、Wine Docker CI/CD、Bulk Export。

**Defer to v2+：** Docker 容器化部署、多機構/多租戶架構、EHR/EMR 直接整合（每家 HIS 不同，OCR 方案已足夠務實）、行動 App。

**競爭差異化：** SoapVoice 是唯一同時具備「全離線、LAN 部署、繁體中文、OCR 萃取、GPU 加速」的開源醫療語音 SOAP 系統。v1.1 的 LAN thin client 進一步拉開與 DeepScribe、Suki AI 等差異。

### Architecture Approach

v1.0 單體架構拆分為 **客戶端（capture-only）+ 伺服器（processing + storage）**，通訊僅透過 HTTP REST/WebSocket：

```
[Windows EXE Client]  ←── LAN ──→  [Linux GPU Server]
 ├── GUI 側邊欄 (ttkbootstrap)       ├── FastAPI (0.0.0.0:8010)
 ├── 麥克風錄音 → WAV 上傳          ├── ASR (Faster-Whisper, GPU)
 ├── 螢幕截圖 → PNG 上傳            ├── NLP + SOAP 管線
 ├── 本地暫存 (離線備援)             ├── LLM (Gemma 4:E4B, GPU)
 └── API Client (httpx)             ├── SQLite 資料持久層
                                     ├── 監控儀表板 (SSE)
                                     └── Prometheus /metrics
```

**重要架構決策：**

1. **客戶端不 import 任何推理模組** — `client/` 目錄與 `src/` 完全隔離，僅透過 HTTP 協議通訊。這是防止 EXE 體積暴增和循環依賴的硬邊界。
2. **資料持久化使用 aiosqlite + 參數化 SQL**（非 ORM）— 既有 `sqlite3.Row` + raw SQL 模式成熟、效能佳，新增患者記錄 API 使用 `aiosqlite` 保持 async 相容。既有 `LocalDatabase`/`ClinicalDatabase` 內部重構但不改外部介面。
3. **既有單例保留，內部升級** — `get_clinical_db()` 等 5 個模組層級單例保留不變，內部改用 async session 管理，避免大規模重構。
4. **儀表板用 SSE 非 WebSocket** — 監控為單向推送，SSE 更簡潔（瀏覽器原生自動重連、無自訂握手協定）。
5. **LLM 推理必須解耦** — 使用獨立 process + `asyncio.Semaphore(1)` + 內部佇列，防止阻塞 event loop 和 VRAM 競爭。

**建置順序：** DB 持久層 → 客戶端分離（可與儀表板平行） → 儀表板 → Wine EXE 驗證 → 技術文件。

### Critical Pitfalls

1. **Event Loop 凍結（LLM 推理阻塞）** — llama-cpp-python 的 `generate()` 是同步 GPU 操作，在 async handler 內直接呼叫會凍結所有其他請求（含 `/health`）。**避免：** LLM 推理移至獨立 process + `asyncio.Semaphore(1)`，API 層僅做路由與排隊通知。

2. **SQLite 寫入競爭導致記錄流失** — 多醫師同時寫入 `soap_records` 時觸發 `SQLITE_BUSY`，現有程式碼無 busy_timeout 也無重試。**避免：** 啟用 WAL 模式 + `PRAGMA busy_timeout=5000` + 序列化寫入（asyncio.Lock 或背景 writer）。

3. **SOAP 審計追蹤缺失（醫療合規風險）** — 直接 UPDATE SOAP 欄位違反醫療記錄不可竄改原則。**避免：** append-only 設計（version 遞增，不 UPDATE）+ 獨立審計表記錄所有 CREATE/READ/AMEND 操作。

4. **Wine EXE 驗證的虛假信心** — Wine 下「看似正常」≠ Windows 實機正常。PyInstaller 不支援交叉編譯。**避免：** Wine 僅用於 CI 語法/啟動測試，功能驗證必須在真實 Windows 10/11 或 `windows-latest` CI runner 上執行。

5. **API 版本不一致導致靜默失敗** — 伺服器 API 更新後舊版客戶端 EXE 送錯格式，僅顯示「API 錯誤」卻不提示更新。**避免：** 客戶端啟動時檢查版本（`GET /api/v1/version`），不相容時強制彈窗提示；伺服器 API 採 Tolerant Reader 模式（只加不刪）。

## Implications for Roadmap

基於研究的建議階段結構（對應既有專案 Phase 10-14）：

### Phase 10: 資料持久層重構（DB Persistence）

**Rationale:** 這是所有後續功能的基礎——病人搜尋、監控分析、session 持久化都依賴結構化資料儲存。無上游依賴，可立即啟動。

**Delivers:**
- `patient_records` 表結構（含審計追蹤 `soap_audit_log`）
- `src/db/patient_records_db.py`（aiosqlite + 參數化 SQL）
- 既有 `SessionManager._sessions` (in-memory dict) → DB 持久化
- 錄音檔時間戳命名策略（`YYYYMMDD_HHMMSS_sessionid.wav`）

**Avoids:** 陷阱 2（SQLite 寫入競爭）、陷阱 5（審計追蹤缺失）、陷阱 10（無備份驗證）

**Research Flag:** 既有 raw SQL 模式已成熟，但審計追蹤的 schema 設計需要與醫師討論（哪些操作需要記錄、保留期限）。建議 `gsd-discuss-phase` 時確認醫療合規需求。

### Phase 11: LAN 瘦客戶端分離（Thin Client）

**Rationale:** 實現 v1.1 核心價值——讓 Windows EXE 可透過 LAN 使用 GPU 伺服器。依賴 Phase 10 的 DB schema 定義（用於上傳後的 SOAP 儲存）。

**Delivers:**
- `client/` 目錄結構（`thin_app.py`, `api_client.py`, `audio_recorder.py`, `screen_capture.py`）
- `POST /api/v1/thin/upload` 端點（multipart: audio.wav + screen.png）
- `GET /api/v1/version` 端點（客戶端版本檢查）
- 客戶端本地暫存機制（離線佇列 + 時間戳命名）
- LAN 斷線提示 GUI 指示器（綠/黃/紅燈）
- `soapvoice-client.spec`（輕量 PyInstaller spec，不含推理模組）

**Avoids:** 陷阱 1（Event loop 阻塞）、陷阱 3（API 版本不一致）、陷阱 8（離線錄音遺失）、陷阱 9（VRAM 競爭）

**Research Flag:** 客戶端與伺服器 API 合約需要 `gsd-discuss-phase` 時精確定義（欄位名稱、必填/選填、錯誤碼）。LLM 推理的 process 隔離模式需要在 `gsd-plan-phase` 時 spike 驗證。

### Phase 12: GPU 監控儀表板（Dashboard + Metrics）

**Rationale:** 診所 IT 人員需要監控 GPU 使用率與處理佇列。與 Phase 10/11 無硬依賴，可平行開發。

**Delivers:**
- `src/api/metrics_api.py`（SSE 即時串流端點）
- `src/monitor/system_metrics.py`（psutil + 可選 pynvml）
- `static/dashboard.html`（Chart.js 三面板：GPU 儀表、請求趨勢、處理時間分布）
- `GET /api/v1/monitor/stream`（SSE，每 2 秒推送）
- 監控數據記憶體快取（避免每次請求查 DB/nvidia-smi）

**Avoids:** 陷阱 7（Dashboard 輪詢拖垮伺服器）

**Research Flag:** 標準 SSE 模式，`gsd-research-phase` 可跳過。但 pynvml API 在 llama-cpp-python 環境下的並行行為需在 `gsd-plan-phase` 時釐清。

### Phase 13: Wine EXE 驗證（CI Integration）

**Rationale:** 確保 Windows EXE 在 Wine 下可啟動。依賴 Phase 11 的 `soapvoice-client.spec` 可建置。

**Delivers:**
- `.github/workflows/wine-test.yml`（GitHub Actions CI）
- `tests/wine/test_exe_launch.py`（L1 Smoke Test：啟動 → 無 crash）
- `scripts/wine_wrapper.sh`
- 明確區分 Wine 測試範圍（僅語法/啟動，不驗證功能）

**Avoids:** 陷阱 4（Wine EXE 虛假信心 — 明確標註 Wine 測試 ≠ Windows 驗證）

**Research Flag:** 標準 CI/CD 模式，`gsd-research-phase` 可跳過。Windows 實機測試清單需在 `gsd-execute-phase` 時手動驗證。

### Phase 14: 技術文件重寫（Documentation）

**Rationale:** v1.1 架構大幅變更，現有 README.md 仍描述 v0.8 CLI。需彙整所有 v1.1 功能後重寫。

**Delivers:**
- README.md 全面重寫（LAN 架構圖、部署指南、API 文件、FAQ）
- ARCHITECTURE.md 更新
- AGENTS.md 更新

**Research Flag:** 文件標準已有研究建議，`gsd-research-phase` 可跳過。

### Phase Ordering Rationale

- **資料持久層必須先行**：病人搜尋、session 持久化、監控分析都依賴結構化儲存。Phase 10 是所有下游功能的基礎。
- **客戶端與儀表板可平行**：Phase 11（客戶端）和 Phase 12（儀表板）之間無直接依賴。但 Phase 11 需等 Phase 10 的資料模型定義完成。
- **Wine 驗證自然在客戶端之後**：沒有可建置的客戶端 EXE 就無法執行 Wine 測試。
- **文件最後**：需彙整所有功能內容。
- **LLM 推理解耦應貫穿全階段**：陷阱 1（事件迴圈凍結）和陷阱 9（VRAM 競爭）不是某個階段的問題，而是架構設計決策。Phase 11 的 `POST /api/v1/thin/upload` 端點設計時就必須將推理放入獨立 process。

### Research Flags

**建議執行 `gsd-research-phase` 的階段：**
- **Phase 10（資料持久層）：** 審計追蹤 schema 需符合台灣醫療法規（《醫療法》第 67-70 條）— 建議研究具體合規要求
- **Phase 11（LAN 瘦客戶端）：** LLM 推理 process 隔離模式的具體實作（`ProcessPoolExecutor` vs `multiprocessing.Queue` vs llama.cpp server mode）需要 spike 驗證
- **Phase 11（LAN 瘦客戶端）：** PyInstaller 輕量打包（僅含 client/ 模組，排除 `src/asr`、`src/llm`、GGUF 模型）的 hook 設定需要研究

**可跳過 `gsd-research-phase` 的階段：**
- **Phase 12（儀表板）：** SSE + Chart.js 是成熟模式，多篇 2025-2026 文章提供完整範例
- **Phase 13（Wine CI）：** GitHub Actions + Wine + xvfb-run 是標準做法，PyInstaller 官方文件已提供指引
- **Phase 14（文件）：** 文件結構已有研究建議的模板

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | 所有推薦套件均有 PyPI 官方頁面驗證版本、Python 3.11 相容性、FastAPI 整合方式。替代方案決策有明確理由與觸發條件。 |
| Features | **HIGH** | P1/P2/P3 分級基於既有程式碼分析（確認哪些已有、哪些需新建）與 Google Search 交叉驗證的競爭者分析。邊界案例與錯誤處理已詳細列舉。 |
| Architecture | **HIGH** | 既有架構經 `src/` 全目錄程式碼分析確認；v1.1 模組歸屬決策有明確理由（GPU 密集 → 伺服器，capture-only → 客戶端）。既有單例相容策略確保向後相容。 |
| Pitfalls | **HIGH** | 9 個關鍵陷阱均有多來源驗證（Context7 + 官方文件 + WebSearch），且針對 SoapVoice 既有程式碼（如 `sqlite3.connect()` 每次新建、`temp.wav` 固定檔名、無 busy_timeout）進行了逐項對照。 |

**Overall confidence:** HIGH

### Gaps to Address

1. **SQLAlchemy vs aiosqlite + raw SQL 的架構張力：** ARCHITECTURE.md 推薦 SQLAlchemy 2.0+ async + Alembic，但 STACK.md 明確拒絕 ORM（除 Peewee 外）並推薦 aiosqlite + 參數化 SQL。兩者的核心分歧在於：既有程式碼已有成熟的 raw SQL 模式（2000+ 行 `sqlite3` 程式碼），加入 ORM 是否值得遷移成本。**建議：** 在 Phase 10 規劃時討論——若僅新增 1-2 張表，raw SQL + aiosqlite 更務實；若未來 schema 頻繁變更，SQLAlchemy 的遷移管理價值才顯現。短期推薦 **aiosqlite + raw SQL**（與 STACK.md 一致），預留未來升級空間。

2. **GPU 監控的 pynvml 可用性：** 研究假設伺服器有 NVIDIA GPU（RTX 3060），但如果未來改用 AMD GPU 或 Intel Arc，pynvml 將不可用。psutil 是跨平台的替代方案但缺少 VRAM 用量。**建議：** Phase 12 設計時將監控後端抽象化（`pynvml` → fallback `psutil` → fallback 純文字提示）。

3. **LAN 安全性未深入：** 研究提到 API Key + JWT 認證（已實作），但未詳細討論 HTTPS（自簽憑證）、SQLite 加密（SQLCipher）、錄音檔傳輸加密。**建議：** Phase 11 規劃時討論 LAN 環境下的安全策略——自簽 HTTPS 的成本低（Let's Encrypt 不可用於 LAN），但 API-level 加密 payload 更簡單。

4. **Windows Auto-Start/Service 模式：** FEATURES.md 未涉及客戶端 EXE 的開機自動啟動或安裝程式（Inno Setup）。**建議：** Phase 11 或 Phase 13 規劃時確認是否需要安裝程式，現有 `scripts/build_windows.sh` 僅產出 portable EXE。

5. **台灣醫療法規合規細節：** 審計追蹤的具體欄位（保留年限、簽章格式）需要與醫師討論。研究提供了通用審計模式（append-only、HMAC 簽章），但未確認台灣《醫療法》第 67-70 條的具體要求。

## Sources

### Primary (HIGH confidence)
- **httpx 0.28.1** — [PyPI](https://pypi.org/project/httpx/0.28.1/) + [官方文件](https://www.python-httpx.org/) — 版本、async API、transport retry 限制已驗證
- **tenacity 9.1.4** — [PyPI](https://pypi.org/project/tenacity/9.1.4/) — retry/stop/wait/retry_if API 已驗證
- **aiosqlite 0.22.1** — [PyPI](https://pypi.org/project/aiosqlite/0.22.1/) — Python 3.11 相容性、WAL mode PRAGMA 已驗證
- **sse-starlette 3.3.4** — [PyPI](https://pypi.org/project/sse-starlette/3.3.4/) — EventSourceResponse、心跳/斷線偵測已驗證
- **psutil 7.2.2** — [PyPI](https://pypi.org/project/psutil/7.2.2/) — Python 3.11 相容性已驗證
- **PyInstaller** — [官方文件](https://pyinstaller.org/) 明確指出不支援交叉編譯
- **既有程式碼分析** — `src/` 全目錄（以下模組逐一驗證）：`main.py`, `api/rest.py`, `api/websocket.py`, `gui/desktop_app.py`, `db/clinical_db.py`, `db/local_database.py`, `consultation/session_manager.py`, `security/auth.py`, `soap/soap_generator.py`, `soapvoice.spec`
- **既有專案文件** — `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `AGENTS.md`

### Secondary (MEDIUM confidence)
- **SSE vs WebSocket 選擇** — 2025-2026 技術文章（freeCodeCamp、OneUptime、dev.to）共識：儀表板用 SSE，雙向互動用 WebSocket
- **SQLite 生產環境最佳實踐** — WAL mode + NORMAL synchronous + single-worker deployment（Reddit/HN 討論）
- **FastAPI thin client 架構** — LAN medical application patterns 2025（Google Search）
- **醫療軟體文件結構標準** — IEC 62304 合規指引

### Tertiary (LOW confidence — 僅供參考)
- **Peewee vs TinyDB 比較** — 一般性技術文章，非醫療領域專門研究
- **Celery/Redis 不推薦** — 基於專案規模的架構判斷，若流量增長需重新評估
- **台灣《醫療法》第 67-70 條** — 審計追蹤的具體合規要求未詳細研究，建議 Phase 10 規劃時進一步確認

---

*Research completed: 2026-04-24*
*Ready for roadmap: yes*
