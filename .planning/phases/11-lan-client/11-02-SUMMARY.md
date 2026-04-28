---
phase: 11-lan-client
plan: "02"
subsystem: "Windows 瘦客戶端 GUI"
tags: [tkinter, lan-client, async, http, multipart, soap-display]
requires:
  - "11-01 伺服器端 LAN API（/api/v1/health, /api/v1/lan/process）"
provides:
  - "Windows 瘦客戶端可獨立啟動的 GUI 應用程式"
  - "錄音/截圖/上傳一鍵流程"
  - "連線指示燈（綠/黃/紅）+ 自動補傳"
  - "客戶端啟動健康檢查與版本相容性彈窗"
affects:
  - "client/ 套件新增 7 模組（lan_config / http_client / lan_client / audio_recorder / screenshot_capture / gui / main）"
tech-stack:
  added:
    - "tkinter（標準函式庫，主要 GUI 框架）"
    - "PyAudio（錄音 16kHz mono）"
    - "PIL.ImageGrab + mss（跨平台截圖）"
    - "httpx + tenacity（async HTTP + 指數退避重試）"
  patterns:
    - "Threading: tkinter mainloop 在主執行緒，asyncio loop 在背景 thread"
    - "Status callback 同步包裝（after(0,...) 跨 thread 安全）"
    - "Pending upload queue：失敗暫存 JSON → 連線恢復自動補傳"
    - "Semver 比較容錯（rc/beta tag）"
key-files:
  created:
    - "client/__init__.py"
    - "client/lan_config.py"
    - "client/http_client.py"
    - "client/lan_client.py"
    - "client/audio_recorder.py"
    - "client/screenshot_capture.py"
    - "client/gui.py"
    - "client/main.py"
    - "tests/test_client.py"
  modified: []
decisions:
  - "GUI 與 PyAudio/mss 解耦：SOAPVoiceGUI 不直接 import recorder，由 main.py App 透過 set_recording_callbacks() 綁定"
  - "Async callback 採 async def + run_until_complete 介面，便於測試以 asyncio loop 驗證"
  - "ConnectionIndicator 使用 Canvas 直接畫圓，避免外部圖示資源依賴"
  - "離線/降級時自動 disable 錄音按鈕，避免使用者誤操作"
  - "啟動時 load_pending_from_disk()：上次未上傳的問診恢復載入"
  - "AudioRecorder 單聲道 16kHz：Whisper 最佳採樣率，伺服器端再壓 Opus 32kbps"
  - "ScreenshotCapture 雙後端：PIL.ImageGrab 優先（Windows/macOS 快），mss 備選（Linux）"
metrics:
  duration: "1 個對話 session（執行 Task 3：GUI + main.py + 14 測試）"
  completed: "2026-04-27"
  tasks_completed: "3 of 3"
  files_created: 9
  files_modified: 0
  total_loc: 2799
  test_count: 38
  test_pass_rate: "100%"
---

# Phase 11 Plan 02: Windows 瘦客戶端 GUI Summary

完整實作 Windows 瘦客戶端，提供獨立 GUI 應用程式（錄音/截圖/連線指示燈/SOAP 面板），透過 LAN HTTP multipart 上傳到 11-01 伺服器端 API；支援連線斷線自動暫存與恢復後補傳。

## 實作概覽

Phase 11-02 拆三個 task 完成；Tasks 1-2（核心 LAN client + I/O 模組）於 commit `c650402` 已完成，本次 session 補完 Task 3（GUI + 應用程式入口）並擴充測試覆蓋率：

### Task 1：客戶端核心（已於 c650402 完成）
- `client/lan_config.py` (92 行) — `LANConfig` dataclass，含 SOAPVOICE_SERVER_URL 環境變數覆蓋、跨平台快取目錄
- `client/http_client.py` (190 行) — `AsyncHTTPClient` 包裝 httpx + tenacity 指數退避重試，統一以 `HTTPClientError` 包裝例外
- `client/lan_client.py` (381 行) — 健康狀態機（unknown/healthy/degraded/offline）、版本檢查、async 上傳、本機 JSON 暫存佇列、補傳邏輯、async/sync 雙模式 callback

### Task 2：I/O 模組（已於 c650402 完成）
- `client/audio_recorder.py` (194 行) — PyAudio 錄音 16kHz mono；背景 daemon thread；on_start/on_stop/on_error callback；檔名 `audio_YYYYMMDD_HHMMSS_<hex>.wav`
- `client/screenshot_capture.py` (100 行) — PIL.ImageGrab 優先 + mss fallback；JPEG quality=85 optimize；檔名 `screenshot_YYYYMMDD_HHMMSS_<hex>.jpg`

