# 領域陷阱研究 — SoapVoice v1.1 網路部署與資料管理

**領域:** 醫療語音轉 SOAP 病歷系統 — LAN 瘦客戶端 + 資料庫持久化 + 儀表板 + Wine EXE 驗證
**研究日期:** 2026-04-24
**信心等級:** HIGH（多來源驗證，Context7 + 官方文件 + WebSearch 交叉比對）

---

## 關鍵陷阱（Critical Pitfalls）

### 陷阱 1：同一個 Event Loop 同時處理音檔上傳 + LLM 推理 + DB 寫入，導致服務完全凍結

**會出什麼問題:**
LAN 瘦客戶端上傳 WAV 音檔 → FastAPI 在同一個 async handler 內執行 LLM 推理（Gemma 4:E4B，GPU 佔用 3-8 秒）→ 同時寫入 SQLite 儲存 SOAP 記錄。LLM 推理是同步阻塞操作（llama-cpp-python 的 `generate()` 不會 yield event loop），期間 **所有** 其他 HTTP 請求（包括 `/health`、WebSocket 訊息、第二個醫師的 SOAP 請求）全部凍結。

更糟的是，如果 uvicorn 使用多 worker（如 `--workers 4`），每個 worker 都會嘗試載入一份 Gemma 4:E4B 模型到 VRAM（12GB RTX 3060），瞬間 OOM。

**為什麼會發生這種事:**
開發者習慣把 Flask/FastAPI 的 `BackgroundTasks` 當作「真背景執行」，但 `BackgroundTasks` 只是 defer 到 response 回傳後執行——**仍然在同一個 event loop/thread 內**。llama-cpp-python 的 `generate()` 是 CPU/GPU 密集操作，不會釋放 GIL 或 await。

**如何避免:**
1. **LLM 推理必須在獨立的 worker process 中執行**，透過內部佇列（如 `asyncio.Queue` + `ProcessPoolExecutor` 或 Redis+Celery）解耦 API 層與推理層
2. 如果只有一個 GPU，使用 **semaphore（信號量）** 限制同時推理請求數為 1
3. 音檔上傳使用 **chunked streaming**（`await file.read(CHUNK_SIZE)`），不要將整份 WAV 載入記憶體
4. DB 寫入也應加入佇列（避免 `SQLITE_BUSY`，見陷阱 2）

**預警訊號:**
- 處理一個 SOAP 請求時，`/health` endpoint 回應時間 >1s
- Uvicorn 日誌出現 `WARNING: Application startup complete` 後馬上出現 OOM
- `nvidia-smi` 顯示多個 process 嘗試載入 CUDA context

**應對階段:** （Phase 2 / LAN 搜客戶端架構 + Phase 7 / 儀表板重寫）

---

### 陷阱 2：SQLite 寫入競爭 — 多醫師同時請求導致 `SQLITE_BUSY`，SOAP 記錄流失

**會出什麼問題:**
SQLite 使用 **檔案層級鎖定**。WAL 模式允許多讀者同時讀取，但 **同時只能有一個寫入者**。當 3 個診間同時完成 SOAP 生成、同時嘗試寫入 `soap_records` 表格時，第二和第三個寫入會收到 `OperationalError: database is locked`（`SQLITE_BUSY`）。

現有程式碼的 `ClinicalDatabase._get_connection()` 和 `LocalDatabase._get_connection()` 都沒有設定 `busy_timeout` 或重試機制——寫入失敗 = SOAP 記錄永久流失（醫療資料不可接受）。

**為什麼會發生這種事:**
SQLite 並非 client-server 資料庫。FastAPI 搭配多 worker（`--workers N`）時，每個 worker 是獨立 process，無法協調寫入鎖。加上現有程式碼沒有 WAL 模式 pragma、沒有 busy_timeout、沒有重試邏輯。

