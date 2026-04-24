# Feature Research: SoapVoice v1.1 網路部署與資料管理

**Domain:** 醫療語音轉 SOAP 病歷系統 — LAN 瘦客戶端擴展
**Researched:** 2026-04-24
**Confidence:** HIGH

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Thin Client: 錄音上傳** | 醫師在診間錄音後須能將音檔傳至 GPU 伺服器 | MEDIUM | 現有 GUI 已支援錄音，需改造為 HTTP multipart upload。使用 FastAPI `UploadFile` 串流傳輸，大檔不分塊進記憶體 |
| **Thin Client: 截圖上傳** | OCR 患者資訊自動萃取需要 HIS 畫面截圖 | LOW | 現有 `mss` + Tesseract 已實作，僅需改變處理位置（從本機→伺服器） |
| **Thin Client: SOAP 結果顯示** | 上傳後須接收並顯示 SOAP 病歷 | LOW | 現有 GUI 展開面板已含 SOAP 顯示區 (`text_soap`)，API 回應格式已定 |
| **Patient Record Persistence** | 每次問診的病歷、音檔、逐字稿須持久儲存 | HIGH | 需新建 `patient_records` 資料表。現有 `SessionManager` 僅存 JSON，非結構化查詢。須改為 SQLite 結構化儲存 |
| **Patient Search by Name/Date** | 醫師須能回溯查詢病患歷史記錄 | MEDIUM | 依賴 Persistence 完成。SQLite LIKE + indexed columns。需建立 `patient_name`, `record_date` 索引 |
| **Session Auto-Save** | 伺服器斷線時不遺失已錄音檔 | MEDIUM | 需在 thin client 端本地暫存（錄音時同步寫入本地暫存目錄），上傳成功後清除 |
| **Network Error Handling** | LAN 斷線須有清楚提示，不可靜默失敗 | LOW | HTTP 超時設定 + retry logic（3 次指數退避）。現有 `status_label` 可顯示錯誤訊息 |
| **API Key Authentication** | LAN 內須驗證客戶端身分 | LOW | 現有 `X-API-Key` header 驗證已實作於 `src/security/auth.py`。Thin client 從 `.env` 或設定檔讀取 |
| **Wine EXE Smoke Test** | 確保 Windows 打包檔在 Wine 下可啟動 | LOW | 現有 `wine_package.sh` 僅做 dry-run。需擴充為完整 smoketest：啟動 → 健康檢查 → 關閉 |
| **README Rewrite** | v1.1 新增架構後，文件須反映實際系統 | LOW | 現有 README.md 過時（仍描述 v0.8 CLI，無 thin client 架構） |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Real-time GPU Monitoring Dashboard** | 診所 IT 人員可監控 GPU 使用率、處理佇列長度、平均延遲 | HIGH | 使用 `pynvml` 擷取 GPU 指標 + FastAPI WebSocket/SSE 推送 + Chart.js 前端繪圖。現有 Zero，完全新建 |
| **Processing Time Analytics** | 歷史趨勢圖可協助診所評估硬體升級需求 | MEDIUM | 基於 Persistence 層的 `processing_time_ms` 欄位聚合。SQLite `strftime` + GROUP BY 即可 |
| **Thin Client Local Fallback** | GPU 伺服器不可用時，自動降級為本機 CPU 推理 | HIGH | 需 thin client 內嵌 llama.cpp 引擎（`llama_cpp` + gguf 模型約 2GB）。複雜度高，可能延後至 v1.2 |
| **Bulk Patient Export (CSV/DOCX)** | 供健保申報或研究分析使用 | MEDIUM | 利用現有 `python-docx` 依賴。從 SQLite 查詢 → 格式化匯出 |
| **Audio Waveform Preview** | 錄音後可快速拖曳檢視波形，確認錄音品質 | LOW | 使用 HTML5 Canvas 或 Python matplotlib（現有依賴排除，需重新加入）繪製波形圖 |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Docker 容器化部署** | 標準化部署，跨環境一致性 | v1.1 目標是 LAN 直接部署，Docker 增加 GPU pass-through 複雜度（nvidia-docker 設定、磁碟映射）。超出 scope | 列為 v1.2 backlog。目前 FastAPI 直接 `uv run uvicorn` 即可 |
| **多機構/多租戶架構** | 多家診所共用一台伺服器 | 資料隔離、權限管理、租戶路由大幅增加複雜度。v1.1 僅單一診所使用 | 在 Persistence 層預留 `clinic_id` 欄位以便未來擴充 |
| **即時語音串流 (WebSocket) 至 thin client** | 邊錄音邊看逐字稿 | WebSocket 連線管理複雜、LAN 環境可能不穩定、thin client 端 buffer 管理難 | 錄音完成後整批上傳（HTTP POST），簡化錯誤處理。現有 WebSocket 端點保留供本機使用 |
| **行動 App (iOS/Android)** | 醫師用手機錄音 | 不同 UI 框架、安全性模型、憑證管理。超出 v1.1 scope | 桌面端優先。未來 thin client API 設計為 RESTful，手機端可重用 |
| **EHR/EMR 直接整合** | 自動從 HIS 系統拉患者資料 | 每家醫院 HIS 不同（自訂格式、無標準 API），整合成本極高 | 現有 OCR 方案（截圖→文字萃取）是務實的通用解法 |
| **Real-time speech-to-text streaming display** | 醫師說話時即時顯示文字 | 增加 GUI 複雜度與 WebSocket 連線管理，非核心價值 | 錄音完成後一次性轉錄，簡化 UX 與錯誤處理 |

