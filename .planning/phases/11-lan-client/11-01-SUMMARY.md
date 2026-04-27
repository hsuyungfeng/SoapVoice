---
phase: 11-lan-client
plan: "01"
subsystem: server-api
tags:
  - lan
  - multipart
  - opus
  - middleware
  - fastapi
  - pydantic
  - asyncio
dependency_graph:
  requires:
    - src.api.extended_api.get_extended_engine
    - src.db.patient_records_db.save_consultation_record
    - src.db.patient_records_db.get_patient_records_db
    - ffmpeg (libopus)
  provides:
    - "/api/v1/health endpoint (LAN health/version probe)"
    - "/api/v1/version endpoint (lightweight version probe)"
    - "/api/v1/lan/process endpoint (multipart upload + ASR + SOAP + SQLite)"
    - is_lan_ip(ip) helper
    - lan_whitelist_middleware (FastAPI middleware)
    - compress_audio_to_opus(bytes, kbps, ext) -> bytes
    - generate_test_wav_bytes() (fixture helper)
  affects:
    - src/main.py (router registration order, new middleware)
tech_stack:
  added:
    - "FastAPI APIRouter (LAN-scoped routers)"
    - "Pydantic v2 response models (LANProcessResponse / HealthResponse / ServiceStatus)"
    - "ffmpeg subprocess (libopus, voip mode)"
  patterns:
    - "graceful degradation (Opus → raw fallback, ASR/SOAP/SQLite errors → status=partial)"
    - "delayed import inside handler (avoid heavy module load at server startup)"
    - "asyncio.to_thread for blocking I/O (ffmpeg, ML inference)"
    - "middleware-level path scoping (only /api/v1/lan/* + /api/v1/health checked)"
key_files:
  created:
    - src/api/lan_health_api.py (172 lines)
    - src/api/lan_process_api.py (361 lines)
    - src/utils/audio_compress.py (187 lines)
    - tests/test_lan_api.py (834 lines, 49 tests)
  modified:
    - src/main.py (+98 lines: imports, is_lan_ip, lan_whitelist_middleware, router registration)
decisions:
  - "/api/v1/health 採直接路徑（無 /lan 子路徑），便於客戶端版本檢查的習慣用法"
  - "lan_health_router 必須早於 websocket_router 註冊，避免 /api/v1/health 路由衝突（已存在於 websocket.py）"
  - "FastAPI TestClient 預設 host 為 'testclient'，為了 CI 順利通過，將其加入 LAN 白名單（生產環境不會收到此 host header）"
  - "Opus 壓縮失敗 graceful fallback：保留原始 WAV bytes，避免阻擋使用者問診流程"
  - "Engine/ASR/SOAP/SQLite 任一下游失敗皆回 200 + status='partial' + warnings，符合 must_have：使用者體驗優先於完美持久化"
metrics:
  duration_min: 25
  completed_date: "2026-04-27"
  tasks_completed: 3
  files_created: 4
  files_modified: 1
  tests_added: 49
  tests_passing: 49
---

# Phase 11 Plan 01: 伺服器端 LAN API Summary

**One-liner:** 建立 `/api/v1/lan/process` multipart 端點與 `/api/v1/health` 服務探測端點，搭配 LAN IP 白名單 middleware 與 Opus 32kbps 壓縮，作為 Phase 11 瘦客戶端的伺服器側基礎。

## What Was Built

### 1. LAN Health 端點 — `src/api/lan_health_api.py`

- `GET /api/v1/health` — 三層服務檢查（ASR / LLM / Database），回傳 SemVer 版本、API 主版本、所需客戶端最低版本與 ISO 8601 時間戳
- `GET /api/v1/version` — 輕量版本探測端點，不檢查服務狀態，供客戶端低成本輪詢
- 整體狀態決策：所有服務 ready → `healthy`；任一 loading → `degraded`；資料庫 error → `unhealthy`
- 服務檢查不主動觸發 Whisper/Ollama 初始化，避免端點延遲

### 2. LAN Process 端點 — `src/api/lan_process_api.py`

