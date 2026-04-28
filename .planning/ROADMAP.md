# Roadmap: SoapVoice

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (語音轉 SOAP 核心管線 + GUI + 打包腳本，shipped 2026-04-24)
- 🚧 **v1.1 網路部署與資料管理** — Phases 10-14 (in progress)

## Overview

v1.1 將 SoapVoice 從單機一體式 GPU 工作站轉型為 **LAN 瘦客戶端架構**：一台 Linux GPU 伺服器服務多台 Windows 精簡客戶端。核心策略是將既有單體拆分為「客戶端（capture-only）+ 伺服器（processing + storage）」，透過 HTTP REST 通訊。技術棧僅新增 5 個輕量套件（httpx、tenacity、aiosqlite、sse-starlette、psutil）。

建置順序：資料持久層 → 客戶端分離 ∥ 監控儀表板 → Wine EXE 驗證 → 技術文件。

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) — SHIPPED 2026-04-24</summary>

### Phase 1-8: 核心管線
ASR 轉錄 → 術語標準化 → ICD-10 對應 → LLM SOAP 生成 → GUI 側邊欄 → OCR 患者資訊擷取

### Phase 9: Windows 打包
PyInstaller + Inno Setup 腳本建置

</details>

### 🚧 v1.1 網路部署與資料管理 (In Progress)

**Milestone Goal:** LAN 瘦客戶端架構 — Windows EXE 可透過區網上傳錄音/截圖至 GPU 伺服器、接收 SOAP、資料持久化、監控儀表板。

- [x] **Phase 10: 資料持久化** — SQLite 結構化儲存病歷/音檔/逐字稿、審計追蹤、病患搜尋與分頁瀏覽
- [ ] **Phase 11: LAN 瘦客戶端** — Windows 精簡 EXE 錄音+截圖上傳、接收並顯示 SOAP、LAN 斷線容錯
- [ ] **Phase 12: 監控儀表板** — SSE 即時 GPU 指標推送、處理時間趨勢圖、看診次數統計
- [ ] **Phase 13: Wine EXE 驗證** — Linux Wine 下 EXE 煙霧測試、GitHub Actions CI 自動化
- [ ] **Phase 14: 技術文件** — README.md 完整重寫反映 v1.1 LAN 架構

## Phase Details

### Phase 10: 資料持久化
**Goal**: 每次問診的完整資料（SOAP 病歷、音檔、逐字稿、metadata）被結構化儲存，醫師可搜尋並瀏覽歷史記錄
**Depends on**: 無（基礎層，所有下游功能依賴之）
**Requirements**: PERS-01, PERS-02
**Success Criteria** (what must be TRUE):
  1. 醫師完成一次問診後，SOAP 病歷、原始音檔、ASR 逐字稿及處理 metadata（時間戳、處理耗時）自動儲存至 SQLite，無需手動操作
  2. 醫師可依病患姓名關鍵字搜尋歷史記錄，結果支援分頁瀏覽（每頁 20 筆），依時間倒序排列
  3. 醫師可依問診日期範圍篩選記錄（起始日～結束日），並支援組合搜尋（姓名 + 日期範圍）
  4. 任何對 SOAP 記錄的修改均留有不可變審計追蹤（建立時間、作者、操作類型），原始記錄採 append-only 設計，不可被直接覆寫
   5. SQLite 使用 WAL 模式 + busy_timeout 5000ms，多醫師同時寫入時不出現記錄流失
**Plans**: 3 plans

Plans:
- [x] 10-01-PLAN.md — 資料庫 Schema 與連線基礎（aiosqlite 模組 + 四張表初始化 + lifespan 整合）
- [x] 10-02-PLAN.md — SOAP 儲存整合（SessionManager 雙軌寫入 + consultation_api 自動儲存）
- [x] 10-03-PLAN.md — 搜尋 API 與審計追蹤端點（姓名/日期搜尋 + 分頁 + SOAP 修改審計）

### Phase 11: LAN 瘦客戶端
**Goal**: 醫師可從 Windows 精簡客戶端錄音並截圖，透過 LAN HTTP 上傳至 GPU 伺服器，接收並在 GUI 中查看結構化 SOAP 病歷
**Depends on**: Phase 10（資料模型定義完成後方可儲存上傳的 SOAP）
**Requirements**: THIN-01, THIN-02, THIN-03
**Success Criteria** (what must be TRUE):
  1. 醫師在客戶端點擊錄音後，語音與螢幕截圖自動透過 HTTP multipart 上傳至 LAN GPU 伺服器，無需手動選擇檔案或指定路徑
  2. 伺服器處理完成後，客戶端 GUI 自動展開面板，結構化顯示臨床摘要、雙語 SOAP（中/英）、醫囑與用藥建議
  3. LAN 斷線時，客戶端 GUI 顯示紅色連線指示燈與明確錯誤訊息；連線恢復後自動指數退避重試（最多 3 次），每 3 秒更新連線狀態燈號（綠/黃/紅）
  4. 錄音過程中若未成功上傳至伺服器，音檔以時間戳命名（`YYYYMMDD_HHMMSS_sessionid.wav`）暫存於本地目錄，待連線恢復後自動補傳
  5. 客戶端啟動時自動呼叫 `GET /api/v1/health` 檢查伺服器 API 版本相容性，不相容時強制彈窗提示更新