**如何避免:**
1. **啟用 WAL 模式**：`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` — 這是 web app 的最低要求
2. **設定 busy_timeout**：`PRAGMA busy_timeout = 5000;` — 讓寫入等待 5 秒而非立即失敗
3. **序列化寫入**：使用 `asyncio.Lock` 或背景寫入佇列（單一 writer process）
4. **未來規劃**：如果診所規模 >5 位醫師同時使用，應規劃遷移至 PostgreSQL
5. **永不將 SQLite 檔案放在 NAS/NFS 上**：網路檔案系統的 POSIX 鎖實作不完整，會導致資料損毀

**預警訊號:**
- 日誌出現 `database is locked` 或 `OperationalError`
- 使用者回報「處理完成但病歷沒儲存」
- 寫入延遲隨醫師數量線性上升

**應對階段:** Phase 2（LAN 瘦客戶端）+ Phase 7（儀表板重寫/資料持久化）

---

### 陷阱 3：客戶端與伺服器 API 版本不一致 — 瘦客戶端 EXE 上傳格式變更導致 SOAP 生成失敗但無明顯錯誤

**會出什麼問題:**
瘦客戶端是 Windows EXE（PyInstaller 打包），伺服器端是 Python FastAPI 服務。當伺服器更新 API 合約（如新增必填欄位、變更 JSON 結構、修改 endpoint URL）而客戶端未同步更新時：

- 客戶端發送舊格式請求 → 伺服器回傳 422 Validation Error → 客戶端的 `try/except` 只顯示「API 錯誤」
- 更糟的是：伺服器接受請求但解讀錯誤，產生不完整的 SOAP 病歷，醫師未發現就存檔
- 現有 `desktop_app.py` 的 `process_audio_api()` 使用硬編碼 API 路徑（`/api/v1/extended/transcribe`、`/api/v1/extended/process`），無版本檢查

**為什麼會發生這種事:**
瘦客戶端缺乏自省能力——它不知道伺服器期望什麼。開發者通常假設 client 和 server 會同步更新，但在 LAN 部署中，客戶端 EXE 可能數週未更新。

**如何避免:**
1. **API 版本協商**：在每個請求 header 加入 `X-Client-Version`，伺服器啟動時（或 `/health`）回傳最低支援的客戶端版本
2. **客戶端啟動時檢查版本**：`desktop_app.py` 啟動時 call `GET /api/v1/version`，版本不相容時彈窗提示更新
3. **向後相容層**（Tolerant Reader 模式）：伺服器 API 只做加法變更（新增 optional 欄位，不刪除/不改名），客戶端忽略未知欄位
4. **在伺服器端記錄版本資訊**：每次請求記錄 client_version，便於追溯問題

**預警訊號:**
- 伺服器端 422 錯誤突然增加
- 不同診間的客戶端表現不一致（有的正常有的失敗）
- 客戶端 log 只有「API 錯誤」但無具體訊息

**應對階段:** Phase 2（LAN 瘦客戶端架構）

---

### 陷阱 4：Wine EXE 驗證 — PyInstaller 透過 Wine 交叉編譯不可靠，誤判「EXE 在 Linux 環境能跑 = Windows 能跑」

**會出什麼問題:**
PyInstaller **不支援交叉編譯**。在 Linux 用 Wine 執行 PyInstaller 產生的 EXE 可能在 Wine 環境「看似正常」，但放到真實 Windows 機器上出現：
- `Internal error: cannot create temporary directory`（bootloader 權限問題）
- Tkinter/ttkbootstrap 主題載入失敗（Wine 的 Win32 API 轉譯不完全）
- DLL 載入失敗（PyInstaller 打包了 Linux 版本的 `.so` 而非 Windows 的 `.dll`）
- `ModuleNotFoundError`（Wine 用系統 pip 但 EXE 需要 Wine 內的 Python）

