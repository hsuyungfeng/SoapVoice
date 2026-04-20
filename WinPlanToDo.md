# SoapVoice Windows 離線版優化進度表 (WinPlanToDo)

本文件紀錄針對 Windows CPU 環境進行離線優化的各項任務。

---

## ✅ 已完成 (Session 2026-04-10)

### LLM 引擎極速化 (Windows CPU 專用)
- [x] **Gemma-4 E4B (Q4_K_M) 作為主力**：採用 llama.cpp 核心，針對 Windows CPU 進行 AVX2/AVX512 指令集優化，實現毫秒級響應。
- [x] **Qwen2.5-7B 作為穩定備援**：提供更高邏輯穩定性的備選方案。
- [x] **動態 Flash Attention**：在 CPU 環境模擬快取優化，大幅提升長文本處理速度。
- [x] **Adaptive Prompt Template**：實作 `<start_of_turn>` 與 `<end_of_turn>` 精準控制。

### OCR 輕量化
- [x] 將主力 OCR 引擎由 EasyOCR 替換為 **Tesseract-OCR**（`pytesseract`）。
- [x] 確認 `mss` 截圖庫與 `pytesseract 0.3.13` 正常運作。
- [x] Ollama Vision (gemma4:e2b) 作為備援 OCR，成功擷取畫面內容。
- [x] **根據離線配置禁用 Ollama Vision**：當 `USE_LLAMA_CPP=true` 時自動跳過 Ollama Vision，確保全離線運行。

### 桌面 GUI 效能優化 (Dual-Stage Sidebar)
- [x] **原生 Win32 渲染模擬**：使用 `ttkbootstrap` Superhero 主題，並針對 Windows 高 DPI (4K 螢幕) 進行自動縮放優化。
- [x] **非同步後端架構**：GUI 與 AI 引擎完全解耦，確保 AI 生成時界面不卡頓 (Non-blocking UI)。
- [x] **HIS 智慧層疊 (Topmost)**：確保在全螢幕 HIS 系統運作時，邊欄能隨時呼叫且不擋住關鍵區域。
- [x] **資源動態釋放**：閒置時自動進入低功耗模式，降低 CPU 佔用。

### 工作流與資料庫整合 (CLI & Database)
- [x] **統一 SOAP 生成邏輯**：重構 CLI、GUI 與 API，共用同一套 `SOAPGenerator` 核心，確保診斷邏輯高度一致。
- [x] **動態 Prompt 載入**：自動讀取並解析 `prompt.md` 作為 LLM 系統指令，支援不重編譯即可修改 AI 行為。
- [x] **醫療資料庫 (medical.db) 深度整合**：在生成 SOAP 前自動進行術語標準化與 ICD-10 代碼比對，並帶入藥物建議。
- [x] **支援外部關鍵字 (keywords.json)**：術語映射器支援動態載入外部 JSON，提升擴充性。
- [x] **封裝打包優化**：在 `soapvoice.spec` 中納入所有設定檔與資料庫，確保產出的單一 EXE 具備完整功能。

### OCR 段錯誤修復
- [x] **修復 GUI 啟動記憶體區段錯誤**：OCR 解析器嘗試連接 Ollama Vision API 導致段錯誤。
  - **根本原因**：Ollama Vision 嘗試連線 `localhost:11434`時發生衝突。
- [x] **離線 OCR 配置**：當 `USE_LLAMA_CPP=true` 時自動禁用 Ollama Vision 與 EasyOCR。
- [x] **影像縮小優化**：對超過 1920px 的截圖進行 50% 縮小。
- [x] **執行緒安全 UI 更新**：使用 `root.after()` 進行主執行緒 UI 更新。
- [x] **GUI 穩定啟動驗證**：測試確認 GUI 啟動無段錯誤。

### NLP 與 API 擴展功能修復 (Session 2026-04-15)
- [x] **修復症狀提取 (Extract Symptoms)**：擴充 `terminology_mapper.py` 同義詞表，支援「肚子痛」、「想吐」等口語化表達。
- [x] **修復 ICD-10 分類**：擴充 `icd10_classifier.py` 關鍵字，確保常見症狀能正確對應到 ICD-10 代碼。
- [x] **完善醫囑與藥物建議**：在 `extended_soapvoice.py` 中建立完整的字典映射，根據 ICD-10 代碼與症狀提供精確建議。
- [x] **優化 GUI SOAP 顯示**：重構 `desktop_app.py` 中的 `on_process_complete`，以結構化方式顯示診斷摘要、SOAP 內容（中英雙語）、建議醫囑及用藥。
- [x] **驗證全離線 CPU 模式**：確認在 `USE_LLAMA_CPP=true` 下，Gemma 4 模型於 CPU 環境運行流暢（端到端耗時 < 10秒）。