### Task 3：GUI 與應用程式入口（本 session 新增）
- `client/gui.py` (420 行) — Tkinter
  - `ConnectionIndicator(tk.Canvas)` — 30×30 圓燈，綠/黃/紅/灰 對應 healthy/degraded/offline/unknown
  - `SOAPPanel(tk.Frame)` — `ttk.Notebook` 5 分頁（S/O/A/P + 摘要），自動切回 S 分頁
  - `SOAPVoiceGUI(tk.Tk)` — 主視窗：頂部列（指示燈、連線文字、錄音按鈕、截圖按鈕、病患/醫師輸入欄）+ SOAPPanel + 狀態列
  - async API：`update_connection_status(status)` / `display_soap_result(result)`（給測試 run_until_complete）
  - 同步包裝：`_sync_status_callback` / `_sync_result_callback`（內部以 `after(0, ...)` 排程到 Tk 主執行緒，避免跨 thread 操作 widget）
  - 視窗關閉鉤子：自動呼叫 `lan_client.stop()` 終止 health monitor

- `client/main.py` (410 行) — 應用程式入口
  - `AsyncRunner` — 背景 thread 內運行 asyncio 事件迴圈；`submit(coro)` 從 GUI 主執行緒提交協程；`stop()` 取消所有任務並 join
  - `App` 控制器 — 把 GUI / LANClient / AudioRecorder / ScreenshotCapture 黏合起來
  - `perform_health_check()` — 啟動時同步檢查；版本不相容彈窗 `messagebox.showwarning`
  - `_on_record_toggle()` — 開始錄音時自動截圖；停止錄音時 `async_runner.submit(upload_consultation())`
  - 錄音/截圖透過 `gui.set_recording_callbacks()` 綁定，避免 GUI 層直接依賴 PyAudio
  - `_configure_logging()` — 同時寫 `~/AppData/Local/SoapVoice/logs/soapvoice_client.log` 與 stderr
  - CLI: `--server-url`, `--cache-dir`, `-v` (verbose)

## Test Coverage

`tests/test_client.py` (997 行)：**38/38 通過**（執行時間 0.43s）

| 測試類別 | 測試數 | 重點 |
|---------|-------|------|
| TestLANConfig | 4 | 預設值、env 覆蓋、endpoint 屬性、required_services 隔離 |
| TestAsyncHTTPClient | 3 | GET 成功 / GET 重試耗盡丟錯 / POST multipart |
| TestLANClientHealth | 5 | healthy / degraded(低版本) / degraded(服務未 ready) / offline / status_callback |
| TestLANClientUpload | 4 | 上傳成功 / 上傳失敗自動佇列 / 缺檔回 None / 從磁碟載入 pending |
| TestAudioRecorder | 3 | start/stop 產生 WAV / 重複 start no-op / 無 start 直接 stop |
| TestScreenshotCapture | 2 | ImageGrab 路徑 / mss fallback |
| **TestGUIComponents** | **9** | indicator 顏色 / SOAP 寫入 / 主視窗 wiring / 連線狀態切換 disabled / display_soap 回應 / 按鈕 callback / patient_doctor / 缺欄位空值 / 非 dict 容錯 |
| **TestAsyncRunner** | **3** | start/stop / 未 start 直接 submit 丟 RuntimeError / 重複 start 安全 |
| **TestAppController** | **2** | App 初始化 wiring / 錄音切換觸發 upload_consultation |
| **TestLANClientHealthExtra** | **3** | 連線恢復觸發 retry / 佇列上限 drop 最舊 / semver rc/beta 容錯 |

**整體加上 11-01 LAN API：87/87 通過（9.44s）**

## Done Criteria 驗證

| 必要成品 | 狀態 |
|---------|------|
| Windows 客戶端可獨立啟動，GUI 顯示錄音/截圖按鈕、連線指示燈 | ✅ `client/main.py` + `client/gui.py` |
| 點擊錄音 → 語音+截圖透過 multipart 上傳至 /api/v1/lan/process | ✅ `App._on_record_toggle()` 串接 `lan_client.upload_consultation()` |
| 連線指示燈每 3 秒更新，斷線時紅色 + 錯誤訊息，恢復時綠色 | ✅ `lan_client.start_health_monitor` 每 `health_check_interval_sec=3` 秒；`_apply_status` 切換顏色與狀態列 |
| 伺服器傳回 SOAP 後 GUI 自動展開面板顯示結構化 SOAP | ✅ `lan_client.result_callback` → `_apply_soap_result` → `SOAPPanel.display_soap` |
| 客戶端啟動時檢查 /api/v1/health 版本，不相容時彈窗 | ✅ `App.perform_health_check()` → `gui.show_version_mismatch()` |
| ≥12 個測試通過 | ✅ 38 測試通過（plan 設定 12+，實際達 35+ 目標） |