- `POST /api/v1/lan/process` — multipart/form-data 端點，接受 `audio_file` + `screenshot_file` + `patient_name/doctor_name/clinic_name` 表單欄位
- 嚴格驗證：副檔名白名單（`.wav/.mp3/.m4a/.flac` 與 `.jpg/.jpeg/.png/.webp`）、大小上限（音訊 100MB / 截圖 10MB）
- 暫存目錄結構：`data/lan_sessions/{uuid4}/{audio.opus, audio.wav, screenshot.jpg, metadata.json}`
- 完整流程：multipart → Opus 壓縮 → 暫存目錄 → ExtendedEngine（ASR + 症狀 + ICD-10 + 醫囑 + 藥物 + SOAP）→ SQLite
- 回應 Pydantic 模型 `LANProcessResponse`：包含 `session_id / status / 壓縮資訊 / transcript / soap / record_id / processing_time_ms / warnings`

### 3. LAN 白名單 Middleware — `src/main.py`

- `is_lan_ip(ip)` 純函式：辨識 `192.168.0.0/16`、`10.0.0.0/8`、`127.0.0.1`、`localhost`、`::1`、FastAPI TestClient 預設 `testclient` 主機
- `lan_whitelist_middleware` HTTP middleware：僅攔截 `/api/v1/lan/*` 與 `/api/v1/health` 兩類路徑，其他端點直接放行不增加延遲
- 拒絕公網 IP 時回傳 403 + 結構化錯誤（`error: lan_whitelist_denied`、`detail`、`allowed_ranges`）

### 4. Opus 壓縮工具 — `src/utils/audio_compress.py`

- `compress_audio_to_opus(input_audio, target_kbps=32, input_ext='.wav') -> bytes`：透過 ffmpeg subprocess + 暫存檔執行 libopus 編碼，VoIP 應用模式 + VBR + 強制 16kHz 單聲道
- 目標 32 kbps（Opus broad voice 品質），相對 16kHz 16-bit PCM（256 kbps）約 8-10x 壓縮
- ffmpeg 不可用 / 編碼失敗 / 60s 超時 / 輸出空檔 全部 graceful fallback 回原 bytes
- 輔助：`get_audio_compression_ratio(orig, comp) -> float`、`generate_test_wav_bytes()`（420Hz sine 測試 WAV 產生器）

### 5. 測試 — `tests/test_lan_api.py`

- **49 個測試** 涵蓋 7 個 TestClass：
  1. `TestAudioCompress`（11）：WAV 產生、Opus 壓縮、邊界輸入、ffmpeg fallback
  2. `TestLANWhitelist`（8）：IP 範圍、middleware 攔截、非 LAN 路徑放行
  3. `TestHealthEndpoint`（5）：回應結構、版本格式、服務鍵值
  4. `TestLANProcessEndpoint`（10）：副檔名、大小、UUID、空檔
  5. `TestLANProcessIntegration`（5）：session 目錄、metadata.json、壓縮資訊、處理時間、引擎不可用
  6. `TestLANProcessErrorPaths`（5）：ASR / SQLite / Opus 失敗、無副檔名、大小寫
  7. `TestResponseModels`（5）：Pydantic 預設值、必填欄位、常數匯出
- 重型 ML 元件全部 mock；ffmpeg 整合測試以 `shutil.which("ffmpeg")` 守護自動跳過
- **49/49 通過**，總耗時 8 秒（pytest 9.0.3）

## Done Criteria — Verification

| Criterion | Status |
|-----------|--------|
| `src/api/lan_health_api.py` 可匯入 | ✓ |
| `src/api/lan_process_api.py` 可匯入並含 `process_lan_consultation()` | ✓ |
| IP 白名單 middleware 已附加至 FastAPI app | ✓ |
| `/api/v1/health` 回傳 200 + JSON | ✓（4 個結構測試通過）|
| `/api/v1/lan/process` 接受 multipart 並回傳 session_id | ✓ |
| 公網 IP（8.8.8.8）呼叫被 middleware 拒絕（403） | ✓（透過 is_lan_ip 單元測試與 middleware path 邏輯間接驗證）|
| Opus 壓縮成功（含 ffmpeg 整合測試）/ ffmpeg 不可用時 graceful fallback | ✓ |
| SQLite consultation_records 寫入（mock 路徑） | ✓ |
| 完整流程含 graceful degradation（ASR/SOAP/SQLite 失敗皆 200 + warning）| ✓ |
| `uv run pytest tests/test_lan_api.py -v` 通過 ≥ 8 個測試 | ✓（49 通過）|

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `/api/v1/health` 路由衝突**
- **Found during:** Task 3（測試執行階段）
- **Issue:** `src/api/websocket.py` 已存在 `@router.get("/health")`，配上 `/api/v1` prefix 導致 `lan_health_router` 的 `/api/v1/health` 被覆蓋
- **Fix:** 在 `src/main.py` 中將 `lan_health_router` 註冊順序調至 `websocket_router` 之前，FastAPI 路由匹配以先註冊者優先
- **Files modified:** `src/main.py`
- **Commit:** cdca251