---

## Feature Dependencies

```
Patient Record Persistence (SQLite)
    └──requires──> Database Schema Design
    └──enables──> Patient Search (by name/date/symptoms)
    └──enables──> Processing Time Analytics (dashboard)

LAN Thin Client
    └──requires──> File Upload API (audio + screenshot)
    ├──requires──> API Key Authentication (existing)
    ├──requires──> Network Error Handling
    └──enhances──> Session Auto-Save (local cache)

GPU Monitoring Dashboard
    └──requires──> pynvml integration on server
    └──requires──> WebSocket/SSE endpoint
    └──requires──> Frontend chart rendering

Wine EXE Validation
    └──requires──> PyInstaller build (existing phase 9)
    └──requires──> Wine environment setup
    └──independent──> (no dependency on other v1.1 features)

README Rewrite
    └──requires──> All other features documented
    └──conflicts──> None (documentation task)
```

### Dependency Notes

- **Patient Record Persistence 是核心依賴**: 病人搜尋、監控分析都依賴結構化資料儲存。必須在第一階段完成 Schema 設計與實作。
- **File Upload API 是 thin client 的傳輸層**: 現有 REST API 不支援 multipart audio upload。需新增端點。
- **Dashboard 與 Persistence 獨立**: 監控圖表僅需 server 端 metrics（GPU 使用率、請求計數），不依賴 patient records。
- **Wine EXE Validation 與其他完全獨立**: 不需要 server API 即可進行驗證。
- **README Rewrite 應最後進行**: 需彙整所有 v1.1 功能內容後重寫。

---

## MVP Definition

### Launch With (v1.1 — Must Have)

- [ ] **Thin Client: File Upload (audio + screenshot → server)** — 讓 Windows EXE 能透過 LAN 將錄音與截圖傳到 GPU 伺服器
- [ ] **Thin Client: SOAP Display (server response → GUI)** — 將伺服器回應的 SOAP 病歷顯示在 GUI 展開面板
- [ ] **Patient Record Persistence (SQLite)** — 每次問診的 SOAP、音檔路徑、逐字稿、metadata 儲存至 SQLite
- [ ] **Patient Search by Name/Date** — 基本姓名與日期查詢，含分頁
- [ ] **Network Error Handling & Auto-Save** — LAN 斷線提示 + 本地暫存錄音
- [ ] **Wine EXE Smoke Test** — 啟動 → 健康檢查 → 正常關閉
- [ ] **README Complete Rewrite** — 反映 v1.1 thin client 架構