**為什麼會發生這種事:**
Wine 不是模擬器，是 API 轉譯層。它不複製 Windows kernel、registry、檔案系統行為。Tkinter 依賴 Tcl/Tk 與底層視窗系統互動——Wine 下的行為與原生 Windows 不同。開發者容易將「Wine 下看到 GUI 視窗」誤認為「EXE 無問題」。

**如何避免:**
1. **禁止用 Wine 驗證功能正確性**：Wine 僅用於快速語法/啟動測試，不可作為功能驗證手段
2. **使用 CI/CD 原生 Windows runner 編譯**：GitHub Actions `windows-latest` runner 是唯一可靠的 PyInstaller 建置環境
3. **Wine 驗證的合理角色**：只驗證 PyInstaller spec 語法正確、啟動不 crash、基本 import 成功
4. **Windows 實機測試清單**：必須在真實 Windows 10/11 機器上測試（或 Windows VM）
   - 錄音功能（pyaudio + 麥克風）
   - 螢幕截圖 OCR
   - ttkbootstrap Superhero 主題完整渲染
   - 檔案路徑（`C:\Users\...` vs Linux 路徑）
   - 中文字型渲染

**預警訊號:**
- Wine 中測試「全部通過」但 Windows 上啟動 crash
- 檔案路徑錯誤（`/data/recordings/` 在 Windows 上變成 `C:\data\recordings\`）
- OCR 截圖儲存在 Linux 路徑但 Windows 上無法讀取

**應對階段:** Phase 5（Wine EXE 打包驗證）

---

### 陷阱 5：SOAP 病歷從檔案儲存遷移到資料庫時，漏掉不可變審計追蹤與版本控制

**會出什麼問題:**
v1.0 將 SOAP 結果僅存在 GUI 記憶體中（`current_soap_text`），儲存按鈕實際上不寫入磁碟（`save_and_shrink` 只是隱藏面板）。遷移到 SQLite 後：

- 醫師可事後修改 SOAP → 缺乏不可變審計追蹤 → 醫療糾紛時無法證明原始記錄
- 無 `created_at`、`updated_at`、`author_id` 欄位 → 無法追蹤誰在何時修改了什麼
- 直接 `UPDATE` SOAP 欄位而非 append-only → 失去歷史版本

**為什麼會發生這種事:**
開發者將 SOAP 儲存當作「一般 CRUD」，但醫療記錄是法律文件。HIPAA（美國）和台灣《醫療法》第 67-70 條要求病歷記錄完整、不可竄改、有明確時間戳和簽署人。

**如何避免:**
1. **SOAP 記錄表使用 append-only 設計**：每次修改建立新版本（`version` 欄位遞增），不直接 UPDATE 原始記錄
2. **審計追蹤表獨立儲存**：記錄 `user_id`、`action`（CREATE/READ/UPDATE）、`timestamp`、`record_id`、`before_value`、`after_value`
3. **使用 application-level 不可變性**：在應用層禁止對 SOAP 表格直接 UPDATE/DELETE（透過權限控制）
4. **數位簽章**（可選但推薦）：儲存時計算 SOAP 內容的 HMAC 或 hash，便於日後驗證完整性
5. **範例 schema**：
   ```sql
   CREATE TABLE soap_records (
       id INTEGER PRIMARY KEY,
       patient_id TEXT NOT NULL,
       transcript TEXT NOT NULL,
       soap_json TEXT NOT NULL,     -- 完整 SOAP JSON
       content_hash TEXT NOT NULL,  -- SHA-256
       created_at TEXT NOT NULL DEFAULT (datetime('now')),
       created_by TEXT NOT NULL,    -- 醫師 ID
       version INTEGER NOT NULL DEFAULT 1
   );
   CREATE TABLE soap_audit_log (
       id INTEGER PRIMARY KEY,
       record_id INTEGER NOT NULL,
       action TEXT NOT NULL,        -- 'CREATED', 'VIEWED', 'AMENDED'
       user_id TEXT NOT NULL,
       timestamp TEXT NOT NULL DEFAULT (datetime('now')),
       details TEXT                 -- before_value, after_value (JSON)
   );
   ```

**預警訊號:**
- SOAP 表格允許直接 UPDATE 而無審計記錄
- 沒有 `created_at` / `updated_at` / `created_by` 欄位
- 儲存按鈕只是 UI 行為，沒有實際持久化

**應對階段:** Phase 7（儀表板重寫/資料持久化）

---

### 陷阱 6：LAN 音檔上傳未使用 chunked streaming，導致 12GB RAM 伺服器在同時 3+ 個錄音請求時 OOM

**會出什麼問題:**
WAV 錄音檔（16kHz, 16bit, mono）每分鐘約 1.92MB。一次診療錄音通常 5-10 分鐘（10-20MB）。但現有 `process_audio_api()` 使用 `requests.post(files={"audio": f})` 將整份檔案讀入記憶體。

LAN 部署中，如果 3 個診間同時結束錄音、同時上傳 20MB WAV 檔，加上 LLM 模型佔用 ~10GB VRAM + 系統 RAM，容易觸發 OOM。

**為什麼會發生這種事:**
FastAPI 的 `UploadFile` 內部使用 `SpooledTemporaryFile`，但 `requests` 客戶端（desktop_app.py）是一次性讀取全部內容後 POST。伺服器端雖然 FastAPI 支援 streaming，但現有 API endpoint 可能未實作 chunked write。

**如何避免:**
1. **伺服器端使用 chunked 接收**：
   ```python
   @app.post("/api/v1/audio/upload")
   async def upload_audio(file: UploadFile = File(...)):
       file_path = f"data/recordings/{file.filename}"
       async with aiofiles.open(file_path, "wb") as out:
           while chunk := await file.read(1024 * 1024):  # 1MB chunks
               await out.write(chunk)
   ```
2. **客戶端也使用 streaming upload**：使用 `requests` 的 streaming 或改用 `httpx` async client
3. **設定檔案大小上限**：在 API 層限制 `MAX_UPLOAD_SIZE = 50MB`，拒絕過大請求
4. **非同步處理上傳後的推理**：檔案接收完成 → 回傳 202 Accepted → 背景佇列處理 SOAP → WebSocket 或 polling 通知結果

**預警訊號:**
- 伺服器 RAM 使用量隨同時錄音數線性增長
- 大檔案（>20MB）上傳時 API 回應逾時
- uvicorn worker 重啟

**應對階段:** Phase 2（LAN 瘦客戶端架構）

---

### 陷阱 7：儀表板監控 endpoint 使用輪詢而非 SSE，導致每秒數十次 HTTP 請求拖垮伺服器

**會出什麼問題:**
為顯示「即時 GPU 使用率、請求量、處理時間」圖表，前端使用 `setInterval()` 每秒輪詢 `/api/v1/monitor/stats`。當 5 個診間 + 護理站共 6 個 dashboard 同時開啟時，每秒產生 6 個 HTTP 請求。

這些請求觸發資料庫查詢（讀取統計表）、GPU 狀態查詢（nvidia-smi 或 pynvml），每個請求耗時 50-100ms → 累積阻塞 event loop → SOAP 生成請求排隊等待。

**為什麼會發生這種事:**
開發者習慣用 polling 做 dashboard（最簡單），但低估累積效應。FastAPI 的 event loop 是單執行緒，polling 請求的同步 DB 查詢會短暫阻塞所有其他請求。

**如何避免:**
1. **使用 Server-Sent Events (SSE)** 取代輪詢：伺服器推送更新，客戶端被動接收
   ```python
   from fastapi.responses import StreamingResponse
   @app.get("/api/v1/monitor/stream")
   async def monitor_stream():
       async def event_generator():
           while True:
               stats = await get_system_stats()
               yield f"data: {json.dumps(stats)}\n\n"
               await asyncio.sleep(2)  # 2 秒更新一次
       return StreamingResponse(event_generator(), media_type="text/event-stream")
   ```
2. **如果必須用 polling，加入 jitter**：客戶端不使用固定間隔（如 5s±500ms），避免同時請求高峰
3. **快取監控數據**：將 GPU 狀態、請求計數等快取在記憶體中（使用 `asyncio` 背景任務每 2 秒更新一次），dashboard 請求不直接查 DB/nvidia-smi
4. **分離監控資料庫**：監控統計使用獨立的 SQLite 檔案或 in-memory 儲存，不影響主業務資料庫

**預警訊號:**
- 儀表板開啟時，SOAP 生成延遲明顯增加
- Uvicorn access log 每 1 秒規律出現 `/monitor/stats` 請求
- 資料庫 lock 頻率與 dashboard 開啟數量正相關

**應對階段:** Phase 7（儀表板重寫/資料持久化）

---

### 陷阱 8：瘦客戶端網路中斷時，錄音資料遺失且無本地備份

**會出什麼問題:**
LAN 不穩定（WiFi 干擾、交換機故障、網路線鬆脫）時，瘦客戶端正在錄音中 → 錄音結束後嘗試上傳到伺服器 → 網路中斷 → 請求失敗 → `desktop_app.py` 的 `process_audio_api` 只顯示「API 錯誤」。

此時 WAV 檔案 `data/recordings/temp.wav` 如果是被下一個錄音覆蓋，則本次錄音永久遺失。

**為什麼會發生這種事:**
瘦客戶端設計中，客戶端被視為「啞終端」——錄音完成後不留本地副本。但現有程式碼每次錄音寫入 `temp.wav`（固定檔名），下次錄音即覆蓋。

**如何避免:**
1. **每次都使用時間戳命名錄音檔**：`data/recordings/20260424_143025_{patient_id}.wav`，而非固定 `temp.wav`
2. **瘦客戶端本地保留副本**：上傳成功後才刪除本機檔案（或移至 `data/recordings/synced/`）
3. **實作重試機制**：上傳失敗時自動重試（exponential backoff，最多 3 次）
4. **離線佇列**：網路中斷時將錄音加入本地佇列，恢復連線後自動同步
5. **狀態機管理**：`RecordingState` enum 應包含 `UPLOADING`、`UPLOAD_FAILED`、`SYNCED` 等狀態

**預警訊號:**
- 使用者回報「錄完了但沒看到 SOAP」
- `data/recordings/` 目錄只有 `temp.wav`
- 網路斷線事件與遺失錄音數量相關

**應對階段:** Phase 2（LAN 瘦客戶端架構）

---

### 陷阱 9：Python 多執行緒與 llama-cpp-python GPU 並行推理的 VRAM 競爭

**會出什麼問題:**
當多位醫師同時送出 SOAP 生成請求時，如果使用多個 thread/process 同時呼叫 `llama_engine.generate()`：
- 每個 concurrent 推理請求都會嘗試在 GPU 上配置 KV cache
- RTX 3060 12GB 只能容納一個 Gemma 4:E4B (9.6GB) 模型的完整上下文
- 第二個並發請求導致 CUDA OOM → crash 或 fallback 到 CPU（極慢）

**為什麼會發生這種事:**
llama-cpp-python 的 `generate()` 不是 thread-safe 的 GPU 操作。LLM 推理本質上是序列化操作——GPU batch inference 需要特別設計。

**如何避免:**
1. **使用請求佇列 + semaphore**：
   ```python
   _inference_semaphore = asyncio.Semaphore(1)  # 一次只允許一個推理
   async def generate_soap_endpoint(request):
       async with _inference_semaphore:
           result = await run_in_executor(llama_engine.generate, prompt)
   ```
2. **非同步通知結果**：SOAP 請求立即回傳 202 Accepted，完成後透過 WebSocket 推送結果給客戶端
3. **考慮使用 llama.cpp server mode**：llama.cpp 的 server 模式內建請求佇列和並行控制
4. **監控 GPU 使用率**：dashboard 顯示排隊請求數量和預估等待時間

**預警訊號:**
- 第二位醫師開始處理時，第一位醫師的推理速度驟降或 crash
- CUDA OOM 錯誤
- `nvidia-smi` 顯示 VRAM 使用率瞬間從 ~10GB 跳到 12GB

**應對階段:** Phase 2（LAN 瘦客戶端架構）

---

## 技術債模式（Technical Debt Patterns）

| 捷徑 | 立即好處 | 長期代價 | 何時可接受 |
|------|----------|----------|-----------|
| 用 `BackgroundTasks` 處理 LLM 推理 | 快速實作，程式碼簡單 | 阻塞 event loop，多用戶時服務凍結 | 永不（醫療場景不可接受） |
| SQLite 不用 WAL 模式直接上線 | 零配置 | `SQLITE_BUSY` 導致病歷紀錄流失 | 僅單人開發測試時 |
| 固定檔名 `temp.wav` 儲存錄音 | 簡單 | 錄音覆蓋遺失，無法追溯 | 僅開發階段 |
| GUI 記憶體中儲存 SOAP（不寫 DB） | 無 DB 依賴 | 重開後病歷消失，無法追蹤歷史 | v1.0 單機版（現狀） |
| Wine 測試當作 Windows 驗證 | 方便，不須 VM | 誤判相容性，Windows 實機 crash | 只用於 PyInstaller spec 語法檢查 |
| 硬編碼 API URL（`http://127.0.0.1:8010`） | 簡單 | 換伺服器 IP 需重新打包 EXE | 開發階段，上線前必須改用設定檔 |