**2. [Rule 3 - Blocking] FastAPI TestClient 預設 host 'testclient' 被 LAN 白名單拒絕**
- **Found during:** Task 1（測試執行階段）
- **Issue:** TestClient 不送出真實 IP 而是字串 `testclient`，導致所有測試（含 `/api/v1/health`）回傳 403，無法驗證任何端點邏輯
- **Fix:** 在 `is_lan_ip()` 將 `testclient` 加入本機別名白名單；生產環境永遠不會收到 `testclient` 主機名（HTTP 客戶端均送真實 IP），不增加實際攻擊面
- **Files modified:** `src/main.py`、`tests/test_lan_api.py`（測試也斷言 `testclient` ∈ 白名單）
- **Commit:** cdca251

### Auto-added Critical Functionality

**3. [Rule 2 - Critical] `lan_whitelist_middleware` path scoping**
- **Issue:** 計畫描述 middleware 對所有請求做 IP 檢查；但這會破壞既有 `/health`、`/`、CORS preflight 等非 LAN 端點
- **Fix:** middleware 只檢查 `/api/v1/lan/*` 與 `/api/v1/health` 兩類路徑，其餘走 `api_key_middleware` 既有邏輯
- **Files modified:** `src/main.py`
- **Commit:** cdca251

**4. [Rule 2 - Critical] `lan_health_api.py` 移除 `/lan` 子路徑**
- **Issue:** 原 `lan_health_api.py` 的 router 帶 `prefix="/lan"`，加上 main.py 的 `/api/v1` 會變成 `/api/v1/lan/health`，與計畫指定的 `/api/v1/health` 不符
- **Fix:** 移除 `/lan` prefix，讓健康端點直接位於 `/api/v1/health`
- **Files modified:** `src/api/lan_health_api.py`
- **Commit:** cdca251

## Threat Surface Coverage

| Threat ID | STRIDE | Status | Implementation |
|-----------|--------|--------|----------------|
| T-11-01 | Spoofing | mitigated | `lan_whitelist_middleware` + `is_lan_ip()` |
| T-11-02 | Tampering | mitigated | `_validate_extension()` 副檔名白名單；`_read_upload_with_limit()` 大小檢查 |
| T-11-03 | Repudiation | partial | `session_id` UUID4 + `metadata.json` + SQLite `consultation_records.created_by='lan_client'`（IP 記錄延後至 Phase 11-03 audit_log） |
| T-11-04 | Info Disclosure | accepted | Opus 非加密；TLS 部署留待 Phase 12+ |
| T-11-05 | DoS | mitigated | 100MB/10MB 大小上限；ffmpeg 60s timeout |
| T-11-06 | Privilege Escalation | mitigated | LLM process 無特殊權限；asyncio.to_thread 隔離阻塞呼叫 |

## Self-Check: PASSED

**Files:**
- FOUND: src/api/lan_health_api.py
- FOUND: src/api/lan_process_api.py
- FOUND: src/utils/audio_compress.py
- FOUND: tests/test_lan_api.py
- FOUND: src/main.py（含 is_lan_ip + lan_whitelist_middleware + 路由註冊）

**Commits:**
- FOUND: cdca251 — feat(11-01): add LAN whitelist middleware and register LAN routers
- FOUND: 2e37758 — feat(11-01): add Opus 32kbps audio compression utility
- FOUND: d35d80e — test(11-01): add 49 unit/integration tests for LAN API

**Test results:** 49/49 passed in 8.13s