**Plans**: 3 plans

Plans:
- [x] 11-01-PLAN.md — 伺服器端 LAN API（multipart 端點、Opus 壓縮、IP 白名單、健康檢查）
- [x] 11-02-PLAN.md — Windows 瘦客戶端 GUI（錄音+截圖、LAN 上傳、連線狀態指示燈、SOAP 展示面板）
- [x] 11-03-PLAN.md — 本機暫存與恢復機制（失敗上傳隊列、指數退避重試、應用重啟後自動恢復）

### Phase 12: 監控儀表板
**Goal**: 診所 IT 人員可透過瀏覽器即時監控 GPU 伺服器健康狀態，並查看歷史處理效能趨勢
**Depends on**: Phase 10（監控歷史數據依賴持久層儲存）
**Requirements**: DASH-01, DASH-02
**Success Criteria** (what must be TRUE):
  1. IT 人員在瀏覽器中開啟儀表板，可即時查看 GPU 使用率、VRAM 用量、請求佇列長度，指標透過 SSE 每 2 秒自動更新
  2. IT 人員可查看歷史處理時間趨勢圖，支援小時與日粒度切換（使用 Chart.js 前端渲染）
  3. IT 人員可查看患者看診次數統計摘要（如「本日 N 筆、本月 M 筆」），數據來自 Phase 10 持久層
**Plans**: 2 plans

Plans:
- [ ] 12-01-PLAN.md — 伺服器端指標收集與 SSE 推送（GPU/VRAM 輪詢、metrics_history 表、非同步任務）
- [ ] 12-02-PLAN.md — 儀表板前端與歷史圖表（HTML + Chart.js、SSE 連線、統計卡片）

### Phase 13: Wine EXE 驗證
**Goal**: 確保 Phase 11 建置的 Windows 精簡客戶端 EXE 可在 Linux Wine 環境下完成基本煙霧測試，CI 自動化執行
**Depends on**: Phase 11（需可建置的 `soapvoice-client.spec` 產出 EXE）
**Requirements**: PACK-01, PACK-02
**Success Criteria** (what must be TRUE):
  1. 開發者在 Linux 終端透過 `wine soapvoice-client.exe` 啟動客戶端，GUI 視窗正常顯示且無 crash
  2. 客戶端啟動後可成功呼叫伺服器 `GET /api/v1/health` 端點，並在 GUI 顯示綠燈連線狀態
  3. 開發者可正常關閉客戶端視窗（點擊關閉按鈕或視窗 X），無殘留 process 或記憶體洩漏
  4. GitHub Actions CI 在每次 push 時自動在 Wine Docker 容器中執行上述煙霧測試（啟動 → 健康檢查 → 正常關閉），並回報測試結果
**Plans**: TBD

### Phase 14: 技術文件
**Goal**: 開發者與部署人員可從專案文件完整理解 v1.1 LAN 瘦客戶端架構、部署流程與開發指南
**Depends on**: Phases 10-13（彙整所有 v1.1 功能的決策與實作細節）
**Requirements**: DOCS-01
**Success Criteria** (what must be TRUE):
  1. 新進開發者閱讀 README.md 後，可在 30 分鐘內理解 v1.1 LAN 瘦客戶端架構（含架構圖與關鍵設計決策）
  2. IT 部署人員依 README.md 步驟操作，可成功完成 GPU 伺服器部署與 Windows 客戶端安裝
  3. API 文件完整記錄所有 v1.1 端點（含請求/回應範例、必填/選填欄位、錯誤碼說明）
  4. 開發指南含本地開發環境設定（`uv sync`）、測試執行（`pytest`）、客戶端/伺服器建置流程說明
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11 ∥ 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 10. 資料持久化 | v1.1 | 3/3 | ✅ Complete | 2026-04-25 |
| 11. LAN 瘦客戶端 | v1.1 | 0/3 | Planning | — |
| 12. 監控儀表板 | v1.1 | 0/2 | Planning | — |
| 13. Wine EXE 驗證 | v1.1 | 0/TBD | Not started | — |
| 14. 技術文件 | v1.1 | 0/TBD | Not started | — |