---

## 整合陷阱（Integration Gotchas）

| 整合點 | 常見錯誤 | 正確做法 |
|--------|----------|----------|
| 客戶端 WAV → 伺服器 ASR | 將整份 WAV 讀入記憶體後 POST | 使用 chunked streaming upload（`aiofiles` + `UploadFile.read(chunk_size)`） |
| 伺服器 ASR → LLM 推理 | 在 async handler 內同步呼叫 `llama_engine.generate()` | 將推理放入 `ProcessPoolExecutor` 或獨立 worker process，搭配 semaphore |
| LLM 推理 → DB 寫入 | 推理完成後直接 `conn.execute(INSERT)` | 寫入操作經由佇列/背景 writer，處理 `SQLITE_BUSY` 重試 |
| DB 寫入 → Dashboard 推送 | 沒有通知機制，dashboard 靠 polling 發現新資料 | DB 寫入後透過 SSE/WebSocket 推送事件給 dashboard |
| 客戶端 EXE + 伺服器 API | 無版本檢查，API 變更後舊 EXE 默默失敗 | 啟動時版本協商，不相容時強制提示更新 |
| NAS 備份 + SQLite | SQLite 資料庫放在 rsync 同步的 NAS 路徑上 | 備份 SQLite 前先 `VACUUM INTO` 或 `sqlite3 .backup`；不可直接同步開啟中的 DB 檔案 |
| 錄音儲存 + DB 記錄 | 錄音檔路徑存在 DB 但實際檔案已被刪除 | 使用外鍵約束或週期性清理 orphan 檔案 |