### Add After Validation (v1.1.x — Should Have)

- [ ] **GPU Monitoring Dashboard (pynvml + Chart.js)** — 處理後可驗證 GPU 使用趨勢
- [ ] **Symptom-based Patient Search** — 基於 SOAP assessment 關鍵字搜尋（需 FTS 索引）
- [ ] **Local Fallback CPU Processing** — GPU 伺服器不可用時的降級方案
- [ ] **Wine Docker CI/CD Validation** — 使用 Docker 容器自動化 Wine 測試
- [ ] **Bulk Export (CSV/DOCX)** — 資料匯出功能

### Future Consideration (v2+)

- [ ] Docker 容器化部署 — 當需要跨多台伺服器部署時
- [ ] 多機構/多租戶 — 當有多家診所共用時
- [ ] EHR/EMR 直接整合 — 與特定 HIS 廠商對接
- [ ] 行動 App — 當醫師需要手機端使用時

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| File Upload API (audio+screenshot) | HIGH | MEDIUM | P1 |
| SOAP Result Display | HIGH | LOW | P1 |
| Patient Record Persistence (SQLite) | HIGH | HIGH | P1 |
| Patient Search (name/date) | HIGH | MEDIUM | P1 |
| Network Error Handling | HIGH | LOW | P1 |
| Wine EXE Smoke Test | MEDIUM | LOW | P1 |
| README Rewrite | MEDIUM | LOW | P1 |
| GPU Monitoring Dashboard | MEDIUM | HIGH | P2 |
| Session Auto-Save (local cache) | MEDIUM | MEDIUM | P2 |
| Symptom-based Search | MEDIUM | MEDIUM | P2 |
| Local CPU Fallback | HIGH | HIGH | P2 |
| Wine Docker CI/CD | LOW | MEDIUM | P3 |
| Bulk Export | LOW | MEDIUM | P3 |
| Audio Waveform Preview | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v1.1 launch
- P2: Should have, add in v1.1.x follow-ups
- P3: Nice to have, future consideration

---

## Detailed Feature Analysis

### 1. LAN Thin Client (P1)

**Workflow:**
```
Windows EXE (Client)                  GPU Server (0.0.0.0:8010)
    |                                       |
    |-- POST /api/v1/thin/upload --------->|
    |   multipart: audio.wav + screen.png   |
    |                                       |-- ASR (Faster-Whisper) 
    |                                       |-- OCR (Tesseract)
    |                                       |-- NLP Normalize + ICD-10
    |                                       |-- LLM SOAP (Gemma 4:E4B)
    |<-- JSON: SOAP + metadata ------------|
    |                                       |
    GUI 展開面板顯示 SOAP 結果               |
```

**API 設計（新建）:**
- `POST /api/v1/thin/upload` — multipart/form-data（`audio_file` + `screenshot_file`）
- 回應格式沿用現有 `SOAPGenerateResponse` schema
- 認證：`X-API-Key` header（現有 middleweare）

**邊界案例:**
- 音檔過大（>100MB）：伺服器端拒絕並回傳 413，client 端提示「錄音過長，請分段錄製」
- 截圖無文字（空白 HIS 畫面）：OCR 回傳空，SOAP 生成仍可進行（僅基於語音）
- 伺服器忙碌中（LLM 推理中）：回傳 503 + Retry-After header，client 排隊重試
- LAN 斷線：client 端偵測連線失敗，顯示「無法連接伺服器」，錄音保存至本地
- 並發請求：多台 thin client 同時上傳 → 伺服器端用 asyncio 佇列（每個 LLM 推理為 CPU blocking，須用 `run_in_executor` 以免阻塞 event loop）