## 關鍵架構決策

### 1. Threading 模型
```
主執行緒          : tkinter mainloop（GUI 事件迴圈）
async-runner thread: asyncio 事件迴圈（健康監控、HTTP 請求）
recording thread  : PyAudio 採樣（daemon thread）
```
跨執行緒安全規則：所有 widget 寫入必須以 `gui.after(0, ...)` 排程到主執行緒。

### 2. GUI 解耦
`SOAPVoiceGUI` 不 import `pyaudio` 或 `mss`，僅透過 `set_recording_callbacks(on_record, on_screenshot)` 接受外部實作。這允許：
- 無頭測試（不需 PyAudio）
- 未來換成 webrtc/ffmpeg 錄音後端時 GUI 模組不變

### 3. Async/Sync 雙模 Callback
LANClient 的 callback 同時支援 `def` 和 `async def`（透過 `inspect.isawaitable` 偵測）。GUI 層暴露 async 方法以滿足測試 `run_until_complete`，同時提供 `_sync_*` wrapper 給 LANClient 直接呼叫。

### 4. 暫存佇列恢復
`load_pending_from_disk()` 在 App 初始化時掃描 `~/AppData/Local/SoapVoice/cache/pending_*.json` 並重建記憶體佇列；下次健康檢查 healthy 時觸發 `retry_pending_uploads()`。

## Deviations from Plan

無 — Tasks 1-2 在前一 commit 已完成；Task 3 完整實作 GUI + main.py，且測試從 plan 目標 12 個擴充到 38 個（含原已存在的 21 個 + 本次新增 14 個 GUI/AsyncRunner/App/edge-case + 既有 3 個 GUI skeleton 經填補後通過）。

唯一 minor adjustment：plan 範例 `_queue_for_retry` 寫成 async，實際實作為 sync（因為內部僅做檔案 IO 與 list 操作，無需 async）；對應的 `test_lan_client_pending_queue_cap` 改為 sync 呼叫。

## Threat Flags

無新增威脅面（皆與 plan 的 `<threat_model>` 一致）：

| Threat ID | Mitigation 達成 |
|-----------|----------------|
| T-11-07 (Spoofing) | API Key 槽位於 `LANConfig`（待 phase 12+ 啟用），目前依賴 LAN IP 白名單 |
| T-11-08 (Tampering) | 暫存目錄 `%LOCALAPPDATA%/SoapVoice/cache`（僅當前使用者可讀） |
| T-11-09 (Repudiation) | 所有上傳事件透過 `_configure_logging` 寫入 `soapvoice_client.log` 含時間戳 |
| T-11-11 (DoS) | `tenacity wait_exponential(min=2, max=10)` + `max_retries=3` 避免 bombarding |

## Commits

| Commit | Type | Files |
|--------|------|-------|
| c650402 | feat(11-02) | client/lan_config.py, client/http_client.py, client/lan_client.py, client/audio_recorder.py, client/screenshot_capture.py, tests/test_client.py（21 測試） |
| 3b917b1 | feat(11-02) | client/gui.py（420 行 — ConnectionIndicator + SOAPPanel + SOAPVoiceGUI） |
| a8fda61 | feat(11-02) | client/main.py（410 行 — App + AsyncRunner + CLI），tests/test_client.py 擴充至 38 測試 |

## Self-Check: PASSED

- [x] `client/__init__.py` exists
- [x] `client/lan_config.py` exists（92 lines, ≥50 plan min）
- [x] `client/http_client.py` exists（190 lines, ≥150 plan min）
- [x] `client/lan_client.py` exists（381 lines, ≥250 plan min）
- [x] `client/audio_recorder.py` exists（194 lines, ≥150 plan min）
- [x] `client/screenshot_capture.py` exists（100 lines, ≥80 plan min）
- [x] `client/gui.py` exists（420 lines, ≥300 plan min）
- [x] `client/main.py` exists（410 lines, ≥100 plan min）
- [x] `tests/test_client.py` exists（997 lines, 38 tests）
- [x] commit c650402 in `git log`
- [x] commit 3b917b1 in `git log`
- [x] commit a8fda61 in `git log`
- [x] 38/38 client tests pass
- [x] 87/87 combined LAN（49 server + 38 client）tests pass