---

## 效能陷阱（Performance Traps）

| 陷阱 | 症狀 | 預防 | 何時崩潰 |
|------|------|------|----------|
| 單一 event loop 處理所有請求 | 一個 SOAP 生成中，其他請求排隊 | LLM 推理移至獨立 process，API 層只做路由 | >1 同時用戶 |
| SQLite 無 WAL 模式 | 寫入時阻塞所有讀取 | `PRAGMA journal_mode=WAL;` | >2 同時請求 |
| 輪詢 dashboard 每秒查詢 | SOAP 生成延遲從 5s 變 8s+ | SSE 推送 + 記憶體快取 | >3 個 dashboard 同時開 |
| 大檔案同步上傳 | 上傳期間 event loop 凍結 | chunked streaming + async file I/O | >20MB WAV 檔案 |
| 多 worker 重複載入 LLM 模型 | VRAM OOM，worker crash | 單一 inference worker，API 層用佇列 | 任何 uvicorn `--workers >1` |

---

## 安全陷阱（Security Mistakes）

| 錯誤 | 風險 | 預防 |
|------|------|------|
| API Key 僅存在記憶體，無持久化撤銷機制 | `SecurityManager._api_keys` 存在記憶體中，伺服器重啟後自訂 API key 遺失 | 將 API key 持久化到資料庫或環境變數中；支援動態撤銷 |
| Dashboard 監控端點無認證 | 暴露 GPU 使用率、請求量、甚至請求內容 | 所有 `/monitor/*` endpoint 需要 API Key/JWT 驗證 |
| SOAP 病歷明碼儲存於 SQLite | 資料庫檔案被複製即可讀取所有病患 SOAP | 使用 SQLCipher 加密 SQLite 或 application-level 欄位加密 |
| 音檔透過 HTTP 明文傳輸 | LAN 內可被嗅探，錄音內容洩漏 | 使用 HTTPS（自簽憑證即可，LAN 內足夠）或 API-level 加密 payload |
| 無存取控制（所有醫師看到所有病歷） | 違反最小必要原則 | 至少實作醫師級別隔離（`created_by` 欄位 + 查詢過濾） |