**現有程式碼改動範圍:**
- `src/gui/desktop_app.py`: `process_recording()` 改為 HTTP POST 而非本機呼叫
- `src/api/rest.py` (或新建 `src/api/thin_client.py`): 新增 multipart upload endpoint
- `static/` (optional): 若保留 Web 控制台，可新增 thin client 模式的 HTML 介面

### 2. Patient Record Persistence (P1)

**Schema 設計（新建 SQLite 表）:**
```sql
CREATE TABLE patient_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,          -- 患者姓名
    patient_id TEXT,                     -- 身分證號
    birth_date TEXT,                     -- 出生日期 YYYY-MM-DD
    mrn TEXT,                            -- 病歷號碼
    record_date TEXT NOT NULL DEFAULT (datetime('now')),
    chief_complaint TEXT,                -- 主訴（從 OCR/語音萃取）
    transcript TEXT,                     -- ASR 逐字稿全文
    soap_subjective TEXT,                -- S: 主觀資料
    soap_objective TEXT,                 -- O: 客觀檢查
    soap_assessment TEXT,                -- A: 評估診斷
    soap_plan TEXT,                      -- P: 治療計畫
    icd10_codes TEXT,                    -- ICD-10 代碼 (JSON array)
    medications TEXT,                    -- 建議藥物 (JSON array)
    audio_path TEXT,                     -- 音檔儲存路徑
    screenshot_path TEXT,                -- 截圖儲存路徑
    doctor_name TEXT,                    -- 問診醫師
    clinic_name TEXT,                    -- 診所名稱
    processing_time_ms REAL,             -- 處理耗時
    model_version TEXT,                  -- LLM 模型版本
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_patient_name ON patient_records(patient_name);
CREATE INDEX idx_record_date ON patient_records(record_date);
CREATE INDEX idx_chief_complaint ON patient_records(chief_complaint);
```

**實作建議:**
- 使用現有 `sqlite3`（stdlib，無需新增依賴），避免非同步複雜度（LAN 環境單一伺服器，SQLite 寫入鎖定不是瓶頸）
- 與現有 `src/db/clinical_db.py` 模式一致（連線→查詢→關閉），但不共用同一個 `medical.db`
- 新建 `src/db/patient_records_db.py`，使用專屬資料庫 `data/patient_records.db`
- 現有 `SessionManager._save_session()` 的 JSON 檔案儲存保留給諮詢會話暫存，patient records 用 SQLite

**音檔與截圖儲存策略:**
- 儲存路徑：`data/recordings/{YYYY-MM-DD}/{session_id}_audio.wav`
- 截圖路徑：`data/screenshots/{YYYY-MM-DD}/{session_id}_screen.png`
- 定期清理：cron job 刪除 >180 天舊檔（保留資料庫記錄，僅刪除檔案）

### 3. Patient Search (P1)

**API 端點（新建）:**
```
GET /api/v1/patients/search?name=張三&date_from=2026-01-01&date_to=2026-06-30&symptom=咳嗽&page=1&limit=20
```

**實作方式:**
- SQLite `WHERE patient_name LIKE ? AND record_date BETWEEN ? AND ?`
- 症狀搜尋：`WHERE chief_complaint LIKE ?`
- 分頁：`LIMIT ? OFFSET ?`
- 回傳格式：
```json
{
  "total": 45,
  "page": 1,
  "limit": 20,
  "results": [
    {
      "id": 1,
      "patient_name": "張三",
      "record_date": "2026-04-24 14:30:00",
      "chief_complaint": "咳嗽",
      "icd10_codes": ["J06.9"],
      "doctor_name": "李醫師"
    }
  ]
}
```

### 4. GPU Monitoring Dashboard (P2)

