---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: 網路部署與資料管理
status: in_progress
stopped_at: Phase 11-03 complete (2026-04-27)
last_updated: "2026-04-27T16:30:00.000Z"
last_activity: 2026-04-27 — Phase 11-03 完成（本機暫存 + 指數退避重試 + 60 client 測試通過）
progress:
  total_phases: 5
  completed_phases: 1
  planned_phases: 1
  total_plans: 13
  completed_plans: 6
  planned_plans: 1
  percent: 46
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-24)

**Core value:** 語音自動轉錄為專業 SOAP 病歷，讓醫師專注問診而非打字
**Current focus:** Phase 11 — LAN 瘦客戶端（11-01 + 11-02 + 11-03 完成 → 下一步整合測試 / Windows 部署）

## Current Position

Phase: 11 of 14 (LAN 瘦客戶端)
Plan: 11-03 完成 → 下一步 11-04 (整合測試 / Windows 部署)
Status: in_progress
Last activity: 2026-04-27 — Phase 11-03 執行完成（60/60 client tests pass，含 22 新增）

Progress: [██████████░] 46% (6/13 v1.1 計畫已完成，1/13 已規劃)

## Phase 11-03 Completion Summary (2026-04-27)

✅ **Phase 11-03: 本機暫存與重試機制 — COMPLETE**

**Deliverables:**
- `client/local_storage.py` — `LocalStorageManager` + `PendingUpload` dataclass（303 行）
- `client/retry_manager.py` — `RetryManager` 指數退避 2-4-8 秒（193 行）
- `client/lan_client.py` — 整合本機暫存 + 自動重試（524 行，從 381 → 524）
- `client/main.py` — 顯式 import key_link（+2 行）
- `tests/test_client.py` — 22 新測試 + 2 schema 修正（1507 行，從 997 → 1507）

**Commits:**
- 2609705 — feat(11-03): add LocalStorageManager for client offline queue
- 34d8d71 — feat(11-03): add RetryManager with exponential backoff
- 7a798a2 — feat(11-03): integrate LocalStorageManager + RetryManager into LANClient

**Test Coverage:** 60/60 通過 (2.02s)
- TestLocalStorageManager (9) ✓ — add/save/load/remove/overflow/retry_count/corrupt/clear/serialization
- TestRetryManager (6) ✓ — backoff/should_retry/next_delay/wait/state/defaults
- TestLANClientRetry (7) ✓ — restore/queue/success/failure/max_retries/health_recovery/session_id_format
- 既有 38 測試 + 22 新測試 = 60

**Key Decisions:**
- 採單一 queue.json 集中管理（原子寫入：tmp + replace），避免散檔導致同步漏寫
- PendingUpload 採 dataclass + asdict / from_dict（容錯：缺欄位以預設值補齊）
- 隊列上限 10 筆（先 drop_oldest 再 append，避免短暫超限）
- 指數退避 2-4-8 秒（base=2.0, multiplier=2.0, max_retries=3）
- 連線恢復觸發點：unknown→healthy 與 offline→healthy 皆觸發補傳
- _retry_in_progress 旗標避免 retry coroutine 重入
- FileNotFoundError 期間自動清出隊列（不可復原）

---

## Phase 11-02 Completion Summary (2026-04-27)

✅ **Phase 11-02: Windows 瘦客戶端 GUI — COMPLETE**

**Deliverables:**
- `client/__init__.py` — 套件入口（15 行）
- `client/lan_config.py` — `LANConfig` dataclass（92 行）
- `client/http_client.py` — `AsyncHTTPClient` + tenacity 重試（190 行）
- `client/lan_client.py` — `LANClient` 健康狀態機 + 上傳 + 暫存佇列（381 行）
- `client/audio_recorder.py` — `AudioRecorder` PyAudio 16kHz mono（194 行）
- `client/screenshot_capture.py` — `ScreenshotCapture` PIL/mss（100 行）
- `client/gui.py` — Tkinter `SOAPVoiceGUI` + `ConnectionIndicator` + `SOAPPanel`（420 行）
- `client/main.py` — `App` 控制器 + `AsyncRunner` 背景事件迴圈（410 行）
- `tests/test_client.py` — 38 個 client 單元/整合測試（997 行）

**Commits:**
- c650402 — feat(11-02): add LAN client core (config, HTTP client, LANClient + 21 tests)
- 3b917b1 — feat(11-02): add Tkinter GUI (ConnectionIndicator, SOAPPanel, SOAPVoiceGUI)
- a8fda61 — feat(11-02): add client entrypoint App + AsyncRunner + 14 new tests

**Test Coverage:** 38/38 通過 (0.43s)
- TestLANConfig (4) ✓
- TestAsyncHTTPClient (3) ✓
- TestLANClientHealth (5) ✓
- TestLANClientUpload (4) ✓
- TestAudioRecorder (3) ✓
- TestScreenshotCapture (2) ✓
- TestGUIComponents (9) ✓
- TestAsyncRunner (3) ✓
- TestAppController (2) ✓
- TestLANClientHealthExtra (3) ✓