---

## UX 陷阱（UX Pitfalls）

| 陷阱 | 使用者影響 | 改善方式 |
|------|-----------|----------|
| SOAP 生成中無進度回饋 | 醫師不確定系統是否在處理 | 顯示進度條 + 預估完成時間（如「Gemma 推理中，預計 5 秒」） |
| 網路中斷時無提示 | 錄音看似正常但實際上傳失敗 | 在 GUI 顯示連線狀態指示器（綠/黃/紅燈） |
| 儲存按鈕無實際持久化 | 醫師以為已儲存，但重開後找不到 | 儲存後顯示確認（「已儲存至本地資料庫」+ 時間戳） |
| 錯誤訊息不透明 | 「❌ API 錯誤」無法幫助診斷 | 區分錯誤類型：網路中斷 / 伺服器忙碌 / 認證失敗 / ASR 失敗 |
| 展開/收合模式混亂 | 處理完成後自動展開，但醫師可能不想 | 提供手動展開選項，或讓使用者設定 auto-expand 行為 |

---

## 「看似完成但其實沒有」檢查清單

- [ ] **SOAP 持久化儲存:** 看似存了但重開後消失 — 驗證：重啟伺服器後查詢歷史 SOAP 記錄
- [ ] **錄音檔案保留:** 看似有存但只有 temp.wav — 驗證：錄製 3 次後檢查 `data/recordings/` 目錄
- [ ] **LAN 客戶端連線:** 看似能連但換 IP 就掛 — 驗證：更改 `API_BASE_URL` 後重新啟動
- [ ] **多人同時使用:** 看似能處理但輪到第三位醫師就卡住 — 驗證：3 人同時送出 SOAP 請求
- [ ] **審計追蹤:** 看似有 log 但可以 UPDATE 直接改 — 驗證：嘗試直接修改資料庫中的 SOAP 內容
- [ ] **Windows EXE 真實相容:** 看似 Wine 能跑但 Windows 實機 crash — 驗證：在 Windows 10/11 實機測試完整流程
- [ ] **Dashboard 即時更新:** 看似刷新但實際上是快取 — 驗證：生成一個新 SOAP，檢查 dashboard 是否 2 秒內出現
- [ ] **備份完整性:** 看似有備份但 SQLite 檔案在備份時損毀 — 驗證：從備份還原並查詢所有記錄