**資料收集（伺服器端）:**
- `pynvml`：GPU 使用率、VRAM 用量、溫度、功耗
- `psutil`（或自訂 middleware）：請求計數、平均處理時間、佇列長度
- 定時器（asyncio background task）：每 2 秒收集一次

**API 端點（新建）:**
```
GET /api/v1/monitor/gpu         → GPU 即時指標 (JSON)
GET /api/v1/monitor/requests    → 請求統計 (JSON)
WS  /api/v1/monitor/stream      → WebSocket 即時推送
```

**前端（獨立 HTML 頁面）:**
- `static/dashboard.html` — 三面板 layout：
  1. GPU 儀表（使用率 %、VRAM bar、溫度 gauge）
  2. 請求趨勢圖（過去 1 小時的 requests/minute）
  3. 處理時間分布（histogram: SOAP 生成耗時）
- 使用 Chart.js（CDN，無需 node 建置）

**替代方案（若 P1 時間不足）:**
- 直接使用 `nvitop` CLI 工具（已安裝於伺服器），不建 Web 儀表板
- 或使用 Grafana + Prometheus + DCGM Exporter（適合未來多伺服器場景）

### 5. Wine EXE Validation (P1)

**驗證層級:**

| 層級 | 測試項目 | 環境 | 通過標準 |
|------|---------|------|---------|
| L1: Smoke | EXE 啟動 → GUI 視窗出現 → 按鈕可點擊 | Wine 9.x on Linux | 無 crash |
| L2: Functional | 錄音 5 秒 → 上傳 → 接收 SOAP（需 mock server） | Wine 9.x on Linux | 完整流程 |
| L3: Native | 同上，但在真實 Windows 10/11 | Windows VM/實機 | 完整流程 |

**實作腳本（擴充現有 `scripts/wine_package.sh`）:**
```bash
#!/bin/bash
# wine_validate.sh — L1 Smoke Test
set -e

WINE_EXE="dist/SoapVoice.exe"
WINE_TIMEOUT=30  # seconds

echo "[L1] 啟動 SoapVoice.exe..."
timeout $WINE_TIMEOUT wine "$WINE_EXE" &
PID=$!
sleep 10  # 等待 GUI 初始化

# 檢查程序是否存活
if kill -0 $PID 2>/dev/null; then
    echo "[L1] PASS: EXE 成功啟動，程序運行中"
else
    echo "[L1] FAIL: EXE 無法啟動或在 10 秒內 crash"
    exit 1
fi

# 檢查 GUI 視窗
if xdotool search --name "SoapVoice" 2>/dev/null; then
    echo "[L1] PASS: GUI 視窗已顯示"
else
    echo "[L1] WARN: 無法偵測 GUI 視窗（可能無 xdotool）"
fi

kill $PID 2>/dev/null
echo "[L1] 驗證完成"
```

**已知限制（來自研究）:**
- Wine 測試通過 ≠ Windows 真實環境通過（HIGH 信心，多個 source 確認）
- llama.cpp CUDA 在 Wine 下不可用（Wine 不支援 CUDA driver）。測試時需用 CPU-only 模式
- 音訊裝置（pyaudio）在 Wine 下可能無效 → L2 測試用 mock audio

### 6. Technical Documentation (P1)

**README.md 結構建議（基於醫療軟體最佳實踐研究）:**