**Combined LAN tests (server + client): 87/87 通過 (9.44s)**

**Key Decisions:**
- GUI 與 PyAudio/mss 解耦：SOAPVoiceGUI 透過 `set_recording_callbacks()` 接受外部實作，便於無頭測試
- Async/Sync 雙模 callback：`update_connection_status` 為 async（測試以 run_until_complete），同步 wrapper `_sync_*` 用 `after(0,...)` 排程到 Tk 主執行緒
- `AsyncRunner` 在背景 thread 跑 asyncio loop，主執行緒專責 tkinter mainloop（避免阻塞 UI）
- `ConnectionIndicator` 直接畫 Canvas 圓燈，避免外部圖示資源
- 離線/降級時自動 disable 錄音按鈕（防誤操作）
- 啟動時 `load_pending_from_disk()` 恢復上次未上傳項目
- 版本不相容時 `messagebox.showwarning`，但仍進入 GUI 讓使用者重試

---

## Phase 11-01 Completion Summary (2026-04-27)

✅ **Phase 11-01: 伺服器端 LAN API — COMPLETE**

**Deliverables:**
- `src/api/lan_health_api.py` — `/api/v1/health` + `/api/v1/version` 端點（172 行）
- `src/api/lan_process_api.py` — `/api/v1/lan/process` multipart 端點（361 行）
- `src/utils/audio_compress.py` — Opus 32kbps 壓縮工具（187 行）
- `src/main.py` — `is_lan_ip()` + `lan_whitelist_middleware` + 路由註冊
- `tests/test_lan_api.py` — 49 個單元/整合測試（834 行）

**Commits:**
- cdca251 — feat(11-01): add LAN whitelist middleware and register LAN routers
- 2e37758 — feat(11-01): add Opus 32kbps audio compression utility
- d35d80e — test(11-01): add 49 unit/integration tests for LAN API

**Test Coverage:** 49/49 通過 (8.13s)
- TestAudioCompress (11) ✓
- TestLANWhitelist (8) ✓
- TestHealthEndpoint (5) ✓
- TestLANProcessEndpoint (10) ✓
- TestLANProcessIntegration (5) ✓
- TestLANProcessErrorPaths (5) ✓
- TestResponseModels (5) ✓

**Key Decisions:**
- `/api/v1/health` 採直接路徑（無 /lan 子路徑），便於客戶端版本檢查慣例
- `lan_health_router` 須早於 `websocket_router` 註冊以避免路由衝突
- FastAPI TestClient `testclient` 主機名加入 LAN 白名單（生產環境不可達）
- Opus 壓縮失敗 graceful fallback 至原 WAV bytes
- 任一下游（ASR/SOAP/SQLite）失敗皆回 200 + status='partial'

---

## Phase 10 Completion Summary

✅ **Phase 10: 資料持久化 — COMPLETE**

**Completed Plans:**
- 10-01: 資料庫基礎層 (aiosqlite + Schema 初始化)
- 10-02: SOAP 儲存整合 (雙軌寫入 + 自動儲存)
- 10-03: 搜尋 API + 審計追蹤 (REST 端點 + 分頁)

**Deliverables:**
- `src/db/patient_records_db.py` — 完整 aiosqlite 連線管理與 CRUD
- `src/db/patient_records_api.py` — 4 個 REST 端點
- SQLite 四張核心表 (patient_records, consultation_records, soap_audit_log, schema_version)
- 52/52 測試通過 (含 gap closure)

**Test Coverage:**
- Schema 初始化與 WAL 模式驗證 ✓
- CRUD 操作測試 ✓
- 搜尋 + 分頁測試 ✓
- 審計追蹤 immutability 驗證 ✓
- WebSocket 路徑覆蓋 ✓

---

## Phase 11 Planning Summary

🚧 **Phase 11: LAN 瘦客戶端 — PLANNED (Ready for execution)**

**Planned Plans:**

### 11-01: 伺服器端 LAN API (Wave 1)
**Goal:** 建立伺服器端 multipart 端點、Opus 壓縮、IP 白名單、健康檢查

**Deliverables:**
- `src/api/lan_health_api.py` — `/api/v1/health` 端點 + 版本檢查
- `src/api/lan_process_api.py` — `/api/v1/lan/process` multipart 端點
- IP 白名單 middleware (192.168.x.x / 10.x.x.x)
- Opus 壓縮 (32kbps, 10:1 壓縮比)
- ASR + SOAP 生成整合
- SQLite 自動儲存

**Tasks:**
1. LAN API 基礎層與 IP 白名單 middleware
2. Opus 壓縮與 multipart 檔案處理
3. ASR + SOAP 生成與 SQLite 整合

**Requirements:** THIN-01