---

## 復原策略

| 陷阱 | 復原成本 | 復原步驟 |
|------|---------|----------|
| `SQLITE_BUSY` 導致記錄流失 | HIGH（需重建架構） | 1) 啟用 WAL + busy_timeout 2) 實施寫入佇列 3) 如果已久 → 考慮遷移 PostgreSQL |
| 無審計追蹤的 UPDATE | MEDIUM | 1) 將現有表格改為 append-only 2) 建立審計表格 3) 從備份還原歷史版本 |
| Wine EXE 誤判相容性 | LOW（修正流程即可） | 1) 建立 Windows CI runner 2) 重新打包 3) Wine 改為僅語法檢查用途 |
| 固定檔名覆蓋錄音 | MEDIUM（資料可能已遺失） | 1) 改用時間戳命名 2) 檢查備份 3) 實施保留策略 |
| 多 worker 載入模型 OOM | LOW（設定調整） | 1) 改為單 worker + inference process 2) 設定 semaphore |

---

## 陷阱與階段對應表

| 陷阱 | 預防階段 | 驗證方式 |
|------|----------|----------|
| Event loop 阻塞（LLM + upload） | Phase 2（LAN 搜客戶端） | 3 人同時請求，`/health` 回應 <200ms |
| SQLite 寫入競爭 | Phase 2 + Phase 7 | 3 人同時寫入，零 `SQLITE_BUSY` |
| API 版本不一致 | Phase 2（LAN 搜客戶端） | 舊版 EXE 啟動時顯示更新提示 |
| Wine EXE 誤判 | Phase 5（Wine EXE 驗證） | Windows 10/11 實機完整測試 |
| SOAP 審計追蹤缺失 | Phase 7（儀表板/DB） | 嘗試 UPDATE，審計表有記錄 |
| LAN 音檔 OOM | Phase 2（LAN 搜客戶端） | 3 個 20MB 同時上傳，RAM < 2GB 增長 |
| Dashboard 輪詢拖垮 | Phase 7（儀表板/DB） | 儀表板開啟時 SOAP 延遲無明顯增加 |
| 離線錄音遺失 | Phase 2（LAN 搜客戶端） | 錄音期間拔網路線 → 檔案仍在本地 |
| GPU VRAM 競爭 | Phase 2（LAN 搜客戶端） | 同時 2 個 SOAP 請求，無 CUDA OOM |
| 無備份驗證 | Phase 7（儀表板/DB） | 從備份還原後所有記錄可查詢 |