```markdown
# SoapVoice — 醫療語音轉 SOAP 病歷系統

## 產品概述
- 一句話說明 + 系統架構圖（LAN Thin Client → GPU Server）
- 適用場景（診間問診記錄）

## 快速開始
### 環境需求（Python 3.11+, CUDA, RTX 3060 12GB+）
### 伺服器端部署（3 步驟）
### 客戶端部署（Windows EXE 安裝）

## 系統架構
### 網路拓撲圖（Client LAN → Server LAN）
### 數據流程圖（Audio → ASR → NLP → LLM → SOAP）
### API 文件（端點列表，重點標註 thin client 專用端點）

## 功能說明
- 語音轉 SOAP（完整 pipeline）
- 患者資訊自動萃取（OCR）
- 病患記錄管理（搜尋、歷史瀏覽、匯出）
- 監控儀表板（GPU、請求統計）

## 部署指南
- Windows Thin Client 安裝（Inno Setup 一鍵安裝）
- GPU 伺服器設定（CUDA、llama.cpp、環境變數）
- LAN 網路設定（防火牆規則、固定 IP）

## 安全與合規
- API Key 認證機制
- 資料儲存策略（本地 SQLite，定期備份至 NAS + GCS）
- 病患資料隱私（全離線，無雲端傳輸）

## 開發指南（內部文件）
## 疑難排解（常見問題 FAQ）
```

---

## Competitor Feature Analysis

| Feature | 醫呼通 (Hypothetical) | DeepScribe | Suki AI | SoapVoice |
|---------|----------------------|------------|---------|-----------|
| 全離線運作 | ✗ (需要雲端) | ✗ | ✗ | ✓ Core differentiator |
| 繁體中文 ASR | ✓ | ✗ | ✗ | ✓ Faster-Whisper |
| GPU 加速推理 | ✓ | ✓ | ✓ | ✓ RTX 3060 |
| LAN Thin Client | ✗ | ✗ | ✗ | ✓ v1.1 新增 |
| 即時監控儀表板 | ✗ | ✓ (admin panel) | ✗ | ✓ P2 自建 |
| 病患記錄搜尋 | ✓ | ✓ | ✓ | ✓ P1 SQLite |
| OCR 患者資訊萃取 | ✗ | ✗ | ✗ | ✓ Tesseract |
| Windows EXE 打包 | ✗ | ✗ (web only) | ✗ (web only) | ✓ PyInstaller + Inno |
| Wine 跨平台驗證 | ✗ | ✗ | ✗ | ✓ P1 |
| 開放原始碼 | ✗ | ✗ | ✗ | ✓ MIT License |

**競爭優勢總結:**
- SoapVoice 是唯一同時具備「全離線、LAN 部署、繁體中文、OCR 萃取、GPU 加速」的醫療語音 SOAP 系統
- v1.1 加入 LAN thin client 與監控後，可服務更大規模診所（多診間共用一台 GPU 伺服器）

---

## Sources

- **Google Search "Python FastAPI thin client architecture LAN medical application patterns 2025"** — 現代 thin client 架構、FastAPI async-first 設計模式、安全與合規建議（HIGH 信心）
- **Google Search "Python PyInstaller Wine validation testing Linux Windows EXE compatibility 2025"** — Wine 測試不等同 Windows 驗證，需實機測試（HIGH 信心）
- **Google Search "SQLite patient records search Python FastAPI persistence pattern 2025 2026"** — SQLAlchemy async 模式、FastAPI DI、搜尋與分頁最佳實踐（HIGH 信心）
- **Google Search "FastAPI dashboard monitoring GPU usage real-time charts Python 2025"** — pynvml + WebSocket/SSE + Chart.js 架構，或 Prometheus + Grafana 替代方案（HIGH 信心）
- **Google Search "FastAPI file upload audio screenshot multipart Python best practices 2025"** — UploadFile 串流傳輸、安全性驗證（HIGH 信心）
- **Google Search "medical software documentation README best practices 2025 2026 structure"** — 醫療軟體文件結構標準、IEC 62304 合規指引（MEDIUM 信心）
- **專案程式碼分析** — `src/gui/desktop_app.py`, `src/api/rest.py`, `src/api/consultation_api.py`, `src/consultation/session_manager.py`, `src/db/clinical_db.py`, `scripts/wine_package.sh`, `scripts/build_windows.sh`, `soapvoice.spec`, `.env.example`（HIGH 信心）

---

*Feature research for: SoapVoice v1.1 網路部署與資料管理*
*Researched: 2026-04-24*