---

### 11-02: Windows 瘦客戶端 GUI (Wave 2)
**Goal:** 建立完全隔離的 Windows 應用程式，包括錄音、截圖、LAN 上傳、連線狀態指示燈、SOAP 展示

**Deliverables:**
- `client/main.py` — 應用程式入口
- `client/gui.py` — GUI 元件 (錄音按鈕、連線指示燈、SOAP 分頁面板)
- `client/audio_recorder.py` — PyAudio 錄製邏輯
- `client/screenshot_capture.py` — PIL/mss 截圖邏輯
- `client/lan_client.py` — LAN 通訊核心邏輯
- `client/lan_config.py` — 客戶端設定
- `client/http_client.py` — httpx + tenacity 非同步 HTTP 客戶端

**Tasks:**
1. 客戶端核心模組與 LAN 配置
2. 音檔錄製與截圖擷取模組
3. GUI 與應用程式入口

**Requirements:** THIN-01, THIN-02, THIN-03

---

### 11-03: 本機暫存與恢復機制 (Wave 2)
**Goal:** 實現 LAN 斷線時自動暫存、連線恢復後自動重試的機制

**Deliverables:**
- `client/local_storage.py` — 本機暫存隊列管理與 JSON 持久化
- `client/retry_manager.py` — 指數退避重試策略
- 強化 `client/lan_client.py` — 整合暫存與重試機制

**Features:**
- 本機暫存目錄: `~/AppData/Local/SoapVoice/pending/`
- 隊列上限: 10 筆
- 指數退避: 2 → 4 → 8 秒，最多 3 次
- 應用重啟後自動恢復隊列
- 連線恢復時 (offline → healthy) 自動觸發重試

**Tasks:**
1. 本機暫存管理模組
2. 重試策略與指數退避管理
3. 整合至 LANClient + 自動重試

**Requirements:** THIN-03

---

## Performance Metrics

**Velocity:**
- Total plans completed: 3 (Phase 10: 3 plans, Phase 11: 3 plans planned)
- Phase 10 average duration: ~8 min per plan
- Phase 10 total execution: ~22 min (3 plans)

**By Phase:**

| Phase | Plans | Total | Avg/Plan | Status |
|-------|-------|-------|----------|--------|
| 10-persistence | 3 | 22m | ~7m | ✅ Complete |
| 11-lan-client | 3 | TBD | TBD | 🚧 Planned |

**Recent Trend:**
- v1.0 baseline: 9 phases completed, shipped 2026-04-24
- v1.1: Phase 10 completed (52/52 tests), Phase 11 planned (3 plans)

---

## Accumulated Context

### Decisions

Key decisions affecting Phase 11 work:

- **Phase 11**: 客戶端 `client/` 目錄與 `src/` 完全隔離，不 import 任何推理模組 ✓
- **Phase 11**: LLM 推理必須用獨立 process + asyncio.Semaphore(1) 解耦
- **Phase 11**: 語音壓縮使用 Opus (32kbps，壓縮比 10:1) ✓
- **Phase 11**: 本機暫存隊列支援上限 10 筆，超過時自動刪除最舊 ✓
- **Phase 11**: LAN IP 白名單 (192.168.x.x / 10.x.x.x) 在 middleware 層實施 ✓
- **Phase 12**: 儀表板用 SSE 非 WebSocket（單向推送，瀏覽器原生自動重連）
- **Phase 13**: Wine 驗證僅做語法/啟動測試，明確標註不可替代 Windows 實機驗證

### Known Blockers/Concerns

- **Phase 11**: LLM 推理 process 隔離模式需 spike 驗證（ProcessPoolExecutor vs multiprocessing.Queue）— *計畫於 Phase 11 執行時處理*
- **Phase 11**: PyInstaller 輕量打包（排除推理模組與 GGUF 模型）的 hook 設定需驗證 — *計畫於 Phase 13 執行*
- **Phase 12**: pynvml 可用性 — 若未來改用非 NVIDIA GPU，需 fallback 至 psutil

### Pending Todos

None yet. (Use `/gsd-add-todo` to capture ideas)

---

## Wave Structure

**Phase 11 Execution Waves:**

| Wave | Plans | Dependencies | Parallelizable |
|------|-------|--------------|-----------------|
| 1 | 11-01 (Server API) | None (depends on Phase 10) | — |
| 2 | 11-02, 11-03 | Both depend on 11-01 | Yes (different concerns: GUI vs storage) |

**Execution Order:**
1. Execute 11-01 (伺服器端 API) — prerequisite for client
2. Execute 11-02 and 11-03 in parallel (客戶端 GUI 與暫存機制)

---

## Session Continuity

Last session: 2026-04-27T12:00:00.000Z
Stopped at: Phase 11 planning complete (all 3 plans created)
Resume instruction: Run `/gsd-execute-phase 11` to begin Phase 11 implementation