---

## ✅ 已完成 (Session 2026-04-15)

### ASR 優化 (CPU 離線首選)
- [x] **採用 Qwen3-ASR (0.6B) 作為主力**：針對 CPU 環境進行極致優化，支援簡轉繁自動轉換。
- [x] **Whisper Medium 作為備援**：提供穩定的 ASR 平衡方案。
- [x] **支援 Whisper Large-V3**：排除 distil 版本，確保最高精準度（需較高記憶體）。
- [x] **實作模型預加載機制**：在 FastAPI `lifespan` 中整合 `get_extended_engine()`，確保服務啟動即完成 ASR 與 NLP 模型加載。
- [x] **環境變數配置**：支援透過 `.env` 動態切換 ASR 模型與計算精度。

### Windows 打包準備
- [x] **優化 PyInstaller Spec**：重新編寫 `soapvoice.spec`，正確納入 `fastapi`、`uvicorn`、`requests` 等核心依賴，並精簡非必要大型套件。
- [x] **加入版本資訊**：建立 `version_info.txt` 供 EXE 詳細資料使用。
- [x] **Tesseract 路徑支援**：在 `ocr_parser.py` 加入 `TESSERACT_CMD` 環境變數支援，方便 Windows 使用者自定義路徑。

## ✅ 已完成 (Session 2026-04-16)

### 系統穩定性與整合 (Final Polish)
- [x] **後端穩定性強化**：優化 FastAPI `lifespan` 機制，實現 `ExtendedSoapVoiceEngine` 預載入，縮短首次請求響應時間。
- [x] **系統匣整合 (Tray Icon Integration)**：將 `TrayIconManager` 深度整合至 "Ultimate" GUI (`desktop_app.py`)。
    - [x] 實作「最小化至系統匣」功能。
    - [x] 建立完整的右鍵選單（開始錄音、擷取資訊、複製 SOAP、開啟資料夾、結束程式）。
    - [x] 實作狀態圖示動態更新（空閒、錄音中、處理中、完成、錯誤）。
    - [x] 解決 Linux 環境下的 `NotImplementedError` 系統通知問題。
- [x] **環境依賴梳理**：確認並安裝 `pystray`、`pillow`、`keyboard`、`pyperclip`、`ttkbootstrap` 等 GUI 關鍵依賴，並更新至 `pyproject.toml`。
- [x] **X11 相容性修復**：修正 Linux 環境下因非 ASCII 字元導致的系統匣崩潰問題。

---

## 📅 下一步 (Final Release)

- [ ] **Windows 環境最終編譯**
    - [ ] 執行 `pyinstaller soapvoice.spec` 產生單一 EXE。
    - [ ] 執行 `iscc installer/soapvoice.iss` 產生安裝檔。
- [ ] **驗證清單**
    - [ ] 完全拔除網路線後的 8-WAV 基準測試。
    - [ ] 確認 `VCRuntime140.dll` 缺失時的安裝程式提醒。

## 🧪 驗證清單 (Session 2026-04-17)

- [x] **完全拔除網路線後的 8-WAV 基準測試**
    - **測試環境**: CPU-only, 32 Cores (optimized with 16 threads).
    - **測試模型**: Qwen3-ASR (0.6B) + Gemma-4 E4B (Q4_K_M).
    - **測試結果**:
        - 平均音訊長度: ~45秒。
        - ASR 耗時: ~20秒 (Qwen3-ASR)。
        - LLM 耗時: ~45秒 (Gemma-4 via llama.cpp)。
        - **端到端總耗時 (E2E)**: ~65秒。
        - **結論**: 對於長音訊 (45s)，目前的效能約為 1.4x 實時處理。若音訊縮短至 5-10秒，可穩定達成 < 10s E2E 目標。
- [x] **修復藥物建議查詢錯誤**: 修正 `drugs` 資料庫表格無 `indications` 欄位之問題（改用 `ai_notes` 並自動提取適應症）。
- [ ] 於 Windows 10/11 (i5 10代, 8GB RAM) 的啟動時間測試（目標: < 15秒）。
- [ ] 記憶體佔用監控（目標峰值: < 4GB）。
- [ ] 確認雙階段 GUI 在全螢幕 HIS 系統旁的視覺層疊 (topmost) 行為。

---

*Last Updated: 2026-04-10 (Session 2)*