---

## 來源

- **SQLite 並行性**：FastAPI + SQLite WAL 模式最佳實踐（Google Search，2025-2026 多來源驗證，HIGH confidence）
- **醫療資料庫設計**：HIPAA 合規、FHIR 標準、審計追蹤模式（多篇 2025 文章，MEDIUM-HIGH confidence）
- **LAN 搜客戶端架構**：VDI 音訊傳輸最佳實踐、QoS、endpoint offloading（Google Search 2025，MEDIUM confidence — SoapVoice 非 VDI 場景，但網路/客戶端模式通用）
- **Wine + PyInstaller**：PyInstaller 官方文件明確表示不支援交叉編譯（官方文件，HIGH confidence）；Wine GUI 相容性（Reddit/StackExchange 2025-2026，MEDIUM confidence）
- **FastAPI 即時監控**：SSE vs WebSocket vs Polling 取捨（多篇 2025-2026 文章，HIGH confidence）
- **LLM 推理並行**：FastAPI + GPU inference 阻塞問題（Google Search 2025，HIGH confidence）
- **專案原始碼分析**：SoapVoice 現有架構（`src/main.py`、`src/api/websocket.py`、`src/soap/soap_generator.py`、`src/gui/desktop_app.py`、`src/db/clinical_db.py`、`src/security/auth.py`）

---

*陷阱研究：SoapVoice v1.1 網路部署與資料管理*
*研究日期：2026-04-24*
*信心等級：HIGH（多來源交叉驗證 + 原始碼分析）*
